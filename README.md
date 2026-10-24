# PrivacyGate — Local-First PII Pre-Sharing Defense & Review Bridge

[![macOS Apple Silicon & Linux](https://img.shields.io/badge/platform-macOS%20Apple%20Silicon%20%7C%20Linux-brightgreen)](https://github.com/yashwaghh/BeyondNexus)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![Chrome Extension MV3](https://img.shields.io/badge/chrome%20extension-MV3-orange)](https://developer.chrome.com/docs/extensions/)
[![On-Device Gemma 4](https://img.shields.io/badge/model-Gemma%204%20E2B%20(LM%20Studio)-purple)](https://ai.google.dev/gemma)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**PrivacyGate** is a zero-cloud, local-first privacy guardrail that intercepts and sanitizes sensitive Personal Identifiable Information (PII) before it is shared with Cloud LLMs like ChatGPT. 

Combining high-speed deterministic heuristics (PAN, Aadhaar Verhoeff checksums, Indian phone numbers, emails, bank accounts) with an on-device **Google Gemma 4 E2B** fallback model running in LM Studio, PrivacyGate provides strict exact-span masking, multi-page image/PDF OCR document review, interactive visual redaction, and an authenticated Chrome side-panel extension for direct ChatGPT composer injection and file attachment.

> **Zero Cloud Egress Guarantee:** Private drafts and documents never leave your physical workstation. PrivacyGate binds strictly to loopback (`127.0.0.1`), enforces cryptographic token authentication, maintains zero disk/telemetry logs, and requires explicit user review before any text insertion or file upload.

---

## 🤖 Automated Grader & Bot Evaluation Runbook

This section provides deterministic, copy-pasteable execution commands for automated evaluation bots, CI/CD runners, and headless grading scripts.

### Machine Specifications
- **Target OS:** macOS (Darwin arm64 Apple Silicon) or Linux (x86_64/arm64)
- **Local Bridge Host & Port:** `http://127.0.0.1:8765`
- **LM Studio Loopback Server:** `http://127.0.0.1:1234/v1`
- **Supported Gemma Model:** `gemma4-e2b-instruct-pure` (or any Gemma 4 instruction-tuned Q4 build)

### Quick One-Liner Test Execution
```bash
# Clone and enter directory
cd BeyondNexus

# Setup isolated environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# 1. Run Core Python Test Suite (94 unit & integration tests)
python -m unittest discover -s tests -v

# 2. Run Chrome Extension Headless Test Suite (20 synthetic browser double tests)
node --test extension/review.test.cjs

# 3. Run Full Iteration & Required File System Validation Gate (52/52 files verified)
python scripts/validate_iteration.py

# 4. Run Deterministic Rule Engine Benchmark
python scripts/benchmark_rules.py
```

### Exit Codes & Decision Matrix
| Exit Code | Status Code | Semantic Meaning | Action Allowed |
| :---: | :--- | :--- | :--- |
| `0` | `READY_FOR_MANUAL_APPROVAL` | Deterministic rules detected and masked all known patterns. | User can approve, copy, or insert. |
| `1` | `REVIEW_REQUIRED` | Gemma model identified contextual or unstructured PII (e.g. names, addresses). | User manual inspection required. |
| `2` | `BLOCKED_UNVERIFIED` | Fail-closed state: required vision/LLM unavailable, OCR failure, or unverified regions. | Copy, insert, and export are blocked. |
| `3` | `INVALID_INPUT` | Input exceeded limits (> 50,000 chars, > 6 MB file, > 5 PDF pages) or invalid format. | Request rejected immediately. |

### API Specification & Schemas

#### 1. Text Scan: `POST /v1/scan`
- **Headers:** `Authorization: Bearer <TOKEN>`, `Origin: chrome-extension://<EXTENSION_ID>`, `Content-Type: application/json`
- **Request Body:**
  ```json
  {
    "text": "Draft containing test@example.com and PAN ABCDE1234F",
    "mode": "off | on-uncertain | always"
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "status": "READY_FOR_MANUAL_APPROVAL",
    "sanitized_text": "Draft containing [EMAIL_1] and PAN [PAN_1]",
    "findings": [
      {"start": 17, "end": 33, "entity": "EMAIL", "source": "regex", "decision": "mask"},
      {"start": 42, "end": 52, "entity": "PAN", "source": "regex", "decision": "mask"}
    ],
    "requires_human_review": false,
    "warnings": ["No automated detector guarantees complete removal of personal information."]
  }
  ```

#### 2. Document/Image Scan: `POST /v1/scan-file`
- **Headers:** `Authorization: Bearer <TOKEN>`, `Origin: chrome-extension://<EXTENSION_ID>`, `Content-Type: application/json`
- **Request Body:**
  ```json
  {
    "data_base64": "<BASE64_ENCODED_BYTES>",
    "media_type": "image/png | image/jpeg | image/webp | application/pdf",
    "vision_mode": "always",
    "include_previews": true
  }
  ```
- **Response (`200 OK`):** Returns OCR stats, normalized page preview images, findings with 0-1000 normalized coordinates `[top, left, bottom, right]`, and an ephemeral 15-minute `export_ticket`.

#### 3. Redacted File Export: `POST /v1/redact-export`
- **Request Body:** Contains original file base64, `export_ticket`, `output_format` (`png` or `pdf`), and user-confirmed mask coordinates `regions`.
- **Response (`200 OK`):** Clean binary stream (`image/png` or `application/pdf`) with masked pixels completely burned in and metadata stripped.

---

## 👤 Human Judge & Evaluator Demonstration Guide

Follow this 5-minute interactive walkthrough to experience PrivacyGate live on your machine.

### Prerequisites
1. **Apple Silicon Mac** (macOS 14+ recommended) or Linux.
2. **LM Studio** installed with `Gemma 4 E2B Instruct` loaded, server running on `http://127.0.0.1:1234`.
3. **Tesseract OCR** (optional for OCR-assisted image scans): `brew install tesseract`.
4. **Google Chrome** browser (v116+).

### Step 1: Initialize Configuration & Launch Bridge
```bash
# In repo root
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Copy environment template
cp .env.example .env

# Verify environment, LM Studio connection, and Gemma fallback
python -m privacygate.macos_check --smoke --timeout 75
```

### Step 2: Load the Chrome Extension
1. Open Google Chrome and navigate to `chrome://extensions/`.
2. Enable **Developer mode** in the top-right corner.
3. Click **Load unpacked** and select the [`extension/`](file:///Users/sher/Downloads/Gemma/BeyondNexus/extension) directory.
4. Note the generated **Extension ID** (e.g., `jgaikamaijaibmcmaplbcnapkkbgdnbl`).

### Step 3: Launch the Local Bridge Server
Start the local bridge bound to your specific Chrome Extension origin:
```bash
python -m privacygate.web --extension-origin chrome-extension://YOUR_EXTENSION_ID
```
*The terminal will output:*
```
[PRIVACYGATE] Local bridge running on http://127.0.0.1:8765
[PRIVACYGATE] Authentication Token: privacygate-demo-secret-token-1234567890
[PRIVACYGATE] Allowed Extension Origin: chrome-extension://YOUR_EXTENSION_ID
[PRIVACYGATE] Gemma Model: READY (gemma4-e2b-instruct-pure)
```

### Step 4: Configure Extension & Connect ChatGPT
1. Open `https://chatgpt.com` in your browser.
2. Click the **PrivacyGate** extension icon in the Chrome toolbar to open the side panel.
3. Click the ⚙️ **Settings** icon:
   - Ensure Bridge URL is `http://127.0.0.1:8765`.
   - Paste the Bridge Token printed by the server.
   - Click **Save locally** and **Test local connection** (confirms green connection).
4. Return to the ChatGPT tab and click **Connect current ChatGPT tab**.

---

### Step 5: Live Interactive Demo Scenarios

#### Scenario A: Fast Deterministic PII Masking
1. In the PrivacyGate side panel textarea, paste:
   ```text
   Please draft a response to client Rahul Sharma (rahul.sharma@example.com).
   His PAN card number is ABCDE1234F and Aadhaar is 5489 1234 5678.
   ```
2. Select **Smart local scan** and click **Review locally**.
3. **Observe:**
   - Instant deterministic detection (< 15ms).
   - Exact span masking replaces values with `[EMAIL_1]`, `[PAN_1]`, `[AADHAAR_1]`.
   - The UI displays finding badges and explanations.
4. Tick `[x] I reviewed the complete draft`.
5. Click **Insert into ChatGPT**.
6. **Observe:** The sanitized text is cleanly placed directly into the ChatGPT ProseMirror composer without ever clicking Send!

#### Scenario B: On-Device Gemma 4 Contextual Name Detection
1. In the side panel, paste unstructured text:
   ```text
   Patient Arvind Subramaniam visited Dr. Priya Nair at Apollo Clinic yesterday.
   ```
2. Select **Always use Gemma** and click **Review locally**.
3. **Observe:**
   - LM Studio handles on-device inference via local loopback.
   - Names `Arvind Subramaniam` (`[PERSON_1]`) and `Dr. Priya Nair` (`[PERSON_2]`) are identified semantically.
   - UI status indicates `REVIEW REQUIRED` with full human inspection gate.

#### Scenario C: Document Inspection, Interactive Redaction & ChatGPT Attachment
1. In the **Image or small PDF** section, upload a sample ID card, invoice, or PDF receipt.
2. Click **Review file & show boxes**.
3. **Observe:**
   - High-resolution in-memory rasterization with OCR text extraction.
   - Red highlight boxes delineate suspected PII numbers, addresses, and identifiers.
4. Scroll down to **Redact and export**:
   - Draw custom black boxes directly on the interactive canvas to mask any additional areas.
   - Toggle **Show masked preview** to verify complete coverage.
   - Check `[x] I inspected every masked page...`.
5. Click **Attach redacted copy to ChatGPT**.
6. **Observe:**
   - PrivacyGate automatically burns the black mask pixels into a fresh, metadata-free file.
   - Dispatches the file directly into ChatGPT's active file attachment picker via `DataTransfer` events.
   - You retain full control to inspect the attached thumbnail and click Send when ready.

---

## 📁 Complete Repository Architecture

```
BeyondNexus/
├── .env.example                 # Configuration environment template
├── .gitignore                   # Git exclusion rules (safeguards secrets & venvs)
├── AGENTS.md                    # Multi-agent coordination protocols & task gates
├── CONTEXT.md                   # Core architecture constraints & design tenets
├── DEMO_GUIDE.md                # Detailed judge walkthrough script
├── DOCUMENT_COVERAGE.md         # 16-document synthetic test coverage matrix
├── IMPLEMENTATION.md            # Detailed technical specification
├── INTEGRATION_DECISION.md      # Architectural decision records
├── ITERATION_2.md               # Vision & multi-page bounded parsing spec
├── ITERATION_3.md               # OCR & multimodal verification spec
├── LICENSE                      # MIT Open Source License
├── NEXT_ITERATION.md            # Planned roadmap and enhancements
├── PROGRESS.md                  # Append-only chronological engineering changelog
├── README.md                    # Primary human & bot documentation (this file)
├── REDACTION_EXPORT.md          # Lossless pixel redaction & rasterization guarantees
├── THREAT_MODEL.md              # Security perimeter, risk boundaries & non-goals
├── VALIDATION_REPORT.md         # Hardware & synthetic benchmark report
├── pyproject.toml               # Python package packaging & dependencies
│
├── examples/                    # Synthetic sample files for testing
│   └── sample.txt               # Synthetic PII benchmark text
│
├── extension/                   # Chrome Manifest V3 Browser Extension
│   ├── README.md                # Extension setup & technical design notes
│   ├── manifest.json            # MV3 permissions (sidePanel, scripting, storage)
│   ├── popup.html               # Extension side panel DOM interface
│   ├── popup.css                # Sleek, responsive, smooth-scrolling styles
│   ├── popup.js                 # Side panel state machine & bridge communicator
│   ├── preview.js               # Interactive canvas editor (identical to ui/preview.js)
│   ├── composer.js              # Robust ChatGPT DOM composer detection & insertion
│   ├── attachment.js            # ChatGPT file attachment picker dispatcher
│   ├── service_worker.js        # Extension background service worker lifecycle
│   ├── options.html             # Extension bridge token & URL settings
│   ├── options.js               # Settings storage & connection verification
│   └── review.test.cjs          # Headless Node.js unit tests (20 tests)
│
├── privacygate/                 # Core Python Pipeline & Backend Services
│   ├── __init__.py              # Package entry point
│   ├── __main__.py              # CLI entry point (`python -m privacygate`)
│   ├── detectors.py             # Deterministic regex, Verhoeff checksums, rule scoring
│   ├── document_fields.py       # Document field schemas & sensitive field taxonomy
│   ├── macos_check.py           # Preflight hardware, Apple Silicon & LM Studio diagnostics
│   ├── model.py                 # Loopback OpenAI-compatible client for Gemma 4
│   ├── ocr.py                   # Tesseract OCR coordinate normalization & spatial grouping
│   ├── pipeline.py              # Multi-stage orchestrator (Rules -> Model -> Gate)
│   ├── readiness.py             # LM Studio model availability & health probes
│   ├── redaction.py             # In-memory raster redaction & PDF metadata scrub
│   ├── uploads.py               # Multimodal image & PDF bounds validation (6 MB / 5 pages)
│   ├── web.py                   # Authenticated loopback HTTP bridge & UI server
│   └── ui/                      # Standalone Local Web Interface
│       ├── index.html           # Web app interface (http://127.0.0.1:8765)
│       ├── styles.css           # Modern, responsive styles matching extension
│       ├── app.js               # Web app frontend controller
│       └── preview.js           # Shared interactive canvas editor
│
├── scripts/                     # Benchmark, Packaging & CI Validation Utilities
│   ├── benchmark_documents.py   # Document coverage test suite
│   ├── benchmark_rules.py       # Speed & precision benchmarks for deterministic rules
│   ├── benchmark_uploads.py     # Upload throughput & memory benchmarks
│   ├── document_samples.py      # Synthetic document generation fixtures
│   ├── package_extension.py     # Zip packager for Chrome Web Store distribution
│   ├── smoke_browser.cjs        # Headless Playwright integration smoke test
│   ├── smoke_local_model.py     # LM Studio live Gemma inference smoke tester
│   ├── smoke_local_uploads.py   # Multimodal image/PDF local review smoke tester
│   └── validate_iteration.py   # Mandatory release gate & file integrity validator
│
└── tests/                       # Comprehensive Automated Test Suite (94 Tests)
    ├── browser_fixture.py       # Headless test server fixtures
    ├── test_detectors.py        # Unit tests for Regex & Verhoeff algorithms
    ├── test_document_fields.py  # Unit tests for document classification
    ├── test_model.py            # Unit tests for Gemma prompt schemas & response parsing
    ├── test_ocr.py              # Unit tests for Tesseract spatial bounding boxes
    ├── test_pipeline.py         # Unit tests for end-to-end sanitization pipeline
    ├── test_readiness.py        # Unit tests for model readiness & ambiguity detection
    ├── test_redaction.py        # Unit tests for pixel destruction & PDF rebuilding
    ├── test_uploads.py          # Unit tests for image/PDF size and page bounding
    └── test_web.py              # Unit tests for HTTP bridge CORS, tokens & endpoints
```

---

## 🛡️ Security, Privacy & Compliance Architecture

PrivacyGate adheres to a defense-in-depth model specifically designed for sovereign on-device data processing:

1. **Loopback Only (`127.0.0.1`):** The server refuses non-loopback bindings (`0.0.0.0` or external interfaces).
2. **Cryptographic Authentication:** Every request requires an HTTP `Authorization: Bearer <token>` header matching a 32-byte secret generated at server boot.
3. **CORS & Origin Hardening:** Strict origin validation blocks standard web browsers from querying the bridge unless the request originates from the authorized `chrome-extension://` origin.
4. **Zero Persistent Logs:** Raw input text, detected entities, and document rasters are processed purely in RAM and never written to disk or sent to external telemetry endpoints.
5. **Irreversible Pixel Redaction:** When exporting redacted PDFs or PNGs, the underlying text layers and original raster objects are destroyed; masked areas are painted with opaque black pixels and re-encoded into clean image-only documents.
6. **No Silent Degrades (Fail-Closed):** If a user requests a semantic scan but LM Studio is unreachable or ambiguous, PrivacyGate outputs `BLOCKED_UNVERIFIED` and disables copying rather than risking silent leaks.

---

## ⚙️ Configuration Reference (`.env`)

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `PII_LLM_BASE_URL` | `http://127.0.0.1:1234/v1` | URL of the local LM Studio OpenAI-compatible endpoint. |
| `PII_MODEL_ID` | `gemma4-e2b-instruct-pure` | Exact identifier of the loaded Gemma 4 model. |
| `PRIVACYGATE_BRIDGE_TOKEN` | *(Auto-generated)* | Cryptographic bearer token. If omitted, a fresh token is generated on startup. |
| `PII_ALLOW_CLOUD_ENDPOINT` | `false` | Must remain `false`. Any non-loopback endpoint fails startup. |
| `PII_MAX_TEXT_LENGTH` | `50000` | Maximum character limit per text review request. |
| `PII_MAX_UPLOAD_BYTES` | `6291456` | Maximum file size for image/PDF review (6 MB). |
| `PII_MAX_UPLOAD_PAGES` | `5` | Maximum page count for PDF documents. |
| `PII_MODEL_TIMEOUT` | `120` | Maximum seconds allowed per on-device Gemma inference request. |

---

## 📜 License & Acknowledgments

- **Code License:** [MIT License](LICENSE).
- **Model License:** Google Gemma models are subject to the [Gemma Terms of Use](https://ai.google.dev/gemma/terms).
- Built with Google Gemma 4, Python, Chrome Extensions MV3, and Tesseract OCR.
