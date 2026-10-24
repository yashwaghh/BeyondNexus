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

from .detectors import detect_rules


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
        for finding in detect_rules(self.text):
            words = [w for w in self.words if w['start'] < finding.end and w['end'] > finding.start]
            # One box per line avoids a huge rectangle across unrelated text.
            lines = {}
            for word in words:
                lines.setdefault(word['line'], []).append(word)
            for group in lines.values():
                left = min(w['left'] for w in group)
                top = min(w['top'] for w in group)
                right = max(w['right'] for w in group)
                bottom = max(w['bottom'] for w in group)
                output.append({'page': page, 'entity': finding.entity,
                               'score_heuristic': finding.confidence,
                               'ocr_confidence': min(w['confidence'] for w in group),
                               'source': 'ocr:' + finding.source,
                               'rationale': finding.rationale,
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
