"""macOS setup preflight for the optional local Gemma fallback."""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import sys
import time

from .model import GemmaLocalClient
from .pipeline import review_text
from .readiness import probe_local_gemma


def _line(ok: bool, label: str, detail: str) -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}: {detail}")


def main() -> int:
    try:
        from .web import _load_env_file
        _load_env_file()
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Check macOS and local Gemma fallback readiness")
    parser.add_argument("--uploads", action="store_true", help="Also require local OCR engine and configured languages")
    parser.add_argument("--smoke", action="store_true",
                        help="Run one synthetic end-to-end contextual span test")
    parser.add_argument("--timeout", type=float, default=8.0,
                        help="Loopback preflight timeout in seconds (default: 8)")
    args = parser.parse_args()

    is_macos = platform.system() == "Darwin"
    is_apple_silicon = platform.machine().lower() in {"arm64", "aarch64"}
    python_ok = sys.version_info >= (3, 10)
    _line(is_macos, "Operating system", f"{platform.system()} {platform.release()}")
    _line(is_apple_silicon, "Apple Silicon", platform.machine())
    _line(python_ok, "Python", platform.python_version())
    lms_path = shutil.which("lms")
    print(f"[{'PASS' if lms_path else 'WARN'}] LM Studio CLI: "
          f"{'available' if lms_path else 'not on PATH; the LM Studio app can still start the server'}")

    if args.uploads:
        import io
        from PIL import Image
        from .ocr import TesseractOCR, OCRError
        buffer = io.BytesIO()
        Image.new('RGB', (100, 100), 'white').save(buffer, format='PNG')
        try:
            TesseractOCR().recognize(buffer.getvalue())
            _line(True, "Local OCR", "Tesseract and configured language data available")
        except OCRError:
            _line(False, "Local OCR", "install Tesseract and configured language data; see ITERATION_3.md")
            return 1

    try:
        client = GemmaLocalClient(
            os.getenv("PII_LLM_BASE_URL", "http://127.0.0.1:1234/v1"),
            os.getenv("PII_MODEL_ID", ""),
            timeout_seconds=args.timeout,
        )
    except ValueError as exc:
        _line(False, "Loopback endpoint", str(exc))
        return 1

    readiness = probe_local_gemma(client)
    _line(readiness.ready, "Gemma fallback", readiness.message)
    if not (is_macos and is_apple_silicon and python_ok and readiness.ready):
        print("NOT READY: fix the failed checks before enabling contextual fallback.")
        return 1

    if args.smoke:
        synthetic = "My name is Aarav Kulkarni; summarize this synthetic event ticket."
        started = time.perf_counter()
        result = review_text(synthetic, mode="always", model=client)
        kinds = {finding["entity"] for finding in result.findings}
        smoke_ok = result.llm_succeeded and "PERSON" in kinds
        _line(smoke_ok, "Synthetic fallback smoke",
              f"completed in {time.perf_counter() - started:.2f}s; no raw text logged")
        if not smoke_ok:
            print("NOT READY: Gemma did not return a usable exact PERSON span.")
            return 1

    print("READY: local Gemma fallback is configured. This is not a privacy certification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
