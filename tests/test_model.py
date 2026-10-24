import unittest
from privacygate.model import GemmaLocalClient, LocalModelError


class MockGemma(GemmaLocalClient):
    def __init__(self, content):
        super().__init__('http://127.0.0.1:1234/v1', model_id='fake-local-gemma')
        self.content = content
        self.called = False

    def _request(self, method, path, payload=None):
        self.called = True
        self.last_payload = payload
        return {'choices': [{'message': {'content': self.content}}]}


class ModelTests(unittest.TestCase):
    def test_invalid_completion_envelope_fails_closed(self):
        for response in [{'choices': []}, {'choices': [None]}, {'choices': ['invalid']}]:
            with self.assertRaises(LocalModelError):
                GemmaLocalClient._completion_json(response)

    def test_reported_truncation_is_not_repaired_or_cleared(self):
        for content in ['{"entities":[]', '{"entities":[]}']:
            with self.assertRaises(LocalModelError):
                GemmaLocalClient._completion_json({'choices': [{
                    'finish_reason': 'length', 'message': {'content': content}}]})

    def test_stopped_fenced_output_with_missing_outer_brace_can_be_recovered(self):
        response = {'choices': [{'finish_reason': 'stop', 'message': {
            'content': '```json\n{"entities":[{"entity_type":"PERSON","box_2d":[10,20,100,200]}]\n```'}}]}
        parsed = GemmaLocalClient._completion_json(response)
        self.assertEqual(parsed['entities'][0]['entity_type'], 'PERSON')

    def test_exact_span_accepted(self):
        m = MockGemma('{"entities":[{"text":"Aarav Kulkarni","entity_type":"PERSON"}]}')
        rows = m.detect('My name is Aarav Kulkarni')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].entity, 'PERSON')
        self.assertEqual(rows[0].start, 11)

    def test_unknown_span_fails_closed(self):
        m = MockGemma('{"entities":[{"text":"A name not in input","entity_type":"PERSON"}]}')
        with self.assertRaises(LocalModelError):
            m.detect('No personal information mentioned')

    def test_invalid_json_fails_closed(self):
        m = MockGemma('Here is my answer: {bad_json}')
        with self.assertRaises(LocalModelError):
            m.detect('My name is Aarav Kulkarni')

    def test_no_entities_is_valid(self):
        m = MockGemma('{"entities":[]}')
        self.assertEqual(m.detect('No PII here.'), [])

    def test_vision_finding_accepts_normalized_region_without_raw_value(self):
        m = MockGemma('{"entities":[{"entity_type":"PERSON","box_2d":[10,20,300,400]}]}')
        rows = m.detect_image(b'png-bytes', 'image/png')
        self.assertEqual(rows[0].entity, 'PERSON')
        self.assertEqual(rows[0].region, (10, 20, 300, 400))
        self.assertIn('data:image/png;base64,', str(m.last_payload))
        self.assertNotIn('Aarav', str(rows))

    def test_vision_invalid_region_fails_closed(self):
        m = MockGemma('{"entities":[{"entity_type":"PERSON","box_2d":[500,20,10,400]}]}')
        with self.assertRaises(LocalModelError):
            m.detect_image(b'png-bytes', 'image/png')


if __name__ == '__main__':
    unittest.main()
