# PrivacyGate — Iteration 1 Implementation Specification

**Version:** 0.2 · **Date:** 2026-10-24 · **Status:** Core, local test UI and unpacked extension prototype implemented; local model and supported-site integration still require testing · **Target:** Open-Source AI hackathon track

## 0. Definition of done for this iteration

Build an original, local-first, **text-only PII pre-sharing guardrail**. It must:

1. Accept text from STDIN or a UTF-8 file, without uploading it anywhere.
2. Run deterministic recognizers **first**, for email, PAN-shaped strings, Aadhaar-shaped strings with Verhoeff checksum, Indian mobile-shaped numbers, and labelled bank-account candidates.
3. Attach offsets, entity type, source, **heuristic confidence**, and rationale to candidates. Confidence values are priorities, *not calibrated probabilities*.
4. Trigger **optional** local Gemma 4 E2B/E4B fallback on ambiguous rule matches or contextual hints (`on-uncertain`), or on every short input (`always`). Rules-only mode (`off`) must work without a model.
5. Accept only exact model-proposed substrings from the original input, map them to offsets, mask in Python, and demand human review for model-proposed spans.
6. Fail closed when a required model call is unavailable/invalid, not silently mark input safe.
7. Produce sanitized text and non-sensitive inspection metadata; never print or log raw matched values in reports.
8. Include repeatable unit tests and a runnable local validation-agent script.
9. Provide a local browser test interface with explicit approval and no forwarding endpoint.
10. Provide an unpacked, user-invoked Chrome prototype that can copy or replace a focused editable field but cannot automatically submit it.
11. **Do not** automatically forward content to a cloud AI chatbot in iteration 1.

> **Critical security limit:** The system can detect some PII; it cannot prove that a prompt or document is free of PII. `READY_FOR_MANUAL_APPROVAL` is not a privacy certificate and does not authorize automatic cloud transfer.

## 1. Problem and operating assumptions

The Hack Day deck describes problem #3 as Indian-language/document PII exposure when users paste private material into cloud chatbots. We are implementing only one narrow slice of that scope: text-level pre-sharing review. Our end vision is a reusable open-source privacy layer for chatbot composition, with user-controlled minimization based on what the task actually needs. **Task-aware decisions, PDF/OCR and extension integration are deferred.**

Assumptions: 8 GB Apple Silicon Mac; LM Studio installed by user; Gemma 4 E2B 4-bit preferred; E4B on stronger hardware; Python 3.10+; 1–4 contributors; no raw personal data in source control. No model fine-tuning, embeddings, RAG or external API calls required.

## 2. Architecture and data flow

```text
User input (text, currently STDIN or UTF-8 file)
    |
    v
Input length + encoding checks
    |
    v
Rule detection: regex, context rules, checksum validation
    |
    +--> High-confidence candidate ----+
    |                                   |
    +--> Uncertain candidate / hints --> local LM Studio /v1/chat/completions
    |                                   |   (optional, 127.0.0.1 ONLY)
    |                                   v
    |                           Validated exact-substring model spans
    |                                   |
    +-----------------------------------+
                      |
                      v
             Merge non-overlapping spans
                      |
                      v
           Python exact-offset replacement
                      |
                      v
   Sanitized draft + findings (no raw matched values)
                      |
                      v
         Approval gate (manual review only)
                      |
                      v
              Local review UI / manual extension action
```

**Trust boundary:** Raw content may enter local Python and the local LM Studio instance; it must **never** be sent to hosted APIs, analytics or unapproved extensions. LM Studio should listen on loopback, not LAN. Python rejects non-loopback endpoint URLs.

### Components

| File | Responsibility |
|---|---|
| `privacygate/detectors.py` | Regex candidates, Verhoeff verification, context-based scores, span overlap resolution |
| `privacygate/model.py` | LM Studio loopback-only client, model JSON parsing, exact-substring checks |
| `privacygate/pipeline.py` | Sequential policy, fallback decision, status/warnings, sanitized output |
| `privacygate/__main__.py` | CLI integration and output/exit statuses |
| `privacygate/web.py`, `privacygate/ui/` | Authenticated loopback test UI and scan-only bridge |
| `extension/` | Manual Manifest V3 capture/review/copy/replace prototype |
| `privacygate/readiness.py`, `privacygate/macos_check.py` | macOS/Apple Silicon and loaded-Gemma fallback preflight with optional synthetic inference |
| `tests/` | Regression tests for patterns, gating, failure and allowed local networking |
| `scripts/validate_iteration.py` | Reproducible integration gate and optional PII-free work-log entry |
| `CONTEXT.md`, `AGENTS.md`, `PROGRESS.md` | Persistent handoff context and validation records |

## 3. Environment and folder setup

```bash
# macOS Terminal, from the extracted project directory
cd PrivacyGate_Iteration_1
python3 --version                    # should show 3.10 or newer
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .          # optional CLI command alias `privacygate`
cp .env.example .env
```

The core uses only Python standard libraries. This deliberately avoids heavyweight spaCy/Presidio dependencies until the local pipeline works. Presidio is a candidate baseline for later benchmark work, not a mandatory runtime component. You may compare against it without claiming the same functionality.

### LM Studio setup (optional for rules-only smoke test)

1. Install LM Studio from the vendor's official site; open **Developer > Local Server**.
2. Download **Gemma 4 E2B Instruct**, preferably a supported 4-bit GGUF/MLX packaging. On 8 GB unified memory start with E2B; E4B may be too constrained. Choose the precise instruction-tuned model you see available.
3. Load the model, try a 2k–4k context configuration, start the server. The OpenAI-compatible endpoint is usually `http://127.0.0.1:1234/v1`.
4. In terminal, inspect loaded model identifiers:

```bash
curl -s http://127.0.0.1:1234/v1/models
```

5. Write the **exact** returned loaded model ID to `.env` as `PII_MODEL_ID=...`. Source the file with `set -a; source .env; set +a` (do not commit `.env`). If exactly one model is available, the adapter can auto-select it.
6. Run the fallback example below. When running local inference, monitor Activity Monitor for memory pressure and swap. Compare thinking enabled vs disabled on your machine.

**Do not use** `https://...`, other hosts, public proxies or Google-hosted Gemini API for privacy inspection in V1. Gemma is the local model family; **Gemini API is a different execution path**.

### Smoke-test commands

```bash
# Baseline rules-only; does not call LM Studio
python -m privacygate --mode off --text-file examples/sample.txt

# Fallback if ambiguous or contextual trigger appears (uses local Gemma)
python -m privacygate --mode on-uncertain --json --text-file examples/sample.txt

# Always attempt local semantic scan of a short input
printf 'My name is Aarav Kulkarni' | python -m privacygate --mode always --json

# Tests and validator
python -m unittest discover -s tests -v
python scripts/validate_iteration.py --record

# Local browser interface (rules-only)
python -m privacygate.web --no-model

# On the target Mac after loading Gemma in LM Studio
python -m privacygate.macos_check --smoke
```

**CLI status codes:** `0` ready for **manual** approval, `1` needs human review, `2` blocked because semantic checks failed/incomplete, `3` invalid input/config. A nonzero exit is expected for some examples and must not be mistaken for a crash.

## 4. Rule engine details

| Type | Typical detection | Additional checks | Policy |
|---|---|---|---|
| `EMAIL` | ASCII address format | boundaries, basic domain suffix | High priority auto mask |
| `PAN` | 5 letters + 4 digits + 1 letter | boundaries, case-insensitive | Auto mask as *PAN-shaped*, no issuance verification |
| `AADHAAR` | 12 digits optionally grouped 4-4-4, starting 2–9 | Verhoeff check digit; labelled failures become `POSSIBLE_ID` | Valid-format auto mask; invalid labelled value review |
| `PHONE` | Indian 10-digit mobile starting 6–9, optional +91 | nearby mobile/contact keyword | Mask, review if no context |
| `BANK_ACCOUNT` | Labelled plausible 9–18 digit sequence | requires account/acct/a/c label | Mask and require human confirmation |
| `PERSON`, `ADDRESS`, `OTHER_PII` | **Not regex-complete** | Local Gemma exact-substring suggestions | Mask and review; never auto-certify |

**Important:** Account numbers have no single universal bank-wide checksum; many 9–18 digit numbers are unrelated to bank accounts. Phone-shaped numbers may be identifiers. Even Aadhaar checksum validation is not evidence a number belongs to someone.

### Fallback decision tree

```text
mode == off            => never call model
mode == always         => call model for text <= 1200 chars
mode == on-uncertain   => call model if any rule candidate score < 0.90
                          OR a contextual cue is present (e.g. 'my name is', 'address')
otherwise              => rules only; warn that semantic detection was NOT performed
```

**Known recall limitation:** Names without cues, unusual languages, emails with uncommon syntax, formatted phones, scanned image text and indirect identifiers may be missed in `on-uncertain`. With `always`, the model may still miss PII. Extend the cue library only with tests; do not declare that all texts are screened for context in the default mode.

### Span fusion

`Finding = {start, end, entity, confidence, source, rationale}`; use zero-based half-open character offsets in the original Unicode string. A model suggestion is accepted **only if its proposed text literally occurs in the input**. Reject malformed JSON, unknown categories, missing/imaginary text or excess output. Merge overlapping spans deterministically (longest first, then confidence) and mask right-sized spans by Python, not a generative rewrite. Model confidence is not trusted or used as a probability.

### Status contract

- `READY_FOR_MANUAL_APPROVAL`: No known ambiguous finding or required-model failure. **Not** 'no PII', 'safe', or 'ready to transmit automatically'.
- `REVIEW_REQUIRED`: At least one ambiguous/modeled span was masked, but a human must check correctness and usefulness.
- `BLOCKED_UNVERIFIED`: Required local model was missing, failed, returned invalid JSON, or input exceeded the configured semantic scan budget. No automatic downstream sharing.

A future GUI should have an explicit **Approve sanitized draft** action; no auto-send button should unlock purely because the status says `READY_FOR_MANUAL_APPROVAL`.

## 5. Data minimization and privacy boundaries

V1 is conservative and does **not** reason about user task necessity. Thus it can redact useful fields (e.g., beneficiary name, payment reference) and miss unstructured information. Planned V2 will introduce `(task, purpose, protected_fields_policy)` as inputs, but must preserve deterministic high-risk rules and user control. Never let Gemma alone decide whether a verified secret may be transmitted.

* No remote inference or cloud telemetry.
* Do not log document text, raw identifier strings, prompts, or model completions.
* CLI stdout is sanitized draft, **not certified clean**; handle it as sensitive.
* Use ephemeral in-memory processing; do not store the raw user input or model output as a file by default.
* Synthetic examples only; add `private_samples/` to ignore list.
* Existing application uploads are out of scope; no transparent traffic interception is implemented.

## 6. Validation matrix / acceptance checks

| Gate | How to verify | Exit condition |
|---|---|---|
| File layout | `python scripts/validate_iteration.py` | All required files exist |
| Regex correctness | Unit tests | PAN, email, +91 phone, Aadhaar checksum and account label recognized |
| Ambiguous handling | Unit tests | Unlabelled phone requires review; labelled invalid ID not accepted as valid |
| Data preservation | Unit test | Unrelated budget number remains unchanged |
| Fail-closed model | Unit test with failed mock | `BLOCKED_UNVERIFIED` |
| Local-only networking | Unit test | Remote base URLs rejected |
| Span/output integrity | Unit tests + manual comparison | Correct placeholders, zero original matched literals in metadata |
| Actual LM Studio E2B | Developer on their Mac | Model loads, exact-substring JSON obtained, fallback uses loopback |
| Runtime metrics | Manually collected sample set | Median/p95 inference time, detection recall, false positives recorded |
| Privacy posture | Manual security review | No raw logs, no outbound cloud request |

Run `python scripts/validate_iteration.py --record` to append a sanitized validation status to `PROGRESS.md`. **The validator does not and cannot certify that unknown PII was caught.** The local-model integration is explicitly unverified until you run it on your Mac.

### Proposed manual benchmark

Build a `private_samples/` test dataset of 30–50 synthetic inputs with manually annotated spans, including benign numbers, emails, PAN-shaped literals, valid/invalid Aadhaar-format test strings, labelled accounts, surnames, English/Hindi/Marathi examples. No real people's IDs. Compare rules-only and fallback, record **span precision/recall**, false-negative counts, median time and task-relevant information retained. Require external human review of claims; no fabricated scores.

## 7. What can break / countermeasures

| Failure | Countermeasure |
|---|---|
| LM Studio stops, times out, or returns junk | `BLOCKED_UNVERIFIED`; explicit error without raw request logs |
| Prompt injection inside source text | Treat input as data, reject non-JSON/extraneous model output, strict span verification; remains residual risk |
| Regex matches harmless number | Lower confidence, queue human review |
| Model proposes nonexistent name | Reject span, block on invalid response |
| Same identifier appears multiple times | Map all exact occurrences; stable masked placeholders per occurrence in V1 |
| Unicode and language issues | Document English-first limitations, test one additional script before claiming coverage |
| Model text too long | Skip and block; future chunking with offsets |
| Export leaks metadata | V1 exports text only; future formats require flattening/metadata sanitization |
| User mistakes no detections for safety | Never label 'PII-free'; require explicit human approval |

## 8. Allocation across agents (see AGENTS.md)

- **Integrator:** ensure package imports, CLI and local model run.
- **Rule engineer:** maintain regex, validators, edge-case tests.
- **Model engineer:** manage LM Studio response schema/latency, handle failure.
- **Security and validation agent:** review threat boundaries, run validator, independently test bypass/negative cases.

Each agent logs scope, files changed, evidence/test outcomes and next steps in `PROGRESS.md` without raw data. Validator must rerun after changes. A plan is not accepted simply because a coding agent says it is done.

## 9. Handoff to next iteration

Only after V1 acceptance, implement a **user-consented local bridge + browser extension**; see `NEXT_ITERATION.md` for milestones, API contract, permission model and genuine limitations around ChatGPT and other web interfaces. Future requirements: task-aware selective minimization, extra recognizers, PDF/DOCX/OCR, telemetry-free local UI and safe export. Update `CONTEXT.md` and `PROGRESS.md` on each iteration; do not rewrite the history log.

## 10. Primary technical references (verified 2026-10-24)

- LM Studio loopback server: https://lmstudio.ai/docs/developer/core/server
- LM Studio OpenAI-compatible endpoints: https://lmstudio.ai/docs/developer/openai-compat
- Gemma 4 overview/hardware: https://ai.google.dev/gemma/docs/core
- Gemma 4 model card/licensing: https://ai.google.dev/gemma/docs/core/model_card_4
- Chrome extension permissions: https://developer.chrome.com/docs/extensions/mv3/declare_permissions
- Microsoft Presidio supported recognizers: https://microsoft.github.io/presidio/supported_entities/

**Scope evidence:** Organizer deck p.20/problem #3 states people paste private documents containing names, IDs and account numbers into cloud chatbots; the deck's 'What to build' cells have mismatches, so we rely on problem title and stated problem. The model/interface roadmap beyond this problem statement is an engineering proposal.

### Additional local quality checks

```bash
python scripts/benchmark_rules.py       # intentionally tiny synthetic baseline, NOT a real-world accuracy estimate
python scripts/smoke_local_model.py      # requires running LM Studio; outputs only labels/timing
```

`smoke_local_model.py` must run on the developer's Mac with Gemma E2B loaded. A pass there only verifies one contextual demonstration, not reliability across formats. The benchmark includes an expected failure for names in regex-only mode to make this limitation visible.

## Iteration 3 implementation supplement
See ITERATION_3.md for the accepted OCR pipeline, separate recognition/rule confidence, evidence grouping, failure states, benchmark definitions and target-Mac acceptance commands. Earlier iteration-two descriptions without OCR are historical.
