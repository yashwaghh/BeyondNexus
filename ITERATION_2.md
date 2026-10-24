# PrivacyGate - Iteration 2 image and small-PDF review

**Version:** 0.1 · **Date:** 2026-10-24 · **Status:** Local parsing and vision-review scaffold implemented; live Gemma 4 vision quality remains unverified on the target Mac

## Scope for the first slice

Accept one local PNG, JPEG, WebP, or PDF upload through the localhost test UI
or extension side panel.
Files stay in process memory and are never forwarded beyond loopback. Images
are normalized to PNG before analysis. PDFs are limited to 5 pages and 6 MB,
their text layer is extracted and scanned by deterministic rules, and every
page is rendered to an image for local Gemma vision review.

This slice produces **review findings**, not a redacted image or PDF. A text
draft extracted from a PDF is not equivalent to a securely redacted PDF. The
original file remains private until a human has inspected every page, metadata,
attachments, and the review output.

## Processing flow

```text
Upload bytes + declared media type
    |
    +--> size/type/page-count validation
    |
    +--> image: decode, EXIF orientation, RGB normalization, downscale, PNG
    |
    +--> PDF: encryption/page checks
           +--> text-layer extraction -> deterministic PII rules -> sanitized text draft
           +--> metadata/form/attachment structure checks
           +--> render every page to PNG in memory
    |
    +--> local Gemma 4 vision on each normalized image/page
           +--> strict entity type
           +--> optional [y1,x1,y2,x2] region normalized to 0..1000
           +--> never return model-transcribed sensitive values
    |
    +--> fail-closed status + human review guidance
```

## API

`POST /v1/scan-file` uses the same bearer token and exact-origin checks as the
text endpoint.

```json
{
  "data_base64": "...",
  "media_type": "application/pdf",
  "vision_mode": "always",
  "include_previews": true
}
```

The result includes `media_type`, `page_count`, optional `sanitized_text`,
non-sensitive `findings`, `status`, vision attempt/success flags, warnings, and
`export_available: false`. File names, raw model output, extracted identifiers,
and original upload bytes are omitted by default. When `include_previews` is
explicitly true, `preview_pages` contains the normalized PNG page images as data
URLs. These contain private visible content and must not be logged or treated
as sanitized output. The authenticated UI uses exactly the images sent to Gemma,
so normalized coordinates align after EXIF rotation and PDF rendering.

## Visual review output

Both interfaces draw numbered red bounding boxes and show corresponding
plain-language labels. Regions are approximate model proposals; a PHONE label
on an Aadhaar card may be wrong. Unlocated text/metadata/model findings remain
listed with an explicit location-unavailable message; no coordinates are invented.
Missing boxes never mean the document is safe.

Users can deliberately download each annotated page as a PNG labelled
**NOT REDACTED**. This is inspection output containing original visible content,
not a cleaned image/PDF. Upload results cannot authorize copying/insertion or
attachment transfer into ChatGPT. Clearing/replacing the draft or file clears
the preview and invalidates pending results.

## Status rules

- `BLOCKED_UNVERIFIED`: vision disabled, unavailable, malformed, or failed; or
  the input cannot be safely parsed within limits.
- `REVIEW_REQUIRED`: local vision completed and at least one rule, metadata, or
  vision finding exists.
- `READY_FOR_MANUAL_APPROVAL`: local vision completed with no known finding.
  This still requires manual review and is not a privacy certificate.

`requires_human_review` is always true for uploads in this iteration.

## Implemented controls

- Supported types: PNG, JPEG, WebP, PDF.
- Maximum upload: 6 MB; maximum PDF length: 5 pages.
- Maximum decoded image: 20 megapixels; normalized maximum edge: 2200 pixels.
- PDF render scale is bounded before native raster allocation.
- Encrypted PDFs are rejected.
- PDF author/title/subject/keyword metadata presence is flagged without values.
- Embedded files are flagged as unscanned high risk.
- Form fields and XML metadata streams produce explicit warnings.
- PDF parsing and rendering use `pypdf` and permissively licensed PDFium
  bindings (`pypdfium2`); images use Pillow.
- No upload persistence, analytics, hosted inference, or sanitized-file export.

## Known risks and deferred work

- Parser/rendering currently runs in-process. A malicious PDF could consume
  CPU/memory despite byte/page limits; move parsing into a resource-limited
  subprocess before accepting untrusted public uploads.
- Vision regions and OCR quality are model-dependent and uncalibrated.
- Hidden layers, incremental revisions, JavaScript, annotations, unusual forms,
  signatures, steganography, and attachment contents are not comprehensively
  analyzed.
- Region-based visual overlays are not secure redaction. Safe export requires
  removing underlying objects/metadata and verifying the final file.
- Live Gemma 4 image-input behavior, latency, memory pressure, JSON compliance,
  multilingual OCR, handwriting, and false negatives need measurement on the
  target 8 GB Mac.

## Acceptance commands

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python scripts/validate_iteration.py --record
python -m privacygate.web
python scripts/smoke_local_uploads.py  # target Mac with Gemma loaded
```

Manual validation must use only synthetic images/PDFs and record aggregate
results in `PROGRESS.md`, never the source file, OCR transcript, or model output.

## Next evidence milestone

Build a small synthetic set covering: visible email/phone/PAN/Aadhaar shapes,
names and addresses, blank scans, rotated images, handwriting, multilingual
text, metadata-only identity, a form value, benign numbers, and a two-page PDF.
Record per-entity/page recall, false positives, region usefulness, median/p95
latency, and peak memory. Only then decide whether to implement verified
redacted image/PDF export or expand page/file-size limits.
