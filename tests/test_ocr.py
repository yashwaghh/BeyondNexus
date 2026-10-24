import io
import unittest
from unittest.mock import patch

from PIL import Image

from privacygate.ocr import OCRError, OCRPage, TesseractOCR, parse_tsv
from privacygate.uploads import review_upload, combine_findings


HEADER = 'level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n'


def page(confidence=96):
    return parse_tsv(HEADER + f'5\t1\t1\t1\t1\t1\t100\t50\t400\t50\t{confidence}\tdemo@example.org\n', 1000, 500)


def png():
    output = io.BytesIO()
    Image.new('RGB', (1000, 500), 'white').save(output, format='PNG')
    return output.getvalue()


class Vision:
    calls = 0

    def detect_image(self, *_args):
        self.calls += 1
        return []


class OCR:
    def __init__(self, result=None, fail=False):
        self.result, self.fail = result, fail

    def recognize(self, _png):
        if self.fail:
            raise OCRError('synthetic failure')
        return self.result


class OCRTests(unittest.TestCase):
    def test_rule_box_and_confidence_have_separate_meanings(self):
        finding = page(42).findings(1)[0]
        self.assertEqual(finding['entity'], 'EMAIL')
        self.assertEqual(finding['region_0_1000'], [100, 100, 200, 500])
        self.assertEqual(finding['ocr_confidence'], 42)
        self.assertGreater(finding['score_heuristic'], .9)
        self.assertTrue(page(42).summary(1)['uncertain'])

    def test_invalid_word_geometry_and_nonfinite_confidence_rejected(self):
        for confidence in ('nan', 'inf', '-1', '101'):
            with self.assertRaises(OCRError):
                page(confidence)
        with self.assertRaises(OCRError):
            parse_tsv(HEADER + '5\t1\t1\t1\t1\t1\t999\t0\t50\t50\t95\tx\n', 1000, 500)

    def test_ocr_catches_email_when_vision_misses_and_never_returns_transcript(self):
        vision = Vision()
        result = review_upload(png(), 'image/png', model=vision, ocr=OCR(page()))
        self.assertEqual(result.status, 'REVIEW_REQUIRED')
        self.assertEqual(result.findings[0]['entity'], 'EMAIL')
        self.assertEqual(vision.calls, 1)
        self.assertNotIn('demo@example.org', str(result.to_dict()))

    def test_ocr_failure_blocks_even_if_vision_succeeds(self):
        result = review_upload(png(), 'image/png', model=Vision(), ocr=OCR(fail=True))
        self.assertEqual(result.status, 'BLOCKED_UNVERIFIED')
        self.assertTrue(result.vision_succeeded)
        self.assertFalse(result.ocr_succeeded)

    def test_blank_page_requires_review_not_clearance(self):
        result = review_upload(png(), 'image/png', model=Vision(),
                               ocr=OCR(OCRPage('', [], 1000, 500)))
        self.assertEqual(result.status, 'REVIEW_REQUIRED')

    def test_high_ocr_confidence_still_runs_vision(self):
        vision = Vision()
        review_upload(png(), 'image/png', model=vision, ocr=OCR(page(99)))
        self.assertEqual(vision.calls, 1)

    def test_missing_executable_has_private_generic_failure(self):
        with self.assertRaises(OCRError):
            TesseractOCR(executable='privacygate-nonexistent-ocr').recognize(png())

    def test_cli_uses_stdin_no_shell_and_timeout(self):
        with patch('privacygate.ocr.subprocess.run') as run:
            run.return_value.stdout = HEADER.encode()
            TesseractOCR().recognize(png())
            args, kwargs = run.call_args
            self.assertEqual(args[0][1:3], ['stdin', 'stdout'])
            self.assertEqual(kwargs['timeout'], 30)
            self.assertNotIn('shell', kwargs)

    def test_invalid_language_option_rejected(self):
        with self.assertRaises(ValueError):
            TesseractOCR(languages='eng --psm 0')

    def test_same_entity_agreement_combines_but_conflict_survives(self):
        original = page().findings(1)[0]
        vision = dict(original, source='gemma_vision')
        conflict = dict(vision, entity='PHONE')
        findings = combine_findings([original, vision, conflict])
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0]['evidence_sources'], [original['source'], 'gemma_vision'])
        self.assertEqual(findings[1]['entity'], 'PHONE')

    def test_pdf_partial_ocr_failure_keeps_earlier_findings_and_checks_all_vision_pages(self):
        from test_uploads import make_pdf
        with patch.object(OCR, 'recognize', side_effect=[page(), OCRError('failed')]):
            vision = Vision()
            result = review_upload(make_pdf(2), 'application/pdf', model=vision, ocr=OCR())
        self.assertEqual(result.status, 'BLOCKED_UNVERIFIED')
        self.assertEqual(vision.calls, 2)
        self.assertEqual(result.findings[0]['page'], 1)
        self.assertTrue(result.ocr_pages[1]['failed'])

    def test_word_spacing_and_newlines_preserve_rule_offsets(self):
        tsv = HEADER + '5\t1\t1\t1\t1\t1\t10\t10\t80\t20\t95\tEmail:\n'
        tsv += '5\t1\t1\t1\t1\t2\t100\t10\t350\t20\t90\tdemo@example.org\n'
        tsv += '5\t1\t1\t1\t2\t1\t10\t50\t80\t20\t95\tMeeting\n'
        result = parse_tsv(tsv, 1000, 500)
        self.assertEqual(result.text, 'Email: demo@example.org\nMeeting')
        self.assertEqual(result.findings(1)[0]['region_0_1000'], [20, 100, 60, 450])

    def test_benchmark_penalizes_wrong_location_and_duplicate_predictions(self):
        from scripts.benchmark_uploads import score
        expected = [('EMAIL', [10, 10, 100, 100])]
        found = [{'entity': 'EMAIL', 'region_0_1000': [500, 500, 600, 600]}]
        self.assertEqual(score(expected, found)['fn'], 1)
        found = [{'entity': 'EMAIL', 'region_0_1000': [10, 10, 100, 100]}] * 2
        self.assertEqual(score(expected, found)['fp'], 1)


if __name__ == '__main__':
    unittest.main()
