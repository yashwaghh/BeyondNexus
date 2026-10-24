"""Local-only test UI and authenticated bridge for PrivacyGate.

The server deliberately has no forwarding endpoint and keeps request logging off.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
from pathlib import Path
import re
import secrets
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .model import GemmaLocalClient
from .pipeline import review_text
from .readiness import probe_local_gemma
from .uploads import UploadReviewError, review_upload

MAX_REQUEST_BYTES = 100_000
MAX_UPLOAD_REQUEST_BYTES = 9_000_000
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
UI_ROOT = Path(__file__).with_name("ui")


class PrivacyGateServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, server_address, handler, *, token: str, extension_origin: str | None,
                 model: GemmaLocalClient | None, ocr=None):
        super().__init__(server_address, handler)
        self.token = token
        self.extension_origin = extension_origin
        self.model = model
        self.ocr = ocr
        self.scan_slots = threading.BoundedSemaphore(2)

    @property
    def local_origin(self) -> str:
        host, port = self.server_address[:2]
        return f"http://{host}:{port}"


class PrivacyGateHandler(BaseHTTPRequestHandler):
    server: PrivacyGateServer

    def log_message(self, _format: str, *_args) -> None:
        """Disable HTTP access logs so sensitive URLs/metadata are never persisted."""

    def _send(self, status: int, body: bytes, content_type: str,
              *, cors_origin: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data: blob:")
        if cors_origin:
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict, *, cors_origin: str | None = None) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8", cors_origin=cors_origin)

    def _allowed_origin(self) -> str | None:
        origin = self.headers.get("Origin", "")
        if origin == self.server.local_origin:
            return origin
        if self.server.extension_origin and origin == self.server.extension_origin:
            return origin
        return None

    def _authorized(self) -> bool:
        supplied = self.headers.get("Authorization", "")
        expected = f"Bearer {self.server.token}"
        return secrets.compare_digest(supplied, expected)

    def do_OPTIONS(self) -> None:
        if urlparse(self.path).path not in {"/v1/scan", "/v1/scan-file"} or not (origin := self._allowed_origin()):
            self._json(HTTPStatus.FORBIDDEN, {"error": "Origin not allowed"})
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Vary", "Origin")
        self.end_headers()

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._json(HTTPStatus.OK, {"status": "ok", "service": "privacygate"})
            return
        assets = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/app.js": ("app.js", "text/javascript; charset=utf-8"),
            "/styles.css": ("styles.css", "text/css; charset=utf-8"),
            "/preview.js": ("preview.js", "text/javascript; charset=utf-8"),
        }
        if path not in assets:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        filename, content_type = assets[path]
        body = (UI_ROOT / filename).read_bytes()
        if filename == "index.html":
            body = body.replace(b"__PRIVACYGATE_TOKEN__", self.server.token.encode("ascii"))
        self._send(HTTPStatus.OK, body, content_type)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in {"/v1/scan", "/v1/scan-file"}:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        origin = self._allowed_origin()
        if not origin:
            self._json(HTTPStatus.FORBIDDEN, {"error": "Origin not allowed"})
            return
        if not self._authorized():
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "Authentication required"}, cors_origin=origin)
            return
        if self.headers.get_content_type() != "application/json":
            self._json(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "Use application/json"}, cors_origin=origin)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        request_limit = MAX_UPLOAD_REQUEST_BYTES if path == "/v1/scan-file" else MAX_REQUEST_BYTES
        if length <= 0 or length > request_limit:
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "Invalid request size"}, cors_origin=origin)
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError
            if not self.server.scan_slots.acquire(blocking=False):
                self._json(HTTPStatus.TOO_MANY_REQUESTS, {"error": "Scanner busy"}, cors_origin=origin)
                return
            try:
                if path == "/v1/scan":
                    text = payload.get("text")
                    mode = payload.get("mode", "on-uncertain")
                    if not isinstance(text, str) or not isinstance(mode, str):
                        raise ValueError
                    result = review_text(text, mode=mode, model=self.server.model)
                else:
                    encoded = payload.get("data_base64")
                    media_type = payload.get("media_type")
                    vision_mode = payload.get("vision_mode", "always")
                    include_previews = payload.get("include_previews", False)
                    if not isinstance(include_previews, bool):
                        raise ValueError
                    if not isinstance(encoded, str) or not isinstance(media_type, str) or not isinstance(vision_mode, str):
                        raise ValueError
                    try:
                        upload = base64.b64decode(encoded, validate=True)
                    except (binascii.Error, ValueError):
                        raise ValueError from None
                    result = review_upload(upload, media_type, vision_mode=vision_mode,
                                           model=self.server.model, include_previews=include_previews, ocr=self.server.ocr)
            finally:
                self.server.scan_slots.release()
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, UploadReviewError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "Invalid scan request"}, cors_origin=origin)
            return
        self._json(HTTPStatus.OK, result.to_dict(), cors_origin=origin)


def create_server(*, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, token: str,
                  extension_origin: str | None = None,
                  model: GemmaLocalClient | None = None, ocr=None) -> PrivacyGateServer:
    if host != DEFAULT_HOST:
        raise ValueError("PrivacyGate UI must bind to 127.0.0.1")
    if not token or len(token) < 24:
        raise ValueError("Bridge token must contain at least 24 characters")
    if extension_origin is not None:
        parsed = urlparse(extension_origin)
        if (parsed.scheme != "chrome-extension" or not re.fullmatch(r"[a-p]{32}", parsed.netloc)
                or parsed.path not in {"", "/"} or parsed.query or parsed.fragment
                or parsed.username or parsed.password or parsed.port is not None):
            raise ValueError("Extension origin must look like chrome-extension://<extension-id>")
        extension_origin = extension_origin.rstrip("/")
    return PrivacyGateServer((host, port), PrivacyGateHandler, token=token,
                             extension_origin=extension_origin, model=model, ocr=ocr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local-only PrivacyGate test interface")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--extension-origin", help="Exact unpacked extension origin, if extension access is needed")
    parser.add_argument("--token", default=os.environ.get("PRIVACYGATE_BRIDGE_TOKEN", ""),
                        help="Optional 24+ character token; otherwise a fresh token is generated")
    parser.add_argument("--no-model", action="store_true", help="Disable LM Studio for this server")
    parser.add_argument("--model", default=os.environ.get("PII_MODEL_ID", ""))
    parser.add_argument("--model-timeout", type=float, default=120,
                        help="Local model timeout per text/image/page request in seconds (default: 120)")
    args = parser.parse_args()
    token = args.token or secrets.token_urlsafe(32)
    model = None
    if not args.no_model:
        endpoint = os.environ.get("PII_LLM_BASE_URL", "http://127.0.0.1:1234/v1")
        probe = GemmaLocalClient(endpoint, args.model, timeout_seconds=5)
        readiness = probe_local_gemma(probe)
        print(f"Gemma fallback preflight: {'READY' if readiness.ready else 'NOT READY'} — {readiness.message}")
        if readiness.ready:
            model = GemmaLocalClient(endpoint, readiness.selected_model, timeout_seconds=args.model_timeout)
    server = create_server(port=args.port, token=token,
                           extension_origin=args.extension_origin, model=model)
    print(f"PrivacyGate UI: {server.local_origin}")
    print(f"Bridge token (keep local): {token}")
    if args.extension_origin:
        print(f"Allowed extension origin: {args.extension_origin.rstrip('/')}")
    print("No request text is logged. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
