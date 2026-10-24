import io
import unittest
from unittest.mock import patch

from PIL import Image

from privacygate.document_fields import detect_document_fields
from privacygate.ocr import parse_tsv
from privacygate.redaction import redact_export
from privacygate.uploads import review_upload
from privacygate.ocr import OCRPage
from scripts.document_samples import DOCUMENTS, render_document
from scripts.benchmark_documents import coverage


class DocumentFieldTests(unittest.TestCase):
    def test_common_document_fields_seed_masks_and_destroy_selected_pixels(self):
        for name in DOCUMENTS:
            with self.subTest(document=name):
                source, tsv, targets = render_document(name)
                findings = parse_tsv(tsv,1400,850).findings(1)
                self.assertTrue(all(value >= .98 for value in coverage(source,targets,findings)))
                if not targets:
                    self.assertEqual(findings, [])
                regions = [dict(page=1,box=f['region_0_1000']) for f in findings]
                output, _ = redact_export(source,'image/png',regions,'png',reviewed=True)
                with Image.open(io.BytesIO(output)) as result:
                    for f in findings:
                        t,l,b,r = f['region_0_1000']
                        center = (int((l+r)*result.width/2000),int((t+b)*result.height/2000))
                        self.assertEqual(result.getpixel(center),(0,0,0))
                self.assertNotIn('Demo Sample',str(findings))

    def test_next_line_values_and_indented_address(self):
        text = 'Passport number\nZ1234567\nAddress:\n17 Example Lane\n  Sample City\n  State 400001\nInvoice date: 25/10/2026'
        findings = detect_document_fields(text)
        self.assertEqual([f.entity for f in findings], ['POSSIBLE_ID','ADDRESS'])
        address = text[findings[1].start:findings[1].end]
        self.assertIn('State 400001',address)
        self.assertNotIn('Invoice date',address)

    def test_labels_do_not_match_word_prefixes_or_swallow_empty_fields(self):
        text = 'Nameplate: Example\nAccountability: 12345\nPassport number:\nName: Demo Sample\nTotal amount: 1200'
        findings = detect_document_fields(text)
        self.assertEqual([f.entity for f in findings], ['PERSON'])
        self.assertEqual(text[findings[0].start:findings[0].end],'Demo Sample')

    def test_dates_and_amounts_without_personal_labels_remain(self):
        self.assertEqual(detect_document_fields('Invoice date: 25/10/2026\nTotal amount: 1200\nRoom: 42'),[])

    def test_unlabelled_card_and_machine_readable_line(self):
        text = '4111 1111 1111 1111\nP<ZZZDEMO<<SAMPLE<<<<<<<<<<<<<<<<<<<<<<<<<<<'
        findings = detect_document_fields(text)
        self.assertEqual(len(findings),2)
        self.assertTrue(all(f.entity == 'POSSIBLE_ID' for f in findings))
        self.assertEqual(detect_document_fields('0000000000000000\n4111111111111112'),[])
        self.assertEqual(detect_document_fields('Fullname: Demo Sample')[0].entity,'PERSON')
        spaced = 'P<ZZZDEMO<<SAMPLE <<<<<<<<<<<<<<<<<<<<<<<<<<<'
        self.assertEqual(detect_document_fields(spaced)[0].entity,'POSSIBLE_ID')

    def test_multiple_sensitive_fields_inline_are_conservatively_covered(self):
        text = 'Name: Demo Sample DOB: 01/02/1990'
        findings = detect_document_fields(text)
        self.assertEqual(text[findings[0].start:findings[0].end], 'Demo Sample DOB: 01/02/1990')

    def test_hidden_pdf_labelled_fields_are_reported_without_inventing_boxes(self):
        from test_uploads import make_text_pdf
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import DecodedStreamObject, NameObject
        reader = PdfReader(io.BytesIO(make_text_pdf()))
        writer = PdfWriter(); writer.add_page(reader.pages[0])
        stream = DecodedStreamObject()
        stream.set_data(b'BT /F1 12 Tf 20 100 Td (Passport number: Z1234567) Tj ET')
        writer.pages[0][NameObject('/Contents')] = writer._add_object(stream)
        source = io.BytesIO(); writer.write(source)
        class Vision:
            def detect_image(self, *_args):
                return []
        with patch('privacygate.uploads.TesseractOCR') as engine:
            engine.return_value.recognize.return_value = OCRPage('',[],300,200)
            result = review_upload(source.getvalue(),'application/pdf',model=Vision())
        self.assertNotIn('Z1234567',result.sanitized_text)
        field = next(f for f in result.findings if f['entity'] == 'POSSIBLE_ID')
        self.assertIsNone(field['region_0_1000'])


if __name__ == '__main__':
    unittest.main()
