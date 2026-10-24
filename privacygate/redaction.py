"""Destructive raster masking and fresh, image-only exports. No source objects copied."""
from __future__ import annotations

import io
import math

from PIL import Image, ImageDraw
import pypdfium2 as pdfium
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

from .uploads import (_normalized_png, _render_pdf_pages, _pdf_text_pages,
                      MAX_UPLOAD_BYTES, SUPPORTED_IMAGE_TYPES, UploadReviewError)


def redact_export(data: bytes, media_type: str, regions: list, output_format: str,
                  *, reviewed: bool) -> tuple[bytes, str]:
    if reviewed is not True or not data or len(data) > MAX_UPLOAD_BYTES:
        raise UploadReviewError('Review and bounded source upload required.')
    if output_format not in {'png', 'pdf'} or not isinstance(regions, list) or len(regions) > 500:
        raise UploadReviewError('Invalid redaction export options.')
    if media_type == 'application/pdf':
        _pdf_text_pages(data)  # Same structure/page/encryption limits as inspection.
        pages = _render_pdf_pages(data)
        document = pdfium.PdfDocument(data)
        try:
            sizes = []
            for index in range(len(document)):
                page = document[index]
                try:
                    sizes.append(page.get_size())
                finally:
                    page.close()
        finally:
            document.close()
    elif media_type in SUPPORTED_IMAGE_TYPES:
        pages = [_normalized_png(data)]
        sizes = None
    else:
        raise UploadReviewError('Unsupported export source.')
    if output_format == 'png' and len(pages) != 1:
        raise UploadReviewError('Multi-page sources require PDF export.')
    masks = {page: [] for page in range(1, len(pages)+1)}
    for region in regions:
        if not isinstance(region, dict):
            raise UploadReviewError('Invalid redaction region.')
        page, box = region.get('page'), region.get('box')
        if (type(page) is not int or page not in masks or not isinstance(box, list) or len(box) != 4
                or any(type(v) is not int or not 0 <= v <= 1000 for v in box)
                or box[0] >= box[2] or box[1] >= box[3]):
            raise UploadReviewError('Invalid redaction geometry.')
        masks[page].append(box)
    images = []
    for index, png in enumerate(pages, 1):
        with Image.open(io.BytesIO(png)) as source:
            # Fresh RGB buffer discards ancillary image metadata and source pixels under masks.
            image = Image.new('RGB', source.size, 'white')
            image.paste(source.convert('RGB'))
        draw = ImageDraw.Draw(image)
        for top, left, bottom, right in masks[index]:
            x0, y0 = max(0, math.floor(left*image.width/1000)-2), max(0, math.floor(top*image.height/1000)-2)
            x1, y1 = min(image.width, math.ceil(right*image.width/1000)+2), min(image.height, math.ceil(bottom*image.height/1000)+2)
            draw.rectangle((x0, y0, x1-1, y1-1), fill='black')
        images.append(image)
    if output_format == 'png':
        output = io.BytesIO()
        images[0].save(output, format='PNG')
        return output.getvalue(), 'image/png'

    # Lossless Flate raster streams, no JPEG ringing or recoverable overlay/source stream.
    writer = PdfWriter()
    for index, image in enumerate(images):
        width, height = image.size
        page_width, page_height = sizes[index] if sizes else (width, height)
        page = writer.add_blank_page(width=page_width, height=page_height)
        raster = DecodedStreamObject()
        raster.set_data(image.tobytes())
        raster.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Image'),
                       NameObject('/Width'): NumberObject(width), NameObject('/Height'): NumberObject(height),
                       NameObject('/ColorSpace'): NameObject('/DeviceRGB'), NameObject('/BitsPerComponent'): NumberObject(8)})
        reference = writer._add_object(raster.flate_encode())
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/XObject'): DictionaryObject({NameObject('/Im0'): reference})})
        content = DecodedStreamObject()
        content.set_data(f'q {page_width} 0 0 {page_height} 0 0 cm /Im0 Do Q'.encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(content)
    writer.metadata = None
    output = io.BytesIO()
    writer.write(output)
    # Independent logical check before releasing bytes.
    exported = output.getvalue()
    check = PdfReader(io.BytesIO(exported))
    if any(page.extract_text() for page in check.pages) or check.get_fields():
        raise UploadReviewError('Raster export verification failed.')
    return exported, 'application/pdf'
