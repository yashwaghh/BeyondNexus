"""Local Tesseract OCR. Transcripts are transient and never returned by the bridge."""
from __future__ import annotations

import csv
import io
import math
import os
import re
import subprocess
from dataclasses import dataclass

from PIL import Image

from .detectors import detect_rules, verhoeff_valid
from .document_fields import detect_document_fields


# Upload-only conservative candidates: checksum failure may be an OCR error.
# Keep character offsets unchanged; never return the repaired transcript.
_OCR_DIGITS = str.maketrans({'O': '0', 'o': '0', 'I': '1', 'l': '1', '|': '1',
                            'S': '5', 's': '5', 'B': '8'})
_ID_SHAPE = re.compile(r'(?<![\w|])(?:[0-9OoIl|SsB][\s\-–—]*){11}[0-9OoIl|SsB](?![\w|])')
_MASKED_ID = re.compile(r'(?<!\w)[Xx*•]{4}[\s-]*[Xx*•]{4}[\s-]*[0-9]{4}(?!\w)')


class OCRError(ValueError):
    pass


@dataclass
class OCRPage:
    text: str
    words: list[dict]
    width: int
    height: int

    def summary(self, page: int) -> dict:
        scores = [word['confidence'] for word in self.words]
        return {'page': page, 'word_count': len(scores),
                'mean_confidence': round(sum(scores) / len(scores), 2) if scores else None,
                'uncertain': not scores or any(score < 70 for score in scores)}

    def findings(self, page: int) -> list[dict]:
        output = []
        candidates = []
        for finding in detect_rules(self.text) + detect_document_fields(self.text):
            words = [w for w in self.words if w['start'] < finding.end and w['end'] > finding.start]
            candidates.append((words, finding.entity, finding.confidence, finding.source, finding.rationale))

        # OCR reading order can separate the three printed groups into blocks.
        # Reconstruct spatial rows as well as using the original reading order.
        rows = []
        for word in sorted(self.words, key=lambda w: (w['top'], w['left'])):
            center = (word['top'] + word['bottom']) / 2
            if rows and abs(center - rows[-1][0]) <= min(word['bottom']-word['top'], rows[-1][1]) * .5:
                rows[-1][2].append(word)
            else:
                rows.append((center, word['bottom']-word['top'], [word]))
        views = [(self.text, self.words)]
        for _, _, row in rows:
            fragments, mapped, offset, previous = [], [], 0, None
            for word in sorted(row, key=lambda w: w['left']):
                # Do not join columns separated by more than two word heights.
                gap = '\t' if previous and word['left']-previous['right'] > 2 * max(
                    word['bottom']-word['top'], previous['bottom']-previous['top']) else ' '
                if fragments:
                    fragments.append(gap); offset += 1
                value = self.text[word['start']:word['end']]
                fragments.append(value)
                mapped.append(dict(word, start=offset, end=offset+len(value)))
                offset += len(value); previous = word
            views.append((''.join(fragments), mapped))
        for text, mapped in views:
            for finding in detect_document_fields(text):
                words = [w for w in mapped if w['start'] < finding.end and w['end'] > finding.start]
                candidates.append((words, finding.entity, finding.confidence, finding.source, finding.rationale))
            for pattern in (_ID_SHAPE, _MASKED_ID):
                for match in pattern.finditer(text):
                    value = match.group()
                    # Tabs mark distant columns, not identifier separators.
                    if '\t' in value:
                        continue
                    digits = re.sub(r'[\s\-–—]', '', value).translate(_OCR_DIGITS)
                    if pattern is _ID_SHAPE and sum(c.isdecimal() for c in value) < 8:
                        continue
                    valid = (pattern is _ID_SHAPE and not any(c in value for c in 'OoIl|SsB')
                             and verhoeff_valid(digits))
                    entity = 'AADHAAR' if valid else 'POSSIBLE_ID'
                    words = [w for w in mapped if w['start'] < match.end() and w['end'] > match.start()]
                    candidates.append((words, entity, .99 if valid else .6, 'identifier-shape',
                                       'Upload identifier candidate; mask all groups even when OCR/checksum is uncertain'))

        seen = set()
        for words, entity, confidence, source, rationale in candidates:
            # One box per line avoids a huge rectangle across unrelated text.
            lines = {}
            for word in words:
                lines.setdefault(word['line'], []).append(word)
            for group in lines.values():
                left = min(w['left'] for w in group)
                top = min(w['top'] for w in group)
                right = max(w['right'] for w in group)
                bottom = max(w['bottom'] for w in group)
                key = (entity, left, top, right, bottom)
                if key in seen:
                    continue
                seen.add(key)
                output.append({'page': page, 'entity': entity,
                               'score_heuristic': confidence,
                               'ocr_confidence': min(w['confidence'] for w in group),
                               'source': 'ocr:' + source,
                               'rationale': rationale,
                               'decision': 'flag_and_review',
                               'region_0_1000': [math.floor(top * 1000 / self.height),
                                                   math.floor(left * 1000 / self.width),
                                                   math.ceil(bottom * 1000 / self.height),
                                                   math.ceil(right * 1000 / self.width)]})
        return output


def parse_tsv(tsv: str, width: int, height: int) -> OCRPage:
    if len(tsv) > 2_000_000 or width <= 0 or height <= 0:
        raise OCRError('OCR output exceeds limits.')
    words, fragments, offset, previous = [], [], 0, None
    try:
        reader = csv.DictReader(io.StringIO(tsv), delimiter='\t', quoting=csv.QUOTE_NONE)
        if not reader.fieldnames or not {'level', 'text', 'conf', 'left', 'top', 'width', 'height',
                                        'page_num', 'block_num', 'par_num', 'line_num'}.issubset(reader.fieldnames):
            raise ValueError
        for row in reader:
            if row['level'] != '5':
                continue
            text = row['text'].strip()
            if not text:
                continue
            line = tuple(int(row[key]) for key in ('page_num', 'block_num', 'par_num', 'line_num'))
            left, top, w, h = (int(row[key]) for key in ('left', 'top', 'width', 'height'))
            confidence = float(row['conf'])
            if not (math.isfinite(confidence) and 0 <= confidence <= 100 and
                    0 <= left < left + w <= width and 0 <= top < top + h <= height):
                raise ValueError
            if len(words) >= 10_000:
                raise ValueError
            separator = ('\n' if line != previous else ' ') if fragments else ''
            fragments.extend([separator, text])
            offset += len(separator)
            words.append(dict(start=offset, end=offset + len(text), line=line,
                              left=left, top=top, right=left+w, bottom=top+h,
                              confidence=confidence))
            offset += len(text)
            previous = line
    except (KeyError, TypeError, ValueError, csv.Error):
        raise OCRError('Invalid OCR word geometry or confidence.') from None
    return OCRPage(''.join(fragments), words, width, height)


class TesseractOCR:
    def __init__(self, executable: str | None = None, languages: str | None = None):
        self.executable = executable or os.environ.get('PRIVACYGATE_TESSERACT', 'tesseract')
        self.languages = languages or os.environ.get('PRIVACYGATE_OCR_LANGUAGES', 'eng')
        if not re.fullmatch(r'[A-Za-z_]+(?:\+[A-Za-z_]+)*', self.languages):
            raise ValueError('Invalid OCR language configuration.')

    def recognize(self, png: bytes) -> OCRPage:
        with Image.open(io.BytesIO(png)) as image:
            width, height = image.size
        try:
            # No shell, disk image, transcript file, or inherited cloud transport.
            result = subprocess.run([self.executable, 'stdin', 'stdout', '-l', self.languages,
                                     '--psm', '3', 'tsv'], input=png,
                                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                    timeout=30, check=True,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return parse_tsv(result.stdout.decode('utf-8'), width, height)
        except (OSError, subprocess.SubprocessError, UnicodeError):
            raise OCRError('Local OCR unavailable or failed; check Tesseract and language data.') from None
