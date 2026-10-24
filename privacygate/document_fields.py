"""Conservative labelled upload fields, not document authenticity validation.

Used on OCR transcripts only. Values and repaired text never enter reports.
English labels supplement, rather than replace, all-page local vision.
"""
import re

from .detectors import Finding, merge_nonoverlapping


# Label vocabulary rather than assumed universal document-number formats.
_IDENTIFIERS = (
    r'passport(?:\s+(?:no\.?|number))?|'
    r'(?:driving|driver[\x27’]?s?)\s+licen[cs]e(?:\s+(?:no\.?|number))?|dl\s*(?:no\.?|number)|'
    r'voter\s*(?:id|number)|epic(?:\s+(?:no\.?|number))?|'
    r'(?:ration|policy|insurance|patient|member|employee|student|admission|registration|'
    r'customer|consumer|subscriber|beneficiary|pension|certificate)\s*(?:id|no\.?|number)|'
    r'(?:medical\s+record|health\s+id|abha|uan|pf|pran|cif|mrn|uhid)'
    r'(?:\s+(?:id|no\.?|number))?|'
    r'(?:bank\s+)?account(?:\s+(?:no\.?|number))?|a/c|'
    r'(?:credit|debit|payment)\s+card(?:\s+(?:no\.?|number))?|'
    r'(?:gstin|gst\s*(?:no\.?|number))'
)
_LABELS = [
    (_IDENTIFIERS, 'POSSIBLE_ID'),
    (r'(?:full|patient|employee|student|customer|account\s+holder|card\s+holder|'
     r'father[\x27’]?s?|mother[\x27’]?s?|spouse[\x27’]?s?|given)\s*name|surname|name', 'PERSON'),
    (r'(?:residential|permanent|present|mailing|billing|shipping|correspondence)?\s*address', 'ADDRESS'),
    (r'date\s+of\s+birth|d\.?o\.?b\.?|birth\s+date', 'DATE_OF_BIRTH'),
    (r'mobile|phone|telephone|contact(?:\s+(?:no\.?|number))?', 'PHONE'),
    (r'upi(?:\s+id)?|vpa|iban|swift(?:\s+code)?|ifsc(?:\s+code)?', 'FINANCIAL_ID'),
    (r'diagnosis|medical\s+condition|test\s+result|blood\s+group', 'HEALTH_INFO'),
    (r'(?:net|gross|basic)\s+(?:salary|pay)|salary|taxable\s+income', 'FINANCIAL_INFO'),
]


def _pattern(labels):
    # Same-line or next-line values; no blank-line jumps or unbounded spans.
    return re.compile(r'^[ \t]*(?:' + labels + r')(?=[ \t:#=\-\n])[ \t]*(?::|#|=|-)?[ \t]*'
                      r'(?:\n[ \t]*)?(?P<value>[^\s:\n][^\n]{0,159})', re.I | re.M)


_PATTERNS = [(_pattern(label), entity) for label, entity in _LABELS]
_ALL_LABEL = re.compile(r'^(?:' + '|'.join(label for label, _ in _LABELS) + r')[ \t]*(?::|#|=)', re.I)
_CARD_SHAPE = re.compile(r'(?<!\w)(?:[0-9][ -]?){12,18}[0-9](?!\w)')
_MRZ = re.compile(r'^[ \t]*([A-Z0-9<«» ][A-Z0-9<«» ]{28,78}[A-Z0-9<«»])[ \t]*$', re.M)
_NOISY_MRZ = re.compile(r'^[ \t]*([A-Z][<«][^\n]{28,78})[ \t]*$', re.M)


def _luhn_valid(digits):
    total = 0
    for index, digit in enumerate(reversed(digits)):
        value = int(digit) * (2 if index % 2 else 1)
        total += value - 9 if value > 9 else value
    return total % 10 == 0 and len(set(digits)) > 1


def detect_document_fields(text: str) -> list[Finding]:
    findings = []
    for match in _CARD_SHAPE.finditer(text):
        digits = re.sub(r'[ -]', '', match.group())
        if _luhn_valid(digits):
            findings.append(Finding(*match.span(), 'POSSIBLE_ID', .7, 'document-shape',
                                    'Payment-card-shaped candidate with Luhn checksum; not proof of issuance'))
    for match in list(_MRZ.finditer(text)) + list(_NOISY_MRZ.finditer(text)):
        value = match.group(1).replace(' ', '').replace('«','<<').replace('»','<<')
        strict = 30 <= len(value) <= 44 and value.count('<') >= 2
        # OCR commonly turns trailing filler chevrons into letters/punctuation.
        # A machine-readable header plus name delimiter still warrants a full-line mask.
        noisy = (30 <= len(value) <= 80 and value[:2] in {'P<','I<','V<','A<','C<'}
                 and '<<' in value[:24])
        if (strict or noisy) and sum(c.isalnum() for c in value) >= 8:
            findings.append(Finding(*match.span(1), 'POSSIBLE_ID', .7, 'document-shape',
                                    'Machine-readable identity line candidate; cover entire line'))
    for pattern, entity in _PATTERNS:
        for match in pattern.finditer(text):
            value = match.group('value').rstrip()
            # Empty label followed by another field is not a value.
            if not value or _ALL_LABEL.match(value):
                continue
            if entity in {'POSSIBLE_ID', 'PHONE', 'DATE_OF_BIRTH', 'FINANCIAL_INFO'} and not any(
                    c.isdecimal() or c in '*Xx•' for c in value):
                continue
            start = match.start('value')
            end = start + len(value)
            # Include indented postal-address continuations, up to three lines.
            if entity == 'ADDRESS':
                tail = text[end:]
                for continuation in re.finditer(r'\n([ \t]+[^\n]{1,160})', tail):
                    if continuation.start() != end - (start + len(value)):
                        break
                    if _ALL_LABEL.match(continuation.group(1).strip()):
                        break
                    end = start + len(value) + continuation.end()
                    if text[start:end].count('\n') >= 2:
                        break
            findings.append(Finding(start, end, entity, .7, 'document-label',
                                    'Labelled personal document field; conservative review candidate'))
    return merge_nonoverlapping(findings)
