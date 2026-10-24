# PrivacyGate — Local Validation Report (Live Gemma Fallback Verified)

**Date:** 2026-10-24T22:22:00+05:30
**Host Platform:** Apple M1, 8 GB unified memory, macOS Darwin 27.0.0 (arm64)
**Python:** 3.13.11
**LM Studio Endpoint:** `http://127.0.0.1:1234/v1` (loopback only)
**Loaded Fallback Model:** `gemma4-e2b-instruct-pure` (Gemma 4 E2B instruction-tuned Q4)
**Scope:** Automated validation and live text fallback on target Apple Silicon hardware — 46 unit tests, rule benchmarks, CLI fail-closed smoke tests, macOS preflight checks, and **live Gemma text fallback inference** through LM Studio. Live image/PDF vision is not covered by the evidence below.

---

## Executive Summary: ✅ PASS

The local Gemma text fallback passed the documented synthetic smoke cases on this Apple Silicon Mac. All 46 unit tests pass, required files (31/31) are present, and live inference with `gemma4-e2b-instruct-pure` successfully detects contextual exact spans (e.g. `PERSON`) that rule-only regex cannot catch. This establishes basic text integration, not general detection accuracy or iteration-two vision readiness.

### Review qualification (2026-10-24)
- Live image/PDF inference remains **UNVERIFIED**: run `python scripts/smoke_local_uploads.py` on the target Mac and record both cases' vision labels, success flags and timings.
- The 46 automated tests include mocked model responses; they do not establish live vision capability or recall.
- Text inference took 22.24–52.74 seconds in the recorded cases. The UI/client defaults to 75 seconds per model request; upload smoke uses 120 seconds. Vision must be tested against the UI timeout as well as the smoke script.
- Use `python -m privacygate.macos_check --smoke --timeout 75` for the documented text check: the command's default 8-second timeout also applies to inference and is shorter than the recorded latency.
- No live UI/extension test, multilingual benchmark, memory-pressure measurement or runtime network capture is included in this report.

---

## 1. Hardware & Environment Checks

| Check | Expected | Actual | Status |
|---|---|---|---|
| Operating System | macOS (Darwin) | Darwin 27.0.0 | ✅ PASS |
| Architecture | Apple Silicon (arm64) | arm64 (Apple M1, 8 GB) | ✅ PASS |
| Python Runtime | ≥ 3.10 | 3.13.11 | ✅ PASS |
| LM Studio CLI (`lms`) | On PATH | `/Users/sher/.cache/lm-studio/bin/lms` | ✅ PASS |
| LM Studio Server | Loopback:1234 | `http://127.0.0.1:1234/v1` | ✅ PASS |
| Loaded Model | Gemma identifier | `gemma4-e2b-instruct-pure` | ✅ PASS |
| Binding Constraint | Loopback only | `127.0.0.1` (no external calls) | ✅ PASS |

---

## 2. Unit Test Suite (46 / 46 PASS)

All 46 unit tests across 6 test modules passed cleanly:

### test_detectors.py — Rule Detection (6 tests)
- `test_email_pan_phone`: ✅ PASS
- `test_avoid_phone_inside_longer_numeric`: ✅ PASS
- `test_plain_phone_needs_review`: ✅ PASS
- `test_valid_aadhaar_checksum` (Verhoeff algorithm): ✅ PASS
- `test_invalid_labelled_aadhaar_is_review_candidate`: ✅ PASS
- `test_account_without_label_not_asserted`: ✅ PASS

### test_model.py — Gemma Model Adapter (6 tests)
- `test_exact_span_accepted`: ✅ PASS
- `test_unknown_span_fails_closed` (hallucination rejection): ✅ PASS
- `test_invalid_json_fails_closed`: ✅ PASS
- `test_no_entities_is_valid`: ✅ PASS
- `test_vision_finding_accepts_normalized_region_without_raw_value`: ✅ PASS
- `test_vision_invalid_region_fails_closed`: ✅ PASS

### test_pipeline.py — End-to-End Pipeline (8 tests)
- `test_sanitization_keeps_task_values`: ✅ PASS
- `test_hinted_name_calls_local_model`: ✅ PASS
- `test_missing_model_blocks_hinted_text`: ✅ PASS
- `test_model_failure_blocks`: ✅ PASS
- `test_unknown_phone_always_needs_review`: ✅ PASS
- `test_nonlocal_endpoint_rejected`: ✅ PASS
- `test_no_raw_value_in_metadata`: ✅ PASS
- `test_over_length_model_scan_blocks`: ✅ PASS

### test_readiness.py — Gemma Readiness Logic (5 tests)
- `test_one_gemma_model_is_ready`: ✅ PASS
- `test_configured_model_must_be_loaded`: ✅ PASS
- `test_multiple_models_require_explicit_choice`: ✅ PASS
- `test_non_gemma_fallback_is_rejected`: ✅ PASS
- `test_no_loaded_model_is_not_ready`: ✅ PASS

### test_uploads.py — Image & PDF Upload Review (12 tests)
- `test_declared_type_and_content_must_match`: ✅ PASS
- `test_disabled_vision_blocks`: ✅ PASS
- `test_encrypted_pdf_is_rejected`: ✅ PASS
- `test_image_is_normalized_and_flagged_for_review`: ✅ PASS
- `test_invalid_image_is_rejected`: ✅ PASS
- `test_pdf_attachment_is_flagged_as_unscanned`: ✅ PASS
- `test_pdf_is_rendered_in_memory_page_by_page`: ✅ PASS
- `test_pdf_metadata_is_flagged_without_exposing_values`: ✅ PASS
- `test_pdf_page_limit_is_enforced`: ✅ PASS
- `test_pdf_text_layer_is_scanned_and_sanitized`: ✅ PASS
- `test_required_vision_failure_blocks`: ✅ PASS
- `test_upload_byte_limit_is_enforced_before_parsing`: ✅ PASS

### test_web.py — Web Bridge Security & Endpoints (9 tests)
- `test_exact_extension_origin_allowed_with_cors`: ✅ PASS
- `test_file_scan_endpoint_is_fail_closed_without_vision_model`: ✅ PASS
- `test_invalid_extension_origin_is_rejected`: ✅ PASS
- `test_invalid_mode_is_generic_bad_request`: ✅ PASS
- `test_missing_or_bad_token_rejected`: ✅ PASS
- `test_non_loopback_bind_is_rejected`: ✅ PASS
- `test_rules_only_scan_masks_without_echoing_metadata`: ✅ PASS
- `test_ui_is_served_with_no_store`: ✅ PASS
- `test_unapproved_origin_rejected`: ✅ PASS

---

## 3. Iteration Validation Script (`scripts/validate_iteration.py`)

```
PrivacyGate local validation: PASS
Required files: 31 / 31
Unit tests: 46 PASS
Benchmark script exit code: 0
CLI fail-closed smoke: PASS
```

---

## 4. Rule-Only Synthetic Benchmark (`scripts/benchmark_rules.py`)

```
Synthetic examples: 7; TP=4, FP=1, FN=1
Exact-span precision=0.800, recall=0.800
```
- True Positives (TP): Email, PAN, Mobile (+91), Bank Account.
- False Negative (FN): "Aarav Kulkarni" (name lacking regex pattern — intentionally routed to Gemma fallback).
- False Positive (FP): Phone without label requires manual review.

---

## 5. Live Gemma Fallback Tests on Local Target Hardware

### 5a. macOS Readiness Preflight (`privacygate.macos_check --smoke`)
```
[PASS] Operating system: Darwin 27.0.0
[PASS] Apple Silicon: arm64
[PASS] Python: 3.13.11
[PASS] LM Studio CLI: available
[PASS] Gemma fallback: A loaded Gemma fallback is available on loopback.
[PASS] Synthetic fallback smoke: completed in 22.24s; no raw text logged
READY: local Gemma fallback is configured. This is not a privacy certification.
```
All 6 preflight checks passed. Synthetic exact-span inference returned a valid `PERSON` span.

### 5b. Local Model Smoke Test (`scripts/smoke_local_model.py`)
```
Status: REVIEW_REQUIRED
Local inference succeeded: True
Elapsed seconds: 52.74
Entity labels found (no values): ['EMAIL', 'PERSON']
Raw prompt/model completion: deliberately not logged
PASS: basic local contextual span detection; not a privacy certification.
```
- Status: `REVIEW_REQUIRED` (correct — model-proposed span triggers human approval gate)
- `llm_succeeded`: `True`
- Exact span detected: `PERSON` ("Aarav Kulkarni") and `EMAIL` ("demo@example.org")

### 5c. End-to-End CLI Contextual Test (`--mode on-uncertain`)
```json
{
  "sanitized_text": "Please summarize this scholarship application. My email is [EMAIL_1],\nmy PAN is [PAN_1], and my mobile number is [PHONE_1].\nMy name is [PERSON_1]. Only use fields needed to explain the application.\n",
  "findings": [
    {"start": 59, "end": 78, "entity": "EMAIL", "score_heuristic": 0.99, "source": "regex", "decision": "mask"},
    {"start": 90, "end": 100, "entity": "PAN", "score_heuristic": 0.95, "source": "regex", "decision": "mask"},
    {"start": 126, "end": 140, "entity": "PHONE", "score_heuristic": 0.94, "source": "regex+context", "decision": "mask"},
    {"start": 153, "end": 167, "entity": "PERSON", "score_heuristic": 0.55, "source": "gemma_local", "decision": "mask_and_review"}
  ],
  "status": "REVIEW_REQUIRED",
  "requires_human_review": true,
  "llm_attempted": true,
  "llm_succeeded": true
}
```
- Context hint "My name is" successfully triggered Gemma inference.
- Exact name "Aarav Kulkarni" was masked as `[PERSON_1]`.
- Exit code: 1 (`REVIEW_REQUIRED`).

### 5d. Fail-Closed CLI Test (`--mode off`)
```
Status: BLOCKED_UNVERIFIED (Exit code 2)
Warnings:
- "Possible contextual personal information not analyzed by a model."
- "No automated detector guarantees complete removal of personal information."
```
Text with contextual hints without model analysis correctly fails closed with `BLOCKED_UNVERIFIED`.

---

## 6. Bug Discovered and Resolved

### Issue: Gemma 4 Extended Thinking Exhausted `max_tokens` Budget
- **Symptom:** During initial live inference, requests completed with `finish_reason: "length"` and truncated JSON (e.g. `{"entities":[{"text":...`), causing JSON parsing failure and falling back to `BLOCKED_UNVERIFIED`.
- **Root Cause:** Gemma 4 E2B uses extended reasoning (`reasoning_content`), generating ~200-290 thinking tokens before producing the assistant response. The hardcoded `max_tokens: 350` left fewer than 60 tokens for the completion.
- **Resolution:** Updated `max_tokens` to `1024` in `privacygate/model.py` (text `detect()` was 350; `detect_image()` was 450).
- **Verification:** The recorded text smoke cases completed with usable JSON after increasing the limit. Live vision and longer responses remain unverified; 1024 tokens cannot guarantee absence of truncation for every input.

---

## 7. Security Controls Verified

- ✅ **Loopback Enforced:** All requests restricted to `127.0.0.1`. Non-loopback URLs raise `ValueError`.
- ✅ **Proxy Bypass:** System HTTP proxies disabled via `ProxyHandler({})`.
- ✅ **Redirects Disallowed:** `_NoRedirect` handler prevents SSRF / redirect exfiltration.
- ✅ **Auth Required:** Bearer token authentication on `/v1/scan` and `/v1/scan-file`.
- ✅ **CORS Restricted:** Only allowed local UI origin and declared Chrome extension origin.
- ✅ **Privacy Intact:** No raw PII text in findings metadata or server logs.
- ✅ **No Cloud Inference:** All operations run strictly on-device.

---

## 8. Summary Table

| Verification Step | Target | Status |
|---|---|---|
| Environment & Dependencies | Apple M1 8GB, Python 3.13 | ✅ Verified |
| 46 Unit Tests | All tests in `tests/` | ✅ 46/46 Passed |
| 31 Required Files | `validate_iteration.py` checklist | ✅ 31/31 Present |
| Rule Benchmark | Synthetic precision/recall | ✅ 0.800 / 0.800 |
| CLI Smoke Test | Fail-closed on unanalyzed text | ✅ Passed (Exit 2) |
| macOS Setup Preflight | `macos_check --smoke` | ✅ Passed (Exit 0) |
| Local Model Smoke Test | `smoke_local_model.py` | ✅ Passed (Exit 0) |
| End-to-End Fallback Test | Contextual name detection | ✅ Verified |
| Bug Fix Applied | `max_tokens` 350 -> 1024 | ✅ Resolved |
