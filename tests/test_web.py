import json
import base64
import io
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler

from privacygate.web import create_server
from PIL import Image


class WebBridgeTests(unittest.TestCase):
    TOKEN = "synthetic-test-token-1234567890"
    EXTENSION_ORIGIN = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"

    @classmethod
    def setUpClass(cls):
        cls.server = create_server(port=0, token=cls.TOKEN,
                                   extension_origin=cls.EXTENSION_ORIGIN)
        cls.origin = cls.server.local_origin
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.opener = build_opener(ProxyHandler({}))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request(self, payload, *, token=TOKEN, origin=None):
        request = Request(
            self.origin + "/v1/scan",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "Origin": origin or self.origin,
            },
            method="POST",
        )
        with self.opener.open(request, timeout=3) as response:
            return response.status, json.load(response), response.headers

    def request_file(self, payload, *, token=TOKEN, origin=None):
        request = Request(
            self.origin + "/v1/scan-file",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
                "Origin": origin or self.origin,
            },
            method="POST",
        )
        with self.opener.open(request, timeout=3) as response:
            return response.status, json.load(response)

    def test_rules_only_scan_masks_without_echoing_metadata(self):
        status, body, _ = self.request({"text": "Email demo@example.org", "mode": "off"})
        self.assertEqual(status, 200)
        self.assertEqual(body["sanitized_text"], "Email [EMAIL_1]")
        self.assertNotIn("demo@example.org", str(body["findings"]))

    def test_missing_or_bad_token_rejected(self):
        with self.assertRaises(HTTPError) as caught:
            self.request({"text": "Hello", "mode": "off"}, token="wrong")
        self.assertEqual(caught.exception.code, 401)

    def test_unapproved_origin_rejected(self):
        with self.assertRaises(HTTPError) as caught:
            self.request({"text": "Hello", "mode": "off"}, origin="https://example.com")
        self.assertEqual(caught.exception.code, 403)

    def test_exact_extension_origin_allowed_with_cors(self):
        origin = self.EXTENSION_ORIGIN
        status, _, headers = self.request({"text": "Hello", "mode": "off"}, origin=origin)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Access-Control-Allow-Origin"], origin)

    def test_invalid_mode_is_generic_bad_request(self):
        with self.assertRaises(HTTPError) as caught:
            self.request({"text": "Hello", "mode": "invalid"})
        self.assertEqual(caught.exception.code, 400)

    def test_ui_is_served_with_no_store(self):
        with self.opener.open(self.origin + "/", timeout=3) as response:
            html = response.read().decode("utf-8")
            self.assertIn("PrivacyGate Local Review", html)
            self.assertIn('id="upload"', html)
            self.assertIn('id="scan-file"', html)
            self.assertNotIn("__PRIVACYGATE_TOKEN__", html)
            self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_non_loopback_bind_is_rejected(self):
        with self.assertRaises(ValueError):
            create_server(host="0.0.0.0", port=0, token=self.TOKEN)

    def test_invalid_extension_origin_is_rejected(self):
        for origin in ["https://example.com", "chrome-extension://short", self.EXTENSION_ORIGIN + "?bad=1"]:
            with self.assertRaises(ValueError):
                create_server(port=0, token=self.TOKEN, extension_origin=origin)

    def test_file_scan_endpoint_is_fail_closed_without_vision_model(self):
        image = io.BytesIO()
        Image.new('RGB', (20, 20), 'white').save(image, format='PNG')
        status, body = self.request_file({
            "data_base64": base64.b64encode(image.getvalue()).decode('ascii'),
            "media_type": "image/png",
            "vision_mode": "always",
            "include_previews": True,
        })
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "BLOCKED_UNVERIFIED")
        self.assertFalse(body["vision_succeeded"])
        self.assertTrue(body['preview_pages'][0]['image_data_url'].startswith('data:image/png;base64,'))
        self.assertFalse(body['export_available'])

    def test_preview_flag_must_be_boolean(self):
        with self.assertRaises(HTTPError) as caught:
            self.request_file({'data_base64': 'eA==', 'media_type': 'image/png', 'include_previews': 'true'})
        self.assertEqual(caught.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
