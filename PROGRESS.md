# PrivacyGate — Append-Only Progress & Agent Handoff Log

**Policy:** Agents append new entries. Never place real prompts, document contents, original PII values, API credentials or raw model responses in this file. Only record synthetic test labels and aggregate results. The latest verified status should be reflected in `CONTEXT.md` once accepted.

## Iteration 1 scope

- [x] Document architecture, source constraints, risk model and extension roadmap.
- [x] Implement rule-first email/PAN/phone/Aadhaar/account candidates.
- [x] Implement local-only Gemma adapter and exact-substring JSON validation.
- [x] Implement fail-closed statuses, span masking and CLI.
- [x] Add synthetic unit tests and validator agent.
- [ ] Validate Gemma 4 E2B live in LM Studio on developer's 8 GB Mac.
- [ ] Benchmark on annotated synthetic samples and record measured quality/latency.
- [ ] Security-review full prompt/redaction UX and run an offline network check.
- [ ] Complete GitHub repository initialization, public license submission and final demo (owner-run).
- [x] Add authenticated localhost test UI and scan-only bridge.
- [x] Add unpacked user-invoked Chrome MV3 prototype with review-before-copy/replace.
- [ ] Run extension on a local dummy textarea and one selected supported website; complete offline network proof.
- [x] Add a macOS/Apple Silicon Gemma fallback readiness command and synthetic smoke option.
- [x] Add Apple Silicon GitHub Actions coverage for Python 3.10 and 3.13.

## Iteration 2 scope - image and small-PDF review

- [x] Add memory-only PNG/JPEG/WebP normalization and local vision review contract.
- [x] Add PDF text-layer extraction, deterministic rule masking, and page rendering.
- [x] Flag PDF metadata presence and embedded-file/form/metadata-stream risks without exposing values.
- [x] Add authenticated `POST /v1/scan-file` and local file picker UI.
- [x] Enforce 6 MB, 5-page, 20-megapixel, encryption, and fail-closed limits.
- [x] Add a synthetic target-Mac image/PDF vision smoke script.
- [x] Run Gemma 4 E2B vision smoke on the target 8 GB Mac and record aggregate timing/labels (upstream `94708f8`).
- [ ] Benchmark synthetic multilingual/rotated/handwritten/metadata/form samples.
- [ ] Isolate PDF parsing/rendering in a resource-limited subprocess before public/untrusted use.
- [ ] Design and independently verify secure image/PDF redaction before enabling file export.

### 2026-10-24 — Scaffold author — Initial implementation
- Goal: runnable rules-only CLI and optional local model fallback with validation contracts.
- Files: see `IMPLEMENTATION.md` architecture table.
- Tests: generated; validation run evidence will be appended below.
- Evidence: source code and synthetic tests in this folder.
- Unverified: actual model execution, performance on Mac, real-world language/detection accuracy, browser integration.
- Next owner: local integration engineer runs LM Studio model check and records summary without private input.

### Handoff template

```markdown
### YYYY-MM-DD HH:MM TZ — Agent — Work package
- Goal:
- Files changed:
- Test commands + aggregate results:
- Model/hardware verification (yes/no):
- Residual risks / unsolved:
- Next owner/action:
```

- 2026-10-24T16:03:13+00:00 | Validation agent | PASS | files=17/17, tests=0; live local model and external integrations unverified.

- 2026-10-24T16:03:52+00:00 | Validation agent | PASS | files=17/17, tests=0; live local model and external integrations unverified.

- 2026-10-24T16:04:41+00:00 | Validation agent | PASS | files=17/17, tests=0; live local model and external integrations unverified.

### 2026-10-24 IST — Orchestrator / UX — Local UI and Chrome prototype
- Goal: add an interface for iteration-one testing and choose an extension/plugin direction.
- Files changed: `privacygate/web.py`, `privacygate/ui/`, `extension/`, tests and durable documentation.
- Test commands + aggregate results: `python -m unittest discover -s tests -v` passed 25/25 before final documentation hardening; final validator rerun follows this entry.
- Model/hardware verification (yes/no): no; LM Studio/Gemma remains unverified on developer hardware.
- Evidence: authenticated scan endpoint, exact origin checks, loopback-only bind, request limits, no request logs, UI rendered in Edge, synthetic email masking verified by automated bridge tests.
- Residual risks / unsolved: no Chrome Web Store package, token expiry, supported-site DOM test, offline network capture, native app/file uploads, or independent security audit.
- Next owner/action: run the unpacked extension on a local dummy textarea and selected website with synthetic data, then complete network/security review.

- 2026-10-24T16:13:40+00:00 | Validation agent | PASS | files=24/24, tests=0; live local model and external integrations unverified.

- 2026-10-24T16:13:51+00:00 | Validation agent | PASS | files=24/24, tests=26; live local model and external integrations unverified.

### 2026-10-24 IST — Local model integration — macOS fallback readiness
- Goal: make the optional Gemma fallback setup verifiable on the target Mac.
- Files changed: `privacygate/readiness.py`, `privacygate/macos_check.py`, startup preflight, tests and setup documentation.
- Test plan: unit-test model selection/ambiguity/non-Gemma rejection, rerun the full validator, then run `privacygate-check-mac --smoke` on the target Apple Silicon Mac.
- Model/hardware verification (yes/no): no; this Windows development host cannot certify the user's Mac or live Gemma runtime.
- Residual risks / unsolved: actual E2B latency/memory pressure and JSON compliance remain owner-run hardware checks.
- Next owner/action: run the documented command on the 8 GB Mac with Gemma 4 E2B Q4 loaded through LM Studio.

- 2026-10-24T16:16:30+00:00 | Validation agent | PASS | files=27/27, tests=31; live local model and external integrations unverified.

- 2026-10-24T16:22:21+00:00 | Validation agent | PASS | files=27/27, tests=31; live local model and external integrations unverified.

### 2026-10-24 IST — Orchestrator / upload review — Iteration 2 first slice
- Goal: locally review images and small PDFs using deterministic parsing plus Gemma vision semantics.
- Files changed: `privacygate/uploads.py`, vision adapter in `privacygate/model.py`, `/v1/scan-file`, local UI upload controls, `ITERATION_2.md`, tests and smoke tooling.
- Logic: normalize supported images in memory; cap bytes/pixels/pages; extract and mask PDF text; flag selected metadata and embedded structures without values; render every PDF page; accept only strict entity classes and optional normalized regions from local Gemma; block on unavailable/invalid vision; never export a redacted file.
- Test commands + aggregate results: full suite passed 46 tests; validator passed 31/31 required files before final validator wording update.
- Model/hardware verification (yes/no): no; live Gemma 4 image input remains unverified on the target Mac.
- Evidence: synthetic images/PDFs, blank/text-layer PDFs, metadata-value withholding, embedded attachment warning, encryption/page/size rejection, bridge authentication/origin tests, and malformed-region rejection.
- Residual risks / unsolved: in-process parser resource risk, vision false negatives/hallucinations, hidden PDF content, multilingual/handwriting quality, secure object-level redaction, and live 8 GB Mac performance.
- Next owner/action: run `python scripts/smoke_local_uploads.py` with Gemma 4 E2B loaded, then record only labels/timing and build the bounded synthetic benchmark.

- 2026-10-24T16:34:12+00:00 | Validation agent | PASS | files=31/31, tests=46; live local model and external integrations unverified.

- 2026-10-24T16:34:27+00:00 | Validation agent | PASS | files=31/31, tests=46; live text/vision model and external integrations unverified.

- 2026-10-24T16:52:23+00:00 | Validation agent | PASS | files=31/31, tests=46; live text/vision model and external integrations unverified.

### 2026-10-24 IST — Validation agent — Target Mac live Gemma fallback validation & bug fix
- Goal: set up and validate the Gemma fallback option locally on the target Apple Silicon Mac and run all test cases.
- Files changed: `privacygate/model.py`, `VALIDATION_REPORT.md`, `PROGRESS.md`.
- Bug fixed: Gemma 4 extended reasoning exhausted the `max_tokens: 350` budget in `privacygate/model.py` (reasoning consumed ~288 tokens, cutting JSON completion mid-stream and failing closed with `BLOCKED_UNVERIFIED`). Increased `max_tokens` to 1024.
- Test commands + aggregate results:
  - Unit tests: `python -m unittest discover -s tests -v` -> 46/46 PASS.
  - Validation script: `python scripts/validate_iteration.py --record` -> PASS (31/31 files, 46 tests).
  - macOS check: `python -m privacygate.macos_check --smoke --timeout 75` -> PASS (all 6 checks PASS, synthetic span completed in ~22s).
  - Local model smoke test: `python scripts/smoke_local_model.py` -> PASS (status: `REVIEW_REQUIRED`, `llm_succeeded: True`, entities: `['EMAIL', 'PERSON']`).
  - End-to-end CLI: `--mode always` and `--mode on-uncertain` both successfully detect and mask exact `PERSON` spans via `gemma_local`.
- Model/hardware verification (yes/no): YES; verified on Apple M1 (8 GB unified memory, macOS Darwin 27.0.0 arm64) using loaded `gemma4-e2b-instruct-pure` via LM Studio loopback server.
- Residual risks / unsolved: Model inference takes ~22-52s per request on 8 GB unified memory; prompt/payload cap must be respected; human approval gate remains mandatory.
- Next owner/action: Test local UI and optional unpacked Chrome extension with live fallback running.

### 2026-10-24 IST — Review — Pulled target-Mac validation evidence
- Goal: review latest Mac results and check for regressions after fast-forward pull to `29d5f1c`.
- Files changed: qualified `VALIDATION_REPORT.md` scope and token-budget evidence; this handoff entry.
- Test commands + aggregate results: `python scripts/validate_iteration.py --record` PASS (31/31 files, 46 tests, benchmark exit 0, fail-closed CLI PASS); `python -m pip check` PASS on this Windows review host.
- Evidence: upstream report records M1 8 GB live text fallback success at 22.24s and 52.74s, with output token budget raised to 1024. Text was previously 350 tokens; vision was 450, not 350.
- Model/hardware verification: reviewed upstream Mac evidence; no live Mac/model access in this review. No live image/PDF results were present.
- Risks / unfinished: vision capability, vision latency versus UI's 75s timeout (smoke uses 120s), memory pressure, UI/extension live behavior and multilingual quality remain unverified. Mac preflight smoke needs explicit `--timeout 75` because default 8s also applies to inference.
- Next owner/action: run `python scripts/smoke_local_uploads.py` on the Mac, record sanitized aggregate results, then exercise both uploads in the UI with its actual timeout. Do not mark iteration-two live vision complete based on text fallback tests.

### 2026-10-24 IST — Browser integration — ChatGPT pre-entry review panel
- Goal: provide a testable browser plugin before sharing a draft with ChatGPT. Implemented a Chrome extension rather than an in-chat skill, whose execution would be after submission.
- Files changed: extension manifest/side-panel UI/worker, ChatGPT composer adapter, synthetic JS tests, packaging script, Mac CI, setup and architecture documentation.
- Logic: private draft in panel memory -> authenticated fixed-loopback text scan -> explicit human approval -> verify active tab, conversation URL and unchanged captured composer -> insert reviewed draft without Send. Click the toolbar icon to grant temporary activeTab access; no permanent ChatGPT host permission.
- Approval guards: source/mode/config edits, target navigation, tab switch, failed rescan and late responses invalidate prior results. Unsupported/ambiguous editors fail closed with copy fallback. Draft/result values are not stored in browser storage.
- Test commands + aggregate results: `node --test extension/review.test.cjs` covers approval/race guards and synthetic textarea/contenteditable adapters; `python scripts/validate_iteration.py --record` PASS (31/31 files, 46 Python tests); JS syntax and diff checks pass. Packaging script produces a nine-file ZIP excluding tests and secrets.
- Model/hardware verification: no new live model or live ChatGPT browser validation in this work. Mac text smoke remains upstream evidence; Mac image/PDF vision remains pending.
- Residual risks: ChatGPT DOM/editor compatibility and activeTab/side-panel behavior need actual Chrome acceptance; network capture and independent security review remain pending. Existing website drafts may already be exposed; insertion exposes the reviewed text before Send. No attachment transfer or secure file export added.
- Next owner/action: follow extension/README.md on Chrome with synthetic data; record insertion without sending, changed-target/error cases and network evidence. Continue Mac upload smoke separately.

### 2026-10-24 IST — Validation agent — Target Mac live Gemma vision validation & demo milestone
- Goal: execute `smoke_local_uploads.py` and live UI upload endpoints on the target Apple Silicon Mac with Gemma 4 E2B, verify image and small-PDF vision, harden model JSON parser, and prepare judge walkthrough guide.
- Files changed: `privacygate/model.py`, `VALIDATION_REPORT.md`, `PROGRESS.md`, `DEMO_GUIDE.md`.
- Live vision evidence:
  - `python scripts/smoke_local_uploads.py` PASSED with exit code 0:
    - `synthetic_image`: `status=REVIEW_REQUIRED`, `vision_succeeded=True`, `vision_labels=['PERSON']`, elapsed 30.23s.
    - `synthetic_pdf`: `status=REVIEW_REQUIRED`, `vision_succeeded=True`, `vision_labels=['EMAIL', 'PERSON']`, elapsed 37.77s.
  - Live UI server (`http://127.0.0.1:8765`):
    - `POST /v1/scan` (rules + on-uncertain): `[PERSON_1]` masked via `gemma_local` in 22s.
    - `POST /v1/scan-file` (image/png): `PERSON` region `[174, 58, 216, 503]` identified via `gemma_vision`.
    - `POST /v1/scan-file` (application/pdf): deterministic text layer masked `EMAIL`, vision flagged both `PERSON` (`[184, 67, 305, 519]`) and `EMAIL` (`[323, 67, 414, 628]`).
- Model parser fix: hardened `_completion_json` to auto-balance unclosed outer braces when vision completions close code blocks prematurely, preventing false `LocalModelError` triggers.
- Node extension tests: `node --test extension/review.test.cjs` passes all 5 tests.
- Python unit tests: 46 / 46 PASS.
- Validator rerun: `python scripts/validate_iteration.py --record` PASS.
- Deliverables: created `DEMO_GUIDE.md` containing interactive judge demonstration scenarios and preflight instructions.

### 2026-10-24 IST — Visual review and browser integration — Numbered boxes and working local extension path
- Goal: show where suspected upload PII appears, and exercise the extension in an actual browser rather than only mocks.
- Files changed: opt-in previews in uploads/bridge, shared preview renderer in web UI and extension, extension settings/permissions/file controls, browser smoke fixtures, packaging, CI, and durable documentation.
- Visual logic: return the exact normalized PNG pixels sent to the model only when authenticated callers request `include_previews: true`; map [top,left,bottom,right] / 1000 into canvas pixels; draw numbered boxes and matching plain-language labels on each page. Unlocated findings remain explicitly listed; no regions are fabricated. Clear stale previews/results on input changes. Per-page PNG download is labelled NOT REDACTED and retains original visible content; file results cannot authorize text insertion or attachment transfer.
- Extension logic: declare narrowly scoped ChatGPT and loopback host permissions instead of relying on expired activeTab/optional permission state; still inject only on Connect/Capture/Insert clicks, with no persistent content script. Settings shows the exact extension-origin startup command and tests authentication; token/origin/busy failures have actionable messages. Side-panel image/PDF uploads use the same local endpoint and renderer.
- Additional hardening: cap PDF raster scale before native allocation; web model timeout defaults to configurable 120s/page; prompt distinguishes 12-digit Aadhaar-shaped identifiers from phone numbers without asserting correctness.
- Test commands + aggregate results: Python validator PASS (39/39 required files, 50 tests, rule benchmark and fail-closed CLI); Node unit suite 12 PASS. `node scripts/smoke_browser.cjs` PASS in isolated Edge/Chromium with actual unpacked extension and Python HTTP server: connection/token/origin, text scan and approval invalidation, full connect/scan/approve/insert controller path, isolated-world contenteditable insertion, no Send, file preview box pixel alignment, unlocated findings, actual annotated PNG download, two-page PDF previews, 320px layout, no JS page errors or unexpected test requests. Synthetic-model screenshots inspected locally.
- Model/hardware verification: browser smoke uses a synthetic vision double and simulated ChatGPT page, not live Gemma. A separate `--live-site` attempt reached Cloudflare Verify-you-are-human (Just a moment...) with no editor; no challenge bypass attempted. Target-Mac vision accuracy/latency remains unbenchmarked; actual Chrome/ChatGPT toolbar/sidebar acceptance remains pending.
- Tooling note: downloaded Chrome-for-Testing executable hit a Windows side-by-side launch error; installed Edge successfully ran the Chromium integration tests. CI now includes the deterministic browser smoke on Ubuntu with Playwright 1.62.1.
- Next owner/action: pull/reload extension v0.3.0 and allow its scoped ChatGPT permission; use Settings' command and Test local connection, then test inside the normal authenticated ChatGPT browser with synthetic content. Run Mac live upload smoke and visually compare predicted boxes with real synthetic image/PDF content before expanding scope.


- 2026-10-24T16:59:00+00:00 | Validation agent | PASS | files=31/31, tests=46; live text/vision model and external integrations unverified.

- 2026-10-24T17:06:14+00:00 | Validation agent | PASS | files=31/31, tests=46; live text/vision model and external integrations unverified.

- 2026-10-24T17:34:34+00:00 | Validation agent | PASS | files=31/31, tests=50; live text/vision model and external integrations unverified.

- 2026-10-24T17:40:08+00:00 | Validation agent | PASS | files=39/39, tests=50; live text/vision model and external integrations unverified.

- 2026-10-24T17:41:05+00:00 | Validation agent | PASS | files=39/39, tests=50; live text/vision model and external integrations unverified.

- 2026-10-24T17:42:03+00:00 | Validation agent | PASS | files=39/39, tests=52; live text/vision model and external integrations unverified.

### 2026-10-24 IST — Integration — Preserve concurrent Mac vision milestone
- Pulled/rebased onto `94708f8` after push found concurrent upstream work. Preserved both handoffs, the demo guide, live Mac image/PDF timings and JSON brace-recovery fix.
- Updated current context/checklist: basic Mac vision integration is now evidenced; broad recall/localization and five-page memory performance remain unbenchmarked. Synthetic image smoke returned PERSON but not its email, illustrating why smoke success is not complete detection.
- Parser regression guard: never repair or accept completions reported as token-truncated (`finish_reason=length`), even if partial JSON can be balanced. Preserve recovery for stopped fenced output with a missing outer brace; malformed response envelopes fail closed.
- Combined validation: 53 Python tests, 39 required files and 12 extension tests; deterministic installed-extension browser smoke passes with synthetic model/page fixtures. Live ChatGPT attempt remains blocked by Cloudflare rather than a witnessed editor failure.
- Next action: visually check the updated boxes on the target Mac with synthetic documents and verify the reloaded v0.3.0 extension in the user's normal ChatGPT browser. No need to repeat initial model setup if the running configuration is unchanged.

- 2026-10-24T17:42:45+00:00 | Validation agent | PASS | files=39/39, tests=53; live text/vision model and external integrations unverified.

### 2026-10-25 IST - Iteration 3 - OCR + rules + Gemma
- Accepted user scope: improve detection with OCR/rules/vision and benchmarks; do not skip vision based on OCR confidence.
- Implemented local Tesseract stdin/TSV adapter, exact-offset OCR rule boxes, per-page recognition summaries, separate OCR confidence, low-confidence/blank-page review, missing/failed OCR blocking and continued all-page vision. OCR transcripts stay internal.
- Strong same-type spatial agreement combines provenance; conflicting/unlocated evidence remains visible. UI and extension show sources and OCR quality; no file redaction or automatic sending.
- Added synthetic clean/blurred detection/localization benchmark, stricter live upload smoke, optional Mac OCR preflight, Mac CI native OCR gate and setup/handoff docs in ITERATION_3.md.
- Validation in progress: 66 Python tests pass; installed Edge extension + bridge/browser integration passes with synthetic OCR/model/page fixtures. Native Windows Tesseract is absent: real benchmark correctly exits 2 BLOCKED_UNVERIFIED. No native OCR accuracy or new target-Mac Gemma performance claim.
- Next action: final validator/browser rerun, push; target Mac must run native benchmark + live combined benchmark and visually inspect synthetic scanned-PDF boxes.

- 2026-10-24T19:31:32+00:00 | Validation agent | PASS | files=43/43, tests=66; live text/vision model and external integrations unverified.

- Final iteration-three local gate: validator PASS, 43/43 files, 66 Python tests, rule benchmark/CLI checks; 12 extension tests PASS. Installed Edge browser smoke rerun PASS; updated side-panel screenshot inspected. Native upload benchmark explicitly BLOCKED_UNVERIFIED (Tesseract unavailable), not counted as a passing accuracy test. Mac CI and live OCR/Gemma metrics remain pending.

### 2026-10-25 IST - Extension refinement and reviewed redaction/export
- User scope: extension optimization, redaction and export. Added ADR-015 and REDACTION_EXPORT.md with design, workflow and handoff.
- Implemented drag-to-add masks, remove/redraw, masked preview, separate explicit export approval, approval/download invalidation after edits, in-memory blob cleanup and cancellation. Extension v0.4.0 separates file review from text insertion controls and exposes Cancel review.
- Backend destructively overwrites selected pixels (outward rounding + 2px), exports fresh metadata-free PNG or lossless raster PDF; no original PDF text/form/annotation/attachment objects. Preserves rendered PDF page sizes. Signed 15-minute tickets bind completed scan to exact bytes/media and bridge instance. Failed required scans cannot authorize export. No auto-attach/send.
- Evidence: 75 Python tests and 13 extension tests PASS. Installed Edge/Chromium integration PASS with real bridge and synthetic OCR/model/page doubles, including mask edits, actual redacted PNG pixel checks, PNG/PDF downloads, two-page PDF parse/render and stale-link invalidation. Visually inspected editor and exported PDF render.
- Limits: pixels outside selected masks can retain missed PII; raster PDF loses text/search/accessibility/signatures/forms and is capped at review resolution. Target Mac live OCR/Gemma, memory/latency and normal authenticated ChatGPT acceptance remain unverified. Cancel does not kill an already-running local model call.
- Next action: final validator, package and push; user pulls, restarts bridge, reloads extension, and tests synthetic files on target Mac following REDACTION_EXPORT.md.

- 2026-10-24T19:39:32+00:00 | Validation agent | FAIL | files=46/46, tests=75; live text/vision model and external integrations unverified.

- 2026-10-24T19:39:51+00:00 | Validation agent | PASS | files=46/46, tests=75; live text/vision model and external integrations unverified.

- 2026-10-24T19:41:08+00:00 | Validation agent | PASS | files=46/46, tests=75; live text/vision model and external integrations unverified.

- Final export gate: validator PASS (46/46 required files, 75 Python tests); 13 extension tests PASS; installed-extension browser rerun PASS, including whole-page masking and approved PNG/PDF export. One initial aggregate validator invocation reported test failure without identifiers; direct suite, three captured stability runs and subsequent validators all passed. Validator now prints failing test identifiers only to make any recurrence diagnosable without logging payloads. No cause reproduced. Final package refreshed; native target-Mac/live-site checks remain pending.

### 2026-10-25 IST - Refinement and comprehensive regression pass
- Found and fixed: unhashable export format values causing connection failure, non-ASCII auth-header comparison failure, concurrent native PDFium operations, redundant export PDF parse, and mask-commit approval race.
- Added undo (20 edits), whole-page mask replacement, export MIME/nonempty checks, local UI scan cancellation/timeouts/mutual exclusion and stale-response protection. Extension version 0.4.1.
- Regression cases added for malformed API requests, PDF locking, rotated/cropped PDF alignment, JPEG EXIF mask alignment, bridge-restart ticket invalidation, undo, mid-drag approval, bad export responses and overlapping/cancelled scans.
- Inspected public CI: release 14fb186 and OCR adb6fda both completed success. Release jobs: macOS arm64 Python 3.10 and 3.13, each passing native Tesseract clean-fixture benchmark; Ubuntu installed-extension browser smoke success. No live target-Mac Gemma inference in these jobs.
- Build checks: pip check PASS; wheel builds successfully; CLI/UI/Mac preflight help commands work. Final regression counts and fresh CI result to follow.

- 2026-10-24T19:52:45+00:00 | Validation agent | PASS | files=46/46, tests=81; live text/vision model and external integrations unverified.

- Final local results: 81 Python tests PASS, 14 extension tests PASS, installed Edge browser regression PASS (synthetic OCR/model/site fixtures). pip check and wheel build PASS; extracted wheel imports outside repository, contains shared editor assets and successfully exports a masked PNG. Updated editor screenshot inspected. Source diff whitespace check clean. Fresh code CI verification follows push.

- Fresh code CI verified: 193fdae, https://github.com/yashwaghh/BeyondNexus/actions/runs/40127314596 - completed success. macOS arm64 Python 3.10 and 3.13 jobs PASS (including configured native Tesseract clean-fixture benchmark); Ubuntu installed-extension Chromium browser smoke PASS. Remaining hardware/site gates: live combined OCR/Gemma quality, latency/memory on the user Mac, and normal authenticated ChatGPT browser. No general privacy guarantee claimed.

- 2026-10-24T20:00:55+00:00 | Validation agent | PASS | files=47/47, tests=81; live text/vision model and external integrations unverified.

### 2026-10-25 IST - Extension-level integration v0.5.0
- User explicitly chose reviewed export attachment to ChatGPT. Added ADR-016; only explicit Attach transfers generated bytes, never original upload/annotated preview, and never Send.
- Added panel bridge diagnostics and exact startup command; Settings command copy and bounded connection test. Synthetic checks do not send the private draft.
- Implemented tab/conversation-bound PNG/PDF attachment via isolated-world file input assignment, unique compatible picker/fingerprint checks, existing-selection guard, MIME/signature checks, 10 MB transfer bound and download fallback. Invalidated on edits/navigation; successful assignment cannot be repeated without preparing again.
- Installed browser testing in progress: exact generated PNG/PDF bytes verified against website picker, no preparation auto-upload, Send untouched, duplicate picker and navigation rejection. Synthetic page/model/OCR; actual authenticated ChatGPT remains unverified.

- 2026-10-24T20:01:47+00:00 | Validation agent | FAIL | files=47/47, tests=81; live text/vision model and external integrations unverified.

- Integration evidence: real installed extension + bridge + isolated-world test passes exact redacted PNG and PDF assignment, no upload during preparation, duplicate compatible picker blocking and conversation-navigation invalidation; Send counter remains zero. Added unique image-specific picker preference for sites with separate image/general inputs. An auth rejection test intermittently failed once in the aggregate validator; investigating with targeted export stability runs before final gate.

- 2026-10-24T20:03:32+00:00 | Validation agent | PASS | files=47/47, tests=81; live text/vision model and external integrations unverified.

- Final local gates: 81 Python tests, 47 required files and 20 extension unit tests PASS. Five targeted export stability runs and the repeated full validator pass; intermittent prior auth rejection failure did not reproduce. Expanded installed browser integration verifies explicit PNG/PDF assignment, exact bytes, changed URL invalidation, duplicate picker fallback, synthetic bridge connectivity, approval/cancellation and file export. No authenticated ChatGPT/cloud upload acceptance claim.

- Fresh integration CI verified: f60dd19, https://github.com/yashwaghh/BeyondNexus/actions/runs/40128148479 - completed success. macOS arm64 Python 3.10/3.13 and Ubuntu installed-extension Chromium browser smoke all PASS. Synthetic PNG/PDF file assignment is automated; actual authenticated ChatGPT cloud upload acceptance and live target-Mac Gemma remain pending. Packaged v0.5.0 contains 11 runtime/docs files and adds no permissions.
