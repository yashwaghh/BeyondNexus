#!/usr/bin/env python3
"""Synthetic OCR/rules vs optional Gemma benchmark; aggregate output only.

Not a representative dataset. A zero exit means execution completed, not perfect recall.
--require-perfect makes the small clean regression subset an acceptance gate.
"""
import argparse
import io
import json
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from privacygate.detectors import verhoeff_valid
from privacygate.model import GemmaLocalClient, LocalModelError
from privacygate.ocr import OCRError, TesseractOCR


def iou(a, b):
    intersection = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    area = lambda r: (r[2]-r[0]) * (r[3]-r[1])
    return intersection / (area(a)+area(b)-intersection) if intersection else 0


def score(expected, found):
    remaining = list(found)
    tp = 0
    localized = 0
    for entity, box in expected:
        candidates = [(iou(box, f['region_0_1000']), index) for index, f in enumerate(remaining)
                      if f['entity'] == entity and f.get('region_0_1000')]
        if candidates:
            overlap, index = max(candidates)
            if overlap >= .1:
                remaining.pop(index)
                tp += 1
                localized += overlap >= .5
    return {'tp': tp, 'fp': len(remaining), 'fn': len(expected)-tp, 'localized_iou_0_5': localized}


def samples():
    # Pillow's bundled font makes generation independent of OS font paths.
    font = ImageFont.load_default(size=38)
    aadhaar = next('23456789012'+d for d in '0123456789' if verhoeff_valid('23456789012'+d))
    cases = [('email', 'Email: ', 'demo@example.org', 'EMAIL'),
             ('pan', 'PAN: ', 'ABCDE1234F', 'PAN'),
             ('phone', 'Mobile: ', '9876543210', 'PHONE'),
             ('aadhaar', 'Aadhaar: ', aadhaar, 'AADHAAR'),
             ('benign', '', 'Meeting at 14:30 in room 42', None),
             ('blank', '', '', None)]
    for name, prefix, value, entity in cases:
        image = Image.new('RGB', (1200, 240), 'white')
        draw = ImageDraw.Draw(image)
        draw.text((40, 70), prefix+value, fill='black', font=font)
        x = 40 + draw.textlength(prefix, font=font)
        left, top, right, bottom = draw.textbbox((x, 70), value, font=font)
        expected = [(entity, [top/240*1000, left/1200*1000, bottom/240*1000, right/1200*1000])] if entity else []
        variants = [('clean', image)]
        if entity:
            variants.append(('blurred', image.filter(ImageFilter.GaussianBlur(2.5))))
        for variant, rendered in variants:
            output = io.BytesIO()
            rendered.save(output, format='PNG')
            yield name+'_'+variant, output.getvalue(), expected, variant == 'clean'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-gemma', action='store_true', help='Also evaluate local Gemma vision; may take minutes')
    parser.add_argument('--require-perfect', action='store_true')
    args = parser.parse_args()
    ocr = TesseractOCR()
    if args.live_gemma:
        import os
        model = GemmaLocalClient(os.getenv('PII_LLM_BASE_URL', 'http://127.0.0.1:1234/v1'),
                                os.getenv('PII_MODEL_ID', ''), timeout_seconds=120)
    totals, times, rows = {}, [], []
    clean_errors = 0
    for name, png, expected, clean in samples():
        started = time.perf_counter()
        try:
            recognized = ocr.recognize(png)
            findings = recognized.findings(1)
            paths = {'ocr_rules': findings}
            if args.live_gemma:
                vision = [{'entity': f.entity, 'region_0_1000': list(f.region) if f.region else None}
                          for f in model.detect_image(png, 'image/png')]
                paths['vision'] = vision
                # Avoid counting agreement as a second false positive.
                paths['combined'] = findings + [f for f in vision if not any(
                    f['entity'] == o['entity'] and f.get('region_0_1000') and
                    iou(f['region_0_1000'], o['region_0_1000']) >= .5 for o in findings)]
        except (OCRError, LocalModelError):
            print(json.dumps({'status': 'BLOCKED_UNVERIFIED', 'case': name,
                              'reason': 'OCR/Gemma unavailable or failed; no benchmark result claimed'}))
            return 2
        elapsed = time.perf_counter()-started
        times.append(elapsed)
        row = {'case': name, 'seconds': round(elapsed, 3), 'paths': {}}
        for path, detected in paths.items():
            metrics = score(expected, detected)
            row['paths'][path] = metrics
            total = totals.setdefault(path, dict(tp=0, fp=0, fn=0, localized_iou_0_5=0))
            for key, value in metrics.items():
                total[key] += value
            if clean and path == 'ocr_rules':
                clean_errors += metrics['fp'] + metrics['fn']
        rows.append(row)
    for total in totals.values():
        total['precision'] = total['tp'] / max(1, total['tp']+total['fp'])
        total['recall'] = total['tp'] / max(1, total['tp']+total['fn'])
    print(json.dumps({'synthetic_only': True, 'cases': rows, 'totals': totals,
                      'median_seconds': statistics.median(times), 'max_seconds': max(times)}, indent=2))
    return 1 if args.require_perfect and clean_errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
