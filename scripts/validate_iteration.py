#!/usr/bin/env python3
"""Read-only by default iteration gate. --record appends a PII-free status entry."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    'README.md', 'IMPLEMENTATION.md', 'INTEGRATION_DECISION.md', 'CONTEXT.md', 'AGENTS.md',
    'PROGRESS.md', 'NEXT_ITERATION.md', 'THREAT_MODEL.md', '.env.example',
    '.gitignore', 'LICENSE', 'pyproject.toml',
    'privacygate/__main__.py', 'privacygate/detectors.py', 'privacygate/model.py',
    'privacygate/pipeline.py', 'privacygate/web.py', 'privacygate/ui/index.html',
    'privacygate/readiness.py', 'privacygate/macos_check.py',
    'extension/manifest.json', 'extension/popup.js', 'extension/README.md',
    'tests/test_detectors.py', 'tests/test_pipeline.py', 'tests/test_readiness.py', 'tests/test_web.py',
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--record', action='store_true', help='Append result to PROGRESS.md; never record raw prompts')
    args = parser.parse_args()
    missing = [file for file in REQUIRED if not (ROOT / file).is_file()]
    test = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                          cwd=ROOT, capture_output=True, text=True, timeout=30)
    test_match = re.search(r'Ran (\d+) tests?', test.stdout + test.stderr)
    test_count = int(test_match.group(1)) if test_match else 0
    benchmark = subprocess.run([sys.executable, 'scripts/benchmark_rules.py'],
                               cwd=ROOT, capture_output=True, text=True, timeout=30)
    cli = subprocess.run([sys.executable, '-m', 'privacygate', '--mode', 'off',
                          '--text-file', 'examples/sample.txt'],
                         cwd=ROOT, capture_output=True, text=True, timeout=30)
    # Example also includes an unscanned name; exit 2 = expected fail-closed.
    cli_ok = cli.returncode == 2 and '[PAN_1]' in cli.stdout and '[EMAIL_1]' in cli.stdout
    # Never persist raw test output; only aggregate checks are reported.
    ok = not missing and test.returncode == 0 and benchmark.returncode == 0 and cli_ok
    print('PrivacyGate Iteration 1 validation:', 'PASS' if ok else 'FAIL')
    print('Required files:', len(REQUIRED) - len(missing), '/', len(REQUIRED))
    if missing:
        print('Missing files:', ', '.join(missing))
    print('Unit tests:', test_count, 'PASS' if test.returncode == 0 else 'FAIL')
    print('Benchmark script exit code:', benchmark.returncode)
    print('CLI fail-closed smoke:', 'PASS' if cli_ok else 'FAIL')
    print('LM Studio live E2B inference: NOT VERIFIED by this validator (run separately).')
    print('Real-world PII safety / false-negative rate: NOT CERTIFIED.')
    if args.record:
        stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
        with (ROOT / 'PROGRESS.md').open('a', encoding='utf-8') as handle:
            handle.write(f'\n- {stamp} | Validation agent | {"PASS" if ok else "FAIL"} | '
                         f'files={len(REQUIRED)-len(missing)}/{len(REQUIRED)}, tests={test_count}; '
                         'live local model and external integrations unverified.\n')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
