"""Local synthetic document field/box benchmark. Does not establish real-document recall."""
import argparse
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw
from privacygate.ocr import TesseractOCR, OCRError
from privacygate.redaction import redact_export
from privacygate.uploads import _render_pdf_pages
from scripts.document_samples import DOCUMENTS, render_document


def coverage(source, targets, findings):
    """Fraction of target's rendered text ink covered by same-type masks."""
    image = Image.open(io.BytesIO(source)).convert('RGB')
    results = []
    for entity, (left,top,right,bottom) in targets:
        mask = Image.new('1', image.size)
        draw = ImageDraw.Draw(mask)
        for finding in findings:
            if finding['entity'] != entity or not finding.get('region_0_1000'):
                continue
            t,l,b,r = finding['region_0_1000']
            draw.rectangle((l*image.width/1000,t*image.height/1000,
                            r*image.width/1000,b*image.height/1000), fill=1)
        ink = covered = 0
        for y in range(int(top), int(bottom)+1):
            for x in range(int(left), int(right)+1):
                if min(image.getpixel((x,y))) < 180:
                    ink += 1
                    covered += bool(mask.getpixel((x,y)))
        results.append(covered / ink if ink else 0)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-perfect', action='store_true')
    args = parser.parse_args()
    rows, failures = [], 0
    try:
        engine = TesseractOCR()
        for name in DOCUMENTS:
            source, _, targets = render_document(name)
            pdf, _ = redact_export(source, 'image/png', [], 'pdf', reviewed=True)
            for kind, scanned in (('image',source), ('pdf',_render_pdf_pages(pdf)[0])):
                findings = engine.recognize(scanned).findings(1)
                values = coverage(source, targets, findings)
                missed = sum(value < .98 for value in values)
                # A clean benign invoice is a false-positive control.
                false_positives = len(findings) if not targets else 0
                failures += missed + false_positives
                rows.append(dict(document=name, format=kind, fields=len(targets),
                                 field_coverage=[dict(entity=entity,ink_coverage=value)
                                                 for (entity,_),value in zip(targets,values)],
                                 missed_or_partial=missed, min_ink_coverage=min(values,default=1),
                                 benign_false_positives=false_positives))
                if missed:
                    # Character classes/geometry only: diagnose recognition without
                    # emitting words, values or repaired transcripts.
                    recognized = engine.recognize(scanned)
                    diagnostics = []
                    width,height = recognized.width,recognized.height
                    for (_, (l,t,r,b)),value in zip(targets,values):
                        if value >= .98:
                            continue
                        words = [w for w in recognized.words if w['left']/width < r/1400 and
                                 w['right']/width > l/1400 and w['top']/height < b/850 and w['bottom']/height > t/850]
                        classes = []
                        for w in words:
                            word = recognized.text[w['start']:w['end']]
                            classes.append(''.join('d' if c.isdecimal() else 'A' if c.isupper() else
                                                   'a' if c.islower() else c for c in word))
                        diagnostics.append(classes)
                    rows[-1]['missed_field_character_classes'] = diagnostics
    except OCRError:
        print(json.dumps(dict(status='BLOCKED_UNVERIFIED', reason='Native Tesseract unavailable or failed')))
        return 2
    print(json.dumps(dict(synthetic_only=True, cases=rows, failures=failures),indent=2))
    return 1 if args.require_perfect and failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
