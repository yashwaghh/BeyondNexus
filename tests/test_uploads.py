import io
import unittest

from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from privacygate.model import LocalModelError, VisionFinding
from privacygate.uploads import UploadReviewError, review_upload


def make_png() -> bytes:
    output = io.BytesIO()
    Image.new('RGB', (96, 64), 'white').save(output, format='PNG')
    return output.getvalue()


def make_pdf(page_count: int = 1) -> bytes:
    output = io.BytesIO()
    writer = PdfWriter()
    for _ in range(page_count):
        writer.add_blank_page(width=300, height=200)
    writer.write(output)
    return output.getvalue()


def make_text_pdf() -> bytes:
    output = io.BytesIO()
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=200)
    font = DictionaryObject({
        NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'),
        NameObject('/BaseFont'): NameObject('/Helvetica'),
    })
    page[NameObject('/Resources')] = DictionaryObject({
        NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)}),
    })
    stream = DecodedStreamObject()
    stream.set_data(b'BT /F1 12 Tf 20 100 Td (Email demo@example.org) Tj ET')
    page[NameObject('/Contents')] = writer._add_object(stream)
    writer.write(output)
    return output.getvalue()


def make_metadata_pdf() -> bytes:
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=200)
    writer.add_metadata({'/Author': 'Synthetic Person', '/Title': 'Synthetic private title'})
    writer.write(output)
    return output.getvalue()


class FakeVision:
    def detect_image(self, image_bytes, media_type):
        self.last_type = media_type
        self.last_bytes = image_bytes
        return [VisionFinding('PERSON', .55, 'gemma_vision', 'synthetic test', (10, 20, 200, 300))]


class BrokenVision:
    def detect_image(self, image_bytes, media_type):
        raise LocalModelError('synthetic failure')


class UploadReviewTests(unittest.TestCase):
    def test_image_is_normalized_and_flagged_for_review(self):
        model = FakeVision()
        result = review_upload(make_png(), 'image/png', model=model)
        self.assertEqual(result.status, 'REVIEW_REQUIRED')
        self.assertTrue(result.vision_succeeded)
        self.assertEqual(result.findings[0]['region_0_1000'], [10, 20, 200, 300])
        self.assertEqual(model.last_type, 'image/png')
        self.assertTrue(model.last_bytes.startswith(b'\x89PNG'))
        self.assertIsNone(result.sanitized_text)
        self.assertFalse(result.export_available)

    def test_pdf_is_rendered_in_memory_page_by_page(self):
        model = FakeVision()
        result = review_upload(make_pdf(2), 'application/pdf', model=model)
        self.assertEqual(result.page_count, 2)
        self.assertEqual(len(result.findings), 2)
        self.assertIn('no extractable text layer', result.sanitized_text)
        self.assertTrue(any('rendered-page vision' in warning for warning in result.warnings))

    def test_pdf_text_layer_is_scanned_and_sanitized(self):
        result = review_upload(make_text_pdf(), 'application/pdf', model=FakeVision())
        self.assertIn('[EMAIL_1]', result.sanitized_text)
        self.assertNotIn('demo@example.org', result.sanitized_text)
        self.assertIn('EMAIL', {finding['entity'] for finding in result.findings})

    def test_pdf_metadata_is_flagged_without_exposing_values(self):
        result = review_upload(make_metadata_pdf(), 'application/pdf', model=FakeVision())
        self.assertIn('pdf_metadata', {finding['source'] for finding in result.findings})
        self.assertNotIn('Synthetic Person', str(result.findings))
        self.assertNotIn('Synthetic private title', str(result.findings))

    def test_pdf_attachment_is_flagged_as_unscanned(self):
        output = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=200)
        writer.add_attachment('synthetic.txt', b'fabricated attachment')
        writer.write(output)
        result = review_upload(output.getvalue(), 'application/pdf', model=FakeVision())
        self.assertIn('pdf_structure', {finding['source'] for finding in result.findings})
        self.assertTrue(any('embedded files' in warning for warning in result.warnings))

    def test_encrypted_pdf_is_rejected(self):
        output = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=200)
        writer.encrypt('synthetic-password')
        writer.write(output)
        with self.assertRaises(UploadReviewError):
            review_upload(output.getvalue(), 'application/pdf', model=FakeVision())

    def test_required_vision_failure_blocks(self):
        result = review_upload(make_png(), 'image/png', model=BrokenVision())
        self.assertEqual(result.status, 'BLOCKED_UNVERIFIED')
        self.assertFalse(result.vision_succeeded)

    def test_disabled_vision_blocks(self):
        result = review_upload(make_png(), 'image/png', vision_mode='off')
        self.assertEqual(result.status, 'BLOCKED_UNVERIFIED')
        self.assertFalse(result.vision_attempted)

    def test_pdf_page_limit_is_enforced(self):
        with self.assertRaises(UploadReviewError):
            review_upload(make_pdf(6), 'application/pdf', model=FakeVision())

    def test_declared_type_and_content_must_match(self):
        with self.assertRaises(UploadReviewError):
            review_upload(make_png(), 'application/pdf', model=FakeVision())

    def test_invalid_image_is_rejected(self):
        with self.assertRaises(UploadReviewError):
            review_upload(b'not-an-image', 'image/png', model=FakeVision())

    def test_upload_byte_limit_is_enforced_before_parsing(self):
        with self.assertRaises(UploadReviewError):
            review_upload(b'x' * (6 * 1024 * 1024 + 1), 'image/png', model=FakeVision())


if __name__ == '__main__':
    unittest.main()
