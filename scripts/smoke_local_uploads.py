#!/usr/bin/env python3
"""Synthetic image/PDF smoke test for a live local Gemma vision model."""
from __future__ import annotations

import io
import os
from pathlib import Path
import sys
import time

from PIL import Image, ImageDraw
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from privacygate.model import GemmaLocalClient
from privacygate.readiness import probe_local_gemma
from privacygate.uploads import review_upload


def synthetic_image() -> bytes:
    image = Image.new('RGB', (900, 360), 'white')
    draw = ImageDraw.Draw(image)
    draw.text((50, 90), 'Name: Aarav Kulkarni', fill='black', font_size=42)
    draw.text((50, 180), 'Email: demo@example.org', fill='black', font_size=42)
    output = io.BytesIO()
    image.save(output, format='PNG')
    return output.getvalue()


def synthetic_pdf() -> bytes:
    output = io.BytesIO()
    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=300)
    font = DictionaryObject({
        NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'),
        NameObject('/BaseFont'): NameObject('/Helvetica'),
    })
    page[NameObject('/Resources')] = DictionaryObject({
        NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)}),
    })
    stream = DecodedStreamObject()
    stream.set_data(b'BT /F1 28 Tf 40 190 Td (Name: Aarav Kulkarni) Tj 0 -60 Td (Email: demo@example.org) Tj ET')
    page[NameObject('/Contents')] = writer._add_object(stream)
    writer.write(output)
    return output.getvalue()


def run_case(label: str, data: bytes, media_type: str, model: GemmaLocalClient) -> bool:
    started = time.perf_counter()
    result = review_upload(data, media_type, model=model)
    vision_kinds = sorted({finding['entity'] for finding in result.findings
                           if finding['source'] == 'gemma_vision'})
    elapsed = time.perf_counter() - started
    print(f'{label}: status={result.status}, vision_succeeded={result.vision_succeeded}, '
          f'vision_labels={vision_kinds}, elapsed_seconds={elapsed:.2f}')
    return result.vision_succeeded and bool(vision_kinds)


def main() -> int:
    model = GemmaLocalClient(
        os.getenv('PII_LLM_BASE_URL', 'http://127.0.0.1:1234/v1'),
        os.getenv('PII_MODEL_ID', ''),
        timeout_seconds=120,
    )
    readiness = probe_local_gemma(model)
    if not readiness.ready:
        print(f'NOT READY: {readiness.message}')
        return 1
    model.model_id = readiness.selected_model
    image_ok = run_case('synthetic_image', synthetic_image(), 'image/png', model)
    pdf_ok = run_case('synthetic_pdf', synthetic_pdf(), 'application/pdf', model)
    print('Raw image, extracted text, and model completion: deliberately not logged')
    if not (image_ok and pdf_ok):
        print('FAIL or PARTIAL: local Gemma vision did not return usable findings for both inputs.')
        return 1
    print('PASS: basic local vision path works; this is not a recall or privacy certification.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
