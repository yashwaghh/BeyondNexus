import unittest

from privacygate.detectors import Finding
from privacygate.pipeline import review_text
from privacygate.model import LocalModelError, validate_local_url


class FakeModel:
    def detect(self, text):
        begin = text.index('Aarav Kulkarni')
        return [Finding(begin, begin + len('Aarav Kulkarni'), 'PERSON', .55, 'gemma_local', 'test model')]


class BrokenModel:
    def detect(self, text):
        raise LocalModelError('model failed')


class PipelineTests(unittest.TestCase):
    def test_sanitization_keeps_task_values(self):
        res = review_text('My email is demo@example.org. Budget ₹2500.', mode='off')
        self.assertIn('[EMAIL_1]', res.sanitized_text)
        self.assertIn('₹2500', res.sanitized_text)
        self.assertNotIn('demo@example.org', res.sanitized_text)

    def test_hinted_name_calls_local_model(self):
        res = review_text('My name is Aarav Kulkarni', mode='on-uncertain', model=FakeModel())
        self.assertTrue(res.llm_attempted)
        self.assertTrue(res.llm_succeeded)
        self.assertIn('[PERSON_1]', res.sanitized_text)
        self.assertEqual(res.status, 'REVIEW_REQUIRED')

    def test_missing_model_blocks_hinted_text(self):
        res = review_text('My name is Aarav Kulkarni', mode='on-uncertain', model=None)
        self.assertEqual(res.status, 'BLOCKED_UNVERIFIED')

    def test_model_failure_blocks(self):
        res = review_text('My name is Aarav Kulkarni', model=BrokenModel())
        self.assertEqual(res.status, 'BLOCKED_UNVERIFIED')

    def test_unknown_phone_always_needs_review(self):
        res = review_text('9876543210', mode='off')
        self.assertEqual(res.status, 'REVIEW_REQUIRED')
        self.assertEqual(res.sanitized_text, '[PHONE_1]')

    def test_nonlocal_endpoint_rejected(self):
        for bad in ['https://api.example.com/v1', 'http://192.168.0.20:1234/v1',
                    'http://example.com:1234/v1', 'file:///tmp/model']:
            with self.assertRaises(ValueError):
                validate_local_url(bad)
        self.assertEqual(validate_local_url('http://127.0.0.1:1234/v1'), 'http://127.0.0.1:1234/v1')

    def test_no_raw_value_in_metadata(self):
        raw = 'privacytest@example.org'
        res = review_text(raw, mode='off')
        self.assertNotIn(raw, str(res.findings))

    def test_over_length_model_scan_blocks(self):
        res = review_text('My name is Aarav Kulkarni. ' + ('Hello ' * 220), model=FakeModel(), max_model_chars=200)
        self.assertEqual(res.status, 'BLOCKED_UNVERIFIED')


if __name__ == '__main__':
    unittest.main()
