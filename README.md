# PrivacyGate — Local Review Prototype

[![macOS compatibility](https://github.com/yashwaghh/BeyondNexus/actions/workflows/macos.yml/badge.svg)](https://github.com/yashwaghh/BeyondNexus/actions/workflows/macos.yml)

Local-first PII pre-sharing pipeline: **regex + validators → optional Gemma 4 via LM Studio → exact-span masking → human approval gate**.

> **Status:** Iteration-two prototype, not a guarantee of anonymity or compliance. Includes text, image, and small-PDF local review plus an unpacked, user-invoked Chrome prototype; none automatically sends chat messages. Never use real identities to demo or debug.

## Quick start (macOS / Linux)

```bash
cd PrivacyGate_Iteration_1
python3 --version                    # Python 3.10+
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env                # optional configuration
# For local fallback: in LM Studio load Gemma 4 E2B Q4 and start Developer > Local Server.
curl http://127.0.0.1:1234/v1/models
# Set PII_MODEL_ID to the exact model ID returned (optional if exactly one model is visible).
set -a; source .env; set +a
python -m privacygate --mode off --text-file examples/sample.txt
python -m privacygate --mode on-uncertain --text-file examples/sample.txt
python -m unittest discover -s tests -v
python scripts/validate_iteration.py --record
```

## macOS + Gemma fallback check

The intended demo machine is an Apple Silicon Mac with 8 GB unified memory.
Start with a **Gemma 4 E2B instruction-tuned Q4** build. Google estimates about
2.9 GB for E2B Q4 model inference before runtime/context overhead, so E2B is the
conservative first choice; do not assume E4B will fit comfortably without using
LM Studio's memory estimate on the actual Mac.

```bash
# LM Studio must have been opened at least once before `lms` is available.
lms --help
lms ls

# Replace MODEL_KEY with the downloaded Gemma 4 E2B model key.
lms load --estimate-only MODEL_KEY --context-length 2048 --gpu auto
lms load MODEL_KEY --identifier privacygate-gemma --context-length 2048 --gpu auto
lms server start --bind 127.0.0.1 --port 1234

export PII_LLM_BASE_URL=http://127.0.0.1:1234/v1
export PII_MODEL_ID=privacygate-gemma

# Checks macOS, Apple Silicon, Python, loopback URL, loaded model identity,
# and one synthetic exact-span inference without logging the prompt.
privacygate-check-mac --smoke --timeout 75
```

If the package is not installed as an editable command, run the equivalent:

```bash
python -m privacygate.macos_check --smoke --timeout 75
```

The command exits nonzero if the host is not Apple Silicon macOS, LM Studio is
unreachable, the selected model is not loaded/ambiguous, the model ID does not
identify Gemma, or the synthetic fallback does not return a usable exact span.
The server may still run rules-only, but contextual scans remain fail-closed.

## Local testing interface

```bash
# Rules-only UI (no LM Studio needed)
python -m privacygate.web --no-model
# Then open http://127.0.0.1:8765

# Local Gemma enabled (LM Studio must already be running on loopback)
python -m privacygate.web
```

When Gemma mode is enabled, server startup performs a short readiness probe and
prints `READY` or `NOT READY`. A failed probe does not silently downgrade a
required contextual scan: that scan returns `BLOCKED_UNVERIFIED`.

### Image and small-PDF review (iteration two)

The same local UI accepts PNG, JPEG, WebP, and PDFs up to 6 MB; PDFs are limited
to 5 pages. It extracts and masks PDF text, flags metadata/attachment risks,
renders every page locally, and asks the loaded Gemma 4 model for semantic
vision findings and optional normalized regions.

The local UI and extension now show numbered bounding boxes over each normalized
image/PDF page, with plain-language findings and explicit location-unavailable
items. Downloadable annotated PNGs are **NOT redacted** and still show private
content. They are for local inspection, not automatic sharing. The web server
uses a configurable 120-second per-model-request timeout (`--model-timeout`).

This produces review guidance only. It does **not** create a redacted image or
PDF, and a sanitized text extraction is not a sanitized document. See
[`ITERATION_2.md`](ITERATION_2.md) for the contract, threat limits, and target-Mac
benchmark plan.

The server binds only to `127.0.0.1`, creates a fresh bearer token, disables
request logs, limits request size/concurrency, and exposes no forwarding API.
The UI keeps copy disabled until the user reviews the draft; blocked/unverified
results cannot be copied through its approval button.

The optional [`extension/`](extension/) directory contains a minimal Chrome
Manifest V3 prototype. Load it unpacked, configure its exact origin and local
bridge token as described in [`extension/README.md`](extension/README.md), then
 use its side panel to draft privately or capture a ChatGPT draft. It can copy or insert only after an
explicit review; it never submits the field. This is a browser extension—not a
  guaranteed ChatGPT interception mechanism.

With `--mode off`, regex is tested without Gemma; `--mode on-uncertain` calls only a loopback LM Studio server when candidate scores or contextual hints warrant it; `--mode always` invokes Gemma for any text up to the configured cap. All modes produce sanitized output but do **not** certify safety. Exit codes: `0` = ready for *manual* approval, `1` = review required, `2` = blocked/unverified, `3` = invalid input/configuration.

**Privacy caution:** CLI/UI output contains sanitized text, which may still contain undetected sensitive information. Do not pipe it into cloud tools automatically. The prototype extension requires affirmative review and approval.

## Documentation map

- [`IMPLEMENTATION.md`](IMPLEMENTATION.md): complete iteration-1 spec, setup, algorithms, acceptance criteria and commands.
- [`CONTEXT.md`](CONTEXT.md): enduring architecture decisions and project constraints for future coding agents.
- [`AGENTS.md`](AGENTS.md): task assignments, change protocol and validation agent contract.
- [`PROGRESS.md`](PROGRESS.md): append-only work log, next tasks, tests and handoff.
- [`THREAT_MODEL.md`](THREAT_MODEL.md): risk boundaries and minimum controls.
- [`NEXT_ITERATION.md`](NEXT_ITERATION.md): planned local bridge + browser extension integration, explicitly out of scope now.
- [`ITERATION_2.md`](ITERATION_2.md): bounded image/PDF parsing and local Gemma vision-review contract.

## Limitations

English-centric deterministic heuristics; image/PDF vision is unbenchmarked; no DOCX or secure redacted-file export yet; no indirect identity guarantees; possible misses and false alarms. Browser capture is user-invoked and cannot cover native apps or every send path. Rule/model scores are **not calibrated probabilities**. Bank-account numbers are not verified. PAN-shape is not proof of a real PAN. Aadhaar format/checksum is not identity verification. No cloud inference is allowed.

## Licensing

Project code: MIT. Gemma 4 weights are **not bundled** and are licensed separately by Google (Gemma 4 Apache 2.0); see official model card. Product uses LM Studio as a user-provided local runtime. Never commit private samples, real prompts or secrets.

## Iteration 3: OCR + rules + Gemma uploads
Uploads now require local Tesseract as well as Gemma vision. On Mac, install with `brew install tesseract`, then run `python -m privacygate.macos_check --uploads --smoke --timeout 75`. See [ITERATION_3.md](ITERATION_3.md) for setup, benchmark commands, confidence semantics and pending hardware checks. Reload the extension after updating. Missing OCR blocks uploads rather than reporting a completed scan.
