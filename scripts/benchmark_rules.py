#!/usr/bin/env python3
"""Tiny synthetic rule benchmark: demonstration only, NOT a population accuracy claim."""
from __future__ import annotations

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from privacygate.detectors import detect_rules

EXAMPLES = [
    ('My email is demo@example.org', [('EMAIL', 'demo@example.org')]),
    ('PAN: ABCDE1234F', [('PAN', 'ABCDE1234F')]),
    ('Call +91 9876543210', [('PHONE', '+91 9876543210')]),
    ('Bank account number: 23456789012345', [('BANK_ACCOUNT', '23456789012345')]),
    ('The budget is 2500 rupees', []),
    ('Reference 9876543210 is a ticket identifier', []),
    ('My name is Aarav Kulkarni', [('PERSON', 'Aarav Kulkarni')]),
]


def main() -> int:
    tp = fp = fn = 0
    for text, expected in EXAMPLES:
        gold = set(expected)
        predictions = {(item.entity, text[item.start:item.end]) for item in detect_rules(text)}
        tp += len(gold & predictions)
        fp += len(predictions - gold)
        fn += len(gold - predictions)
    precision = tp / (tp + fp) if (tp + fp) else 0
    recall = tp / (tp + fn) if (tp + fn) else 0
    print(f'Synthetic examples: {len(EXAMPLES)}; TP={tp}, FP={fp}, FN={fn}')
    print(f'Exact-span precision={precision:.3f}, recall={recall:.3f}')
    print('Not a real-world benchmark; includes deliberately difficult cases.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
