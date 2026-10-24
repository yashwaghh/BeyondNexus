import base64
import io
import json
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler

from PIL import Image, PngImagePlugin
from pypdf import PdfReader, PdfWriter

from privacygate.ocr import OCRPage
from privacygate.redaction import redact_export
from privacygate.uploads import UploadReviewError
from privacygate.web import create_server
from privacygate.uploads import _render_pdf_pages
from test_uploads import make_text_pdf, make_metadata_pdf, make_pdf, FakeVision


def source_png():
    output = io.BytesIO()
    info = PngImagePlugin.PngInfo()
    info.add_text('private', 'synthetic hidden identifier')
    Image.new('RGB', (100, 80), (231, 187, 91)).save(output, format='PNG', pnginfo=info)
    return output.getvalue()


class RedactionTests(unittest.TestCase):
    def test_png_pixels_replaced_with_padding_and_metadata_removed(self):
        data, kind = redact_export(source_png(), 'image/png',
                                   [{'page': 1, 'box': [250, 200, 750, 800]}], 'png', reviewed=True)
        self.assertEqual(kind, 'image/png')
        with Image.open(io.BytesIO(data)) as image:
            self.assertEqual(image.getpixel((50, 40)), (0, 0, 0))
            self.assertEqual(image.getpixel((18, 18)), (0, 0, 0))
            self.assertEqual(image.getpixel((5, 5)), (231, 187, 91))
            self.assertFalse(image.info)
        self.assertNotIn(b'synthetic hidden identifier', data)

    def test_pdf_is_lossless_raster_without_original_text_or_objects(self):
        data, kind = redact_export(make_text_pdf(), 'application/pdf',
                                   [{'page': 1, 'box': [0, 0, 1000, 1000]}], 'pdf', reviewed=True)
        reader = PdfReader(io.BytesIO(data))
        self.assertEqual(kind, 'application/pdf')
        self.assertEqual(reader.pages[0].extract_text(), '')
        self.assertIsNone(reader.metadata)
        self.assertFalse(reader.get_fields())
        self.assertNotIn('/Names', reader.trailer['/Root'])
        self.assertNotIn('/Annots', reader.pages[0])
        self.assertNotIn(b'demo@example.org', data)
        image = next(iter(reader.pages[0]['/Resources']['/XObject'].values())).get_object()
        self.assertEqual(set(image.get_data()), {0})
        self.assertEqual(image['/Filter'], '/FlateDecode')
        self.assertEqual(float(reader.pages[0].mediabox.width), 300)
        self.assertEqual(float(reader.pages[0].mediabox.height), 200)

    def test_embedded_attachment_is_not_copied(self):
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=200)
        writer.add_attachment('private.txt', b'synthetic attachment secret')
        source = io.BytesIO(); writer.write(source)
        exported, _ = redact_export(source.getvalue(), 'application/pdf', [], 'pdf', reviewed=True)
        reader = PdfReader(io.BytesIO(exported))
        self.assertNotIn('/Names', reader.trailer['/Root'])
        self.assertNotIn(b'synthetic attachment secret', exported)

    def test_metadata_pdf_rebuilt_and_page_count_preserved(self):
        for original in [make_metadata_pdf(), make_pdf(2)]:
            data, _ = redact_export(original, 'application/pdf', [], 'pdf', reviewed=True)
            reader = PdfReader(io.BytesIO(data))
            self.assertIsNone(reader.metadata)
            self.assertEqual(len(reader.pages), len(PdfReader(io.BytesIO(original)).pages))

    def test_invalid_regions_and_missing_review_fail_closed(self):
        invalid = [{'page': 2, 'box': [0, 0, 100, 100]},
                   {'page': True, 'box': [0, 0, 100, 100]},
                   {'page': 1, 'box': [0, 0, 1001, 100]},
                   {'page': 1, 'box': [10, 10, 0, 0]},
                   {'page': 1, 'box': [0, 0, 100.5, 100]}, 'wrong']
        for region in invalid:
            with self.assertRaises(UploadReviewError):
                redact_export(source_png(), 'image/png', [region], 'png', reviewed=True)
        for reviewed in [False, 'true', 1, None]:
            with self.assertRaises(UploadReviewError):
                redact_export(source_png(), 'image/png', [], 'png', reviewed=reviewed)
        with self.assertRaises(UploadReviewError):
            redact_export(make_pdf(2), 'application/pdf', [], 'png', reviewed=True)
        for output_format in [[], {}, None, True, 'jpeg']:
            with self.assertRaises(UploadReviewError):
                redact_export(source_png(), 'image/png', [], output_format, reviewed=True)

    def test_rotated_cropped_pdf_preview_and_export_align(self):
        from pypdf.generic import RectangleObject
        original, _ = redact_export(source_png(), 'image/png', [], 'pdf', reviewed=True)
        writer = PdfWriter(io.BytesIO(original))
        writer.pages[0].rotate(90)
        writer.pages[0].cropbox = RectangleObject([10, 10, 90, 70])
        buffer = io.BytesIO(); writer.write(buffer)
        source = buffer.getvalue()
        exported, _ = redact_export(source, 'application/pdf',
                                    [{'page': 1, 'box': [250, 250, 750, 750]}], 'pdf', reviewed=True)
        before = Image.open(io.BytesIO(_render_pdf_pages(source)[0]))
        after = Image.open(io.BytesIO(_render_pdf_pages(exported)[0]))
        self.assertEqual(before.size, after.size)
        self.assertEqual(before.getpixel((0, 0)), after.getpixel((0, 0)))
        self.assertEqual(after.getpixel((after.width//2, after.height//2)), (0, 0, 0))

    def test_jpeg_exif_orientation_masks_normalized_pixels(self):
        image = Image.new('RGB', (100, 80), 'red')
        exif = Image.Exif(); exif[274] = 6
        source = io.BytesIO(); image.save(source, format='JPEG', exif=exif)
        exported, _ = redact_export(source.getvalue(), 'image/jpeg',
                                    [{'page': 1, 'box': [0, 0, 500, 1000]}], 'png', reviewed=True)
        with Image.open(io.BytesIO(exported)) as result:
            self.assertEqual(result.size, (80, 100))
            self.assertEqual(result.getpixel((40, 20)), (0, 0, 0))
            self.assertGreater(result.getpixel((40, 80))[0], 240)
            self.assertFalse(result.getexif())

    def test_pdfium_entry_points_are_serialized_across_threads(self):
        import time
        from concurrent.futures import ThreadPoolExecutor
        active = 0
        maximum = 0
        guard = threading.Lock()
        barrier = threading.Barrier(2)
        def native(_data, with_sizes):
            nonlocal active, maximum
            with guard:
                active += 1; maximum = max(maximum, active)
            time.sleep(.03)
            with guard:
                active -= 1
            return ([b'page'], [(100, 100)]) if with_sizes else [b'page']
        def render(with_sizes):
            barrier.wait(timeout=2)
            return _render_pdf_pages(b'synthetic', with_sizes=with_sizes)
        with patch('privacygate.uploads._render_pdf_unlocked', side_effect=native):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first, second = pool.submit(render, False), pool.submit(render, True)
                self.assertEqual(first.result(), [b'page'])
                self.assertEqual(second.result(), ([b'page'], [(100, 100)]))
        self.assertEqual(maximum, 1)


class ExportBridgeTests(unittest.TestCase):
    def setUp(self):
        self.server = create_server(port=0, token='synthetic-export-token-1234567890', model=FakeVision())
        self.origin = self.server.local_origin
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.opener = build_opener(ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(2)

    def request(self, path, payload, token=None):
        request = Request(self.origin + path, data=json.dumps(payload).encode(), method='POST',
                          headers={'Origin': self.origin, 'Content-Type': 'application/json',
                                   'Authorization': 'Bearer '+(token or self.server.token)})
        return self.opener.open(request, timeout=3)

    def scan(self):
        payload = {'data_base64': base64.b64encode(source_png()).decode(), 'media_type': 'image/png'}
        with patch('privacygate.uploads.TesseractOCR') as mock:
            mock.return_value.recognize.return_value = OCRPage('', [], 100, 80)
            with self.request('/v1/scan-file', payload) as response:
                result = json.load(response)
        return dict(payload, export_ticket=result['export_ticket'], reviewed=True,
                    regions=[{'page': 1, 'box': [0, 0, 1000, 1000]}], output_format='png')

    def test_ticket_export_auth_and_binary_headers(self):
        payload = self.scan()
        with self.request('/v1/redact-export', payload) as response:
            self.assertEqual(response.headers['Content-Type'], 'image/png')
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            with Image.open(io.BytesIO(response.read())) as image:
                self.assertEqual(image.getpixel((50, 40)), (0, 0, 0))
        with self.assertRaises(HTTPError) as error:
            self.request('/v1/redact-export', payload, token='wrong')
        self.assertEqual(error.exception.code, 401)

    def test_changed_upload_tampered_expired_and_missing_tickets_rejected(self):
        payload = self.scan()
        variants = [dict(payload, export_ticket=''), dict(payload, export_ticket='0.bad'),
                    dict(payload, export_ticket='1234567890.'+'\u00e9'*64),
                    dict(payload, export_ticket=payload['export_ticket']+'x'),
                    dict(payload, data_base64=base64.b64encode(source_png()+b'changed').decode())]
        for invalid in variants:
            with self.assertRaises(HTTPError) as error:
                self.request('/v1/redact-export', invalid)
            self.assertEqual(error.exception.code, 400)

    def test_blocked_scans_do_not_authorize_export(self):
        self.server.model = None
        with self.request('/v1/scan-file', {'data_base64': base64.b64encode(source_png()).decode(),
                                           'media_type': 'image/png'}) as response:
            self.assertNotIn('export_ticket', json.load(response))

    def test_genuine_expired_ticket_is_rejected(self):
        import time
        payload = self.scan()
        future = time.time()+1000
        with patch('privacygate.web.time.time', return_value=future):
            with self.assertRaises(HTTPError) as error:
                self.request('/v1/redact-export', payload)
        self.assertEqual(error.exception.code, 400)

    def test_malformed_options_return_400_and_server_remains_usable(self):
        payload = self.scan()
        for output_format in [[], {}, None, True, 'jpeg']:
            with self.assertRaises(HTTPError) as error:
                self.request('/v1/redact-export', dict(payload, output_format=output_format))
            self.assertEqual(error.exception.code, 400)
        with self.request('/v1/redact-export', payload) as response:
            self.assertEqual(response.status, 200)

    def test_non_ascii_auth_header_is_rejected_without_connection_crash(self):
        with self.assertRaises(HTTPError) as error:
            self.request('/v1/redact-export', {}, token='\u00e9')
        self.assertEqual(error.exception.code, 401)

    def test_bridge_restart_invalidates_previous_export_ticket(self):
        import secrets
        payload = self.scan()
        self.server.export_secret = secrets.token_bytes(32)
        with self.assertRaises(HTTPError) as error:
            self.request('/v1/redact-export', payload)
        self.assertEqual(error.exception.code, 400)


if __name__ == '__main__':
    unittest.main()
