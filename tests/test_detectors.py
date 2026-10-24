import unittest

from privacygate.detectors import detect_rules, verhoeff_valid, _D, _P


def make_valid_aadhaar(prefix: str = '23456789012') -> str:
    # Synthetic test-only check digit, not a real/person-assigned identity claim.
    for digit in '0123456789':
        candidate = prefix + digit
        if verhoeff_valid(candidate):
            return candidate
    raise RuntimeError('No Verhoeff check digit found')


class RuleTests(unittest.TestCase):
    def test_email_pan_phone(self):
        text = 'Contact demo@example.org, PAN ABCDE1234F, mobile +91 9876543210.'
        kinds = {f.entity for f in detect_rules(text)}
        self.assertEqual(kinds, {'EMAIL', 'PAN', 'PHONE'})

    def test_avoid_phone_inside_longer_numeric(self):
        self.assertFalse(any(f.entity == 'PHONE' for f in detect_rules('Ref 1234567890123456789')))

    def test_plain_phone_needs_review(self):
        candidates = detect_rules('9876543210')
        self.assertEqual(candidates[0].entity, 'PHONE')
        self.assertLess(candidates[0].confidence, .90)

    def test_valid_aadhaar_checksum(self):
        value = make_valid_aadhaar()
        self.assertTrue(verhoeff_valid(value))
        entities = {f.entity for f in detect_rules('Aadhaar: ' + value)}
        self.assertIn('AADHAAR', entities)

    def test_invalid_labelled_aadhaar_is_review_candidate(self):
        value = make_valid_aadhaar()
        bad = value[:-1] + str((int(value[-1]) + 1) % 10)
        self.assertIn('POSSIBLE_ID', {f.entity for f in detect_rules('Aadhaar: ' + bad)})

    def test_account_without_label_not_asserted(self):
        self.assertNotIn('BANK_ACCOUNT', {f.entity for f in detect_rules('Reference 23456789012345')})
        self.assertIn('BANK_ACCOUNT', {f.entity for f in detect_rules('account number: 23456789012345')})


if __name__ == '__main__':
    unittest.main()
