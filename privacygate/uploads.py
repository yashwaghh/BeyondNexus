"""Memory-only image and small-PDF privacy review for iteration two."""
from __future__ import annotations

import io
import base64
import math
from dataclasses import asdict, dataclass, field
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError
import pypdfium2 as pdfium
from pypdf import PdfReader

from .detectors import detect_rules
from .model import GemmaLocalClient, LocalModelError, VisionFinding
from .pipeline import HIGH_THRESHOLD, sanitize
from .ocr import TesseractOCR, OCRError

MAX_UPLOAD_BYTES = 6 * 1024 * 1024
MAX_PDF_PAGES = 5
MAX_IMAGE_PIXELS = 20_000_000
MAX_RENDER_EDGE = 2200
SUPPORTED_IMAGE_TYPES = {'image/png', 'image/jpeg', 'image/webp'}
SUPPORTED_UPLOAD_TYPES = SUPPORTED_IMAGE_TYPES | {'application/pdf'}


class UploadReviewError(ValueError):
    pass


@dataclass
class UploadReviewResult:
    media_type: str
    page_count: int
    sanitized_text: str | None
    findings: list[dict]
    status: str
    requires_human_review: bool
    vision_attempted: bool
    vision_succeeded: bool
    warnings: list[str]
    ocr_attempted: bool = True
    ocr_succeeded: bool = False
    ocr_pages: list[dict] = field(default_factory=list)
    export_available: bool = False
    preview_pages: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _normalized_png(data: bytes) -> bytes:
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as opened:
                opened.load()
                image = ImageOps.exif_transpose(opened).convert('RGB')
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise UploadReviewError('Invalid, unsupported, or oversized image.') from None
    if image.width * image.height > MAX_IMAGE_PIXELS:
        raise UploadReviewError('Image pixel count exceeds the local review limit.')
    image.thumbnail((MAX_RENDER_EDGE, MAX_RENDER_EDGE), Image.Resampling.LANCZOS)
    output = io.BytesIO()
    image.save(output, format='PNG', optimize=True)
    return output.getvalue()


def _pdf_text_pages(data: bytes) -> tuple[list[str], list[dict], list[str]]:
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted and not reader.decrypt(''):
            raise UploadReviewError('Encrypted PDFs are not supported in this iteration.')
        if len(reader.pages) == 0:
            raise UploadReviewError('PDF has no pages.')
        if len(reader.pages) > MAX_PDF_PAGES:
            raise UploadReviewError(f'PDF exceeds the {MAX_PDF_PAGES}-page iteration-two limit.')
        structural_findings: list[dict] = []
        structural_warnings: list[str] = []
        metadata = reader.metadata
        for field in ('/Author', '/Title', '/Subject', '/Keywords'):
            if metadata and metadata.get(field):
                structural_findings.append({
                    'page': None,
                    'entity': 'OTHER_PII',
                    'score_heuristic': 0.55,
                    'source': 'pdf_metadata',
                    'rationale': f'PDF {field[1:]} metadata is present; value withheld from results.',
                    'decision': 'flag_and_review',
                    'region_0_1000': None,
                })
        root = reader.trailer.get('/Root')
        if root:
            if root.get('/AcroForm'):
                structural_warnings.append('PDF contains form fields; hidden or stale field values may require separate inspection.')
            names = root.get('/Names')
            if names and names.get('/EmbeddedFiles'):
                structural_warnings.append('PDF contains embedded files; attachments are not scanned and the upload remains high risk.')
                structural_findings.append({
                    'page': None,
                    'entity': 'OTHER_PII',
                    'score_heuristic': 0.55,
                    'source': 'pdf_structure',
                    'rationale': 'PDF contains unscanned embedded files.',
                    'decision': 'flag_and_review',
                    'region_0_1000': None,
                })
            if root.get('/Metadata'):
                structural_warnings.append('PDF contains an XML metadata stream; values are not exposed in results.')
        return ([(page.extract_text() or '').strip() for page in reader.pages],
                structural_findings, structural_warnings)
    except UploadReviewError:
        raise
    except Exception:
        raise UploadReviewError('Invalid or unsupported PDF structure.') from None


def _render_pdf_pages(data: bytes) -> list[bytes]:
    rendered: list[bytes] = []
    try:
        document = pdfium.PdfDocument(data)
        try:
            if len(document) == 0 or len(document) > MAX_PDF_PAGES:
                raise UploadReviewError('PDF page count is outside the supported limit.')
            for index in range(len(document)):
                page = document[index]
                bitmap = None
                try:
                    width, height = page.get_size()
                    if not all(math.isfinite(value) and value > 0 for value in (width, height)):
                        raise UploadReviewError('Invalid PDF page dimensions.')
                    # Bound native raster allocation before rendering, rather than after it.
                    scale = min(2, MAX_RENDER_EDGE / max(width, height))
                    bitmap = page.render(scale=scale)
                    image = bitmap.to_pil().convert('RGB')
                    image.thumbnail((MAX_RENDER_EDGE, MAX_RENDER_EDGE), Image.Resampling.LANCZOS)
                    output = io.BytesIO()
                    image.save(output, format='PNG', optimize=True)
                    rendered.append(output.getvalue())
                finally:
                    if bitmap is not None:
                        bitmap.close()
                    page.close()
        finally:
            document.close()
    except UploadReviewError:
        raise
    except Exception:
        raise UploadReviewError('PDF pages could not be rendered safely.') from None
    return rendered


def _vision_metadata(finding: VisionFinding, page: int) -> dict:
    return {
        'page': page,
        'entity': finding.entity,
        'score_heuristic': finding.confidence,
        'source': finding.source,
        'rationale': finding.rationale,
        'decision': 'flag_and_review',
        'region_0_1000': list(finding.region) if finding.region else None,
    }


def combine_findings(findings: list[dict]) -> list[dict]:
    """Combine strong same-type spatial agreement; preserve disagreements/unlocated evidence."""
    combined = []
    for finding in findings:
        candidate = dict(finding)
        candidate['evidence_sources'] = [finding['source']]
        box = finding.get('region_0_1000')
        match = None
        if box:
            for previous in combined:
                other = previous.get('region_0_1000')
                if not other or previous['page'] != finding['page'] or previous['entity'] != finding['entity']:
                    continue
                intersection = max(0, min(box[2], other[2])-max(box[0], other[0])) * max(0, min(box[3], other[3])-max(box[1], other[1]))
                union = (box[2]-box[0])*(box[3]-box[1]) + (other[2]-other[0])*(other[3]-other[1]) - intersection
                if union and intersection / union >= .5:
                    match = previous
                    break
        if match is None:
            combined.append(candidate)
        elif finding['source'] not in match['evidence_sources']:
            match['evidence_sources'].append(finding['source'])
            # Never average model and OCR scores into a fabricated safety probability.
    return combined


def review_upload(data: bytes, media_type: str, *, vision_mode: str = 'always',
                  model: GemmaLocalClient | None = None,
                  include_previews: bool = False, ocr=None) -> UploadReviewResult:
    if media_type not in SUPPORTED_UPLOAD_TYPES:
        raise UploadReviewError('Only PNG, JPEG, WebP, and PDF uploads are supported.')
    if vision_mode not in {'off', 'always'}:
        raise UploadReviewError('vision_mode must be off or always.')
    if not data:
        raise UploadReviewError('Upload is empty.')
    if len(data) > MAX_UPLOAD_BYTES:
        raise UploadReviewError(f'Upload exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.')

    warnings_out = [
        'Vision and text extraction can miss personal information; inspect every page or image manually.',
        'Detected boxes are suggestions. Review and edit masks before preparing a redacted export; missed information can remain.',
    ]
    findings: list[dict] = []
    sanitized_text: str | None = None
    text_pages: list[str] = []
    if media_type == 'application/pdf':
        if not data.startswith(b'%PDF-'):
            raise UploadReviewError('File content does not match the declared PDF type.')
        text_pages, structural_findings, structural_warnings = _pdf_text_pages(data)
        findings.extend(structural_findings)
        warnings_out.extend(structural_warnings)
        rendered_pages = _render_pdf_pages(data)
        sanitized_pages: list[str] = []
        for page_number, text in enumerate(text_pages, start=1):
            if not text:
                sanitized_pages.append(f'--- Page {page_number}: no extractable text layer ---')
                continue
            rule_findings = detect_rules(text)
            sanitized_pages.append(f'--- Page {page_number} ---\n{sanitize(text, rule_findings)}')
            findings.extend({
                'page': page_number,
                'start': finding.start,
                'end': finding.end,
                'entity': finding.entity,
                'score_heuristic': finding.confidence,
                'source': f'text_layer:{finding.source}',
                'rationale': finding.rationale,
                'decision': 'mask_and_review' if finding.confidence < HIGH_THRESHOLD else 'mask',
                'region_0_1000': None,
            } for finding in rule_findings)
        sanitized_text = '\n\n'.join(sanitized_pages)
    else:
        rendered_pages = [_normalized_png(data)]

    ocr_engine = ocr if ocr is not None else TesseractOCR()
    ocr_pages = []
    ocr_succeeded = True
    for page_number, page_png in enumerate(rendered_pages, start=1):
        try:
            page_ocr = ocr_engine.recognize(page_png)
            ocr_pages.append(page_ocr.summary(page_number))
            findings.extend(page_ocr.findings(page_number))
        except OCRError:
            ocr_succeeded = False
            ocr_pages.append({'page': page_number, 'failed': True, 'uncertain': True})
    if not ocr_succeeded:
        warnings_out.append('Local OCR failed or is unavailable on one or more pages; install Tesseract and configured language data. Upload remains blocked/unverified.')
    elif any(page['uncertain'] for page in ocr_pages):
        warnings_out.append('OCR found low-confidence words or no readable words; inspect those pages manually. OCR confidence does not measure privacy safety.')

    vision_attempted = vision_mode == 'always'
    vision_succeeded = False
    if vision_mode == 'off':
        warnings_out.append('Visual semantic analysis was disabled; upload remains blocked/unverified.')
    elif model is None:
        warnings_out.append('Local Gemma vision model is unavailable; upload remains blocked/unverified.')
    else:
        try:
            for page_number, page_png in enumerate(rendered_pages, start=1):
                findings.extend(_vision_metadata(item, page_number)
                                for item in model.detect_image(page_png, 'image/png'))
            vision_succeeded = True
        except LocalModelError:
            warnings_out.append('Local Gemma vision analysis failed or returned invalid output.')

    if vision_mode != 'always' or not vision_succeeded or not ocr_succeeded:
        status = 'BLOCKED_UNVERIFIED'
    elif findings or any(page['uncertain'] for page in ocr_pages):
        status = 'REVIEW_REQUIRED'
    else:
        status = 'READY_FOR_MANUAL_APPROVAL'
    if media_type == 'application/pdf' and not any(text_pages):
        warnings_out.append('No extractable PDF text layer was found; review relies on rendered-page vision.')
    return UploadReviewResult(
        media_type=media_type,
        page_count=len(rendered_pages),
        sanitized_text=sanitized_text,
        findings=combine_findings(findings),
        status=status,
        requires_human_review=True,
        ocr_succeeded=ocr_succeeded,
        ocr_pages=ocr_pages,
        vision_attempted=vision_attempted,
        vision_succeeded=vision_succeeded,
        warnings=warnings_out,
        preview_pages=[{
            'page': index,
            'image_data_url': 'data:image/png;base64,' + base64.b64encode(png).decode('ascii'),
        } for index, png in enumerate(rendered_pages, start=1)] if include_previews else [],
    )
