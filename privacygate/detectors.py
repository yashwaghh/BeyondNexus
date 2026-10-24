"""Local rule-first PII detection. Matches are candidates, not privacy guarantees."""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Finding:
    start: int
    end: int
    entity: str
    confidence: float
    source: str
    rationale: str


# Verhoeff's check-digit algorithm, used as a format sanity check for Aadhaar.
_D = (
    (0,1,2,3,4,5,6,7,8,9), (1,2,3,4,0,6,7,8,9,5),
    (2,3,4,0,1,7,8,9,5,6), (3,4,0,1,2,8,9,5,6,7),
    (4,0,1,2,3,9,5,6,7,8), (5,9,8,7,6,0,4,3,2,1),
    (6,5,9,8,7,1,0,4,3,2), (7,6,5,9,8,2,1,0,4,3),
    (8,7,6,5,9,3,2,1,0,4), (9,8,7,6,5,4,3,2,1,0),
)
_P = (
    (0,1,2,3,4,5,6,7,8,9), (1,5,7,6,2,8,3,0,9,4),
    (5,8,0,3,7,9,6,1,4,2), (8,9,1,6,0,4,3,5,2,7),
    (9,4,5,3,1,2,6,8,7,0), (4,2,8,6,5,7,3,9,0,1),
    (2,7,9,3,8,0,6,4,1,5), (7,0,4,6,9,1,3,2,5,8),
)


def verhoeff_valid(digits: str) -> bool:
    if len(digits) != 12 or not digits.isascii() or not digits.isdigit() or digits[0] not in '23456789':
        return False
    checksum = 0
    for index, digit in enumerate(reversed(digits)):
        checksum = _D[checksum][_P[index % 8][int(digit)]]
    return checksum == 0


_EMAIL = re.compile(r'(?<![\w@])([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})(?![\w@])', re.I)
_PAN = re.compile(r'(?<![A-Z0-9])([A-Z]{5}[0-9]{4}[A-Z])(?![A-Z0-9])', re.I)
_AADHAAR = re.compile(r'(?<![0-9])([2-9][0-9]{3}[ -]?[0-9]{4}[ -]?[0-9]{4})(?![0-9])')
_PHONE = re.compile(r'(?<![0-9])((?:\+91[ -]?)?[6-9][0-9]{9})(?![0-9])')
_ACCT = re.compile(
    r'\b(?:bank\s+)?(?:account(?:\s+(?:no\.?|number))?|acct\.?|a/c)\s*[:#=\-]?\s*([0-9][0-9 -]{7,22}[0-9])(?![0-9])',
    re.I,
)
_PHONE_CONTEXT = re.compile(r'\b(?:phone|mobile|cell|contact|whatsapp|tel|call)\b', re.I)
_AADHAAR_CONTEXT = re.compile(r'\b(?:aadhaar|aadhar|uidai|uid)\b', re.I)


def _near(text: str, start: int, end: int, expression: re.Pattern[str], radius: int = 30) -> bool:
    return bool(expression.search(text[max(0, start - radius): min(len(text), end + radius)]))


def _overlap(a: Finding, b: Finding) -> bool:
    return a.start < b.end and b.start < a.end


def merge_nonoverlapping(findings: list[Finding]) -> list[Finding]:
    """Keep longer/higher-confidence matches; no character is replaced twice."""
    selected: list[Finding] = []
    ordered = sorted(findings, key=lambda f: (-(f.end - f.start), -f.confidence, f.start))
    for candidate in ordered:
        if not any(_overlap(candidate, saved) for saved in selected):
            selected.append(candidate)
    return sorted(selected, key=lambda f: (f.start, f.end))


def detect_rules(text: str) -> list[Finding]:
    found: list[Finding] = []
    for match in _EMAIL.finditer(text):
        found.append(Finding(*match.span(1), 'EMAIL', 0.99, 'regex', 'Email-format match'))
    for match in _PAN.finditer(text):
        found.append(Finding(*match.span(1), 'PAN', 0.95, 'regex', 'PAN-format match; not proof of issuance'))
    for match in _AADHAAR.finditer(text):
        value = re.sub(r'[ -]', '', match.group(1))
        if verhoeff_valid(value):
            found.append(Finding(*match.span(1), 'AADHAAR', 0.99, 'regex+checksum', 'Aadhaar shape and Verhoeff check digit'))
        elif _near(text, *match.span(1), _AADHAAR_CONTEXT):
            found.append(Finding(*match.span(1), 'POSSIBLE_ID', 0.55, 'regex', 'Aadhaar-labelled value has invalid check digit'))
    for match in _PHONE.finditer(text):
        value = match.group(1)
        has_context = value.startswith('+91') or _near(text, *match.span(1), _PHONE_CONTEXT)
        found.append(Finding(*match.span(1), 'PHONE', 0.94 if has_context else 0.72,
                             'regex+context' if has_context else 'regex',
                             'Indian mobile shape; context present' if has_context else 'Phone-shaped number without context'))
    for match in _ACCT.finditer(text):
        value = re.sub(r'[ -]', '', match.group(1))
        if 9 <= len(value) <= 18 and value.isdigit():
            found.append(Finding(*match.span(1), 'BANK_ACCOUNT', 0.82, 'regex+context',
                                 'Account label and plausible digit length; cannot verify account ownership'))
    return merge_nonoverlapping(found)
