from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .model import GemmaLocalClient
from .pipeline import review_text


def main() -> int:
    parser = argparse.ArgumentParser(description='Local rule-first PII sanitizer (iteration 1)')
    parser.add_argument('--text-file', type=Path, help='UTF-8 input text file. If absent read stdin.')
    parser.add_argument('--mode', choices=['off', 'on-uncertain', 'always'],
                        default=os.environ.get('PII_LLM_MODE', 'on-uncertain'))
    parser.add_argument('--json', action='store_true', help='Print sanitized text and non-PII metadata as JSON')
    parser.add_argument('--model', default=os.environ.get('PII_MODEL_ID', ''), help='Exact loaded LM Studio model ID')
    args = parser.parse_args()
    try:
        text = args.text_file.read_text(encoding='utf-8') if args.text_file else sys.stdin.read()
        model = None
        if args.mode != 'off':
            model = GemmaLocalClient(os.environ.get('PII_LLM_BASE_URL', 'http://127.0.0.1:1234/v1'), args.model)
        result = review_text(text, mode=args.mode, model=model)
        if args.json:
            print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        else:
            print(result.sanitized_text)
            print(f'\n[PrivacyGate status: {result.status}]', file=sys.stderr)
            for warning in result.warnings:
                print(f'[warning] {warning}', file=sys.stderr)
        return 2 if result.status == 'BLOCKED_UNVERIFIED' else (1 if result.requires_human_review else 0)
    except (ValueError, OSError, UnicodeError) as exc:
        print(f'Configuration or input error: {type(exc).__name__}', file=sys.stderr)
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
