import unittest
from privacygate.model import GemmaLocalClient, LocalModelError


class MockGemma(GemmaLocalClient):
    def __init__(self, content):
        super().__init__('http://127.0.0.1:1234/v1', model_id='fake-local-gemma')
        self.content = content
        self.called = False

    def _request(self, method, path, payload=None):
        self.called = True
        return {'choices': [{'message': {'content': self.content}}]}


class ModelTests(unittest.TestCase):
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


if __name__ == '__main__':
    unittest.main()
