#!/usr/bin/env python3
"""Local LM Studio smoke test using entirely synthetic text. Never print raw data."""
from __future__ import annotations
import os
import sys
import time

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from privacygate.model import GemmaLocalClient, LocalModelError
from privacygate.pipeline import review_text


def main() -> int:
    model = GemmaLocalClient(os.getenv('PII_LLM_BASE_URL', 'http://127.0.0.1:1234/v1'),
                             os.getenv('PII_MODEL_ID', ''), timeout_seconds=75)
    test = 'My name is Aarav Kulkarni; please summarize this event ticket. My email is demo@example.org.'
    started = time.perf_counter()
    result = review_text(test, mode='always', model=model)
    elapsed = time.perf_counter() - started
    kinds = sorted({f['entity'] for f in result.findings})
    print(f'Status: {result.status}')
    print(f'Local inference succeeded: {result.llm_succeeded}')
    print(f'Elapsed seconds: {elapsed:.2f}')
    print(f'Entity labels found (no values): {kinds}')
    print('Raw prompt/model completion: deliberately not logged')
    if not result.llm_succeeded or 'PERSON' not in kinds:
        print('FAIL or PARTIAL: local model did not return a usable PERSON span. Test model settings/format.')
        return 1
    print('PASS: basic local contextual span detection; not a privacy certification.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
