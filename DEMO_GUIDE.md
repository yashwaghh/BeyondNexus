# PrivacyGate — Judge Demonstration Guide & Milestone Walkthrough

This document outlines the **live demonstration script** and milestone capabilities for PrivacyGate: a local-first, zero-cloud PII pre-sharing guardrail powered by deterministic rules and an on-device Google Gemma 4 fallback model.

---

## 🌟 The Core Value Proposition

> **The Problem:** When employees and users interact with Cloud LLMs (ChatGPT, Claude, Gemini, etc.), they frequently paste sensitive personal data (names, emails, PAN cards, Aadhaar IDs, phone numbers, bank accounts) or upload documents/screenshots without realizing the compliance or privacy risk.
>
> **The PrivacyGate Solution:** A completely local pre-sharing defense pipeline running on Apple Silicon unified memory:
> 1. **Fast-path deterministic rule engine** (Email, PAN, Aadhaar Verhoeff checksum, Indian Mobile, Bank Account patterns).
> 2. **Local Gemma 4 E2B Fallback** via loopback LM Studio for unstructured contextual personal data (names, addresses) when regex is uncertain.
> 3. **Exact-span masking** (`[EMAIL_1]`, `[PAN_1]`, `[PERSON_1]`) preserving semantic task utility while withholding private values.
> 4. **Multimodal image and PDF review** (page-by-page in-memory rendering and Gemma vision region detection).
> 5. **Human approval gate** with cryptographic token isolation and zero cloud network egress.

---

## 🚀 Live Demo Architecture

```
[ User Input / Chrome Browser / Clipboard ]
                   │
                   ▼
     ┌───────────────────────────┐
     │  PrivacyGate Workbench    │  (http://127.0.0.1:8765)
     │  - Authenticated Bridge   │  (Bearer Token Auth)
     │  - Zero Request Logs      │  (No disk/cloud persistence)
     └─────────────┬─────────────┘
                   │
        ┌──────────┴──────────┐
        ▼                     ▼
┌───────────────┐     ┌───────────────────────────────────┐
│ Fast Regex    │     │ On-Device Gemma 4 E2B Fallback    │
│  - Email      │     │ (LM Studio on loopback :1234)     │
│  - PAN        │     │  - Contextual Name Detection      │
│  - Aadhaar    │     │  - Multimodal Vision (PNG/PDF)    │
│  - Mobile     │     │  - Hallucination Rejection Gate   │
└───────┬───────┘     └─────────────────┬─────────────────┘
        │                               │
        └──────────────┬────────────────┘
                       ▼
        ┌───────────────────────────────┐
        │ Exact Span Masking & Review   │
        │ - Status: REVIEW_REQUIRED     │
        │ - Copy button strictly gated  │
        └───────────────────────────────┘
```

---

## 📋 Pre-Flight Verification for Judges

Run this one-liner to show all system checks passing in real time:

```bash
# 1. Activate environment
cd /Users/sher/Downloads/Gemma/BeyondNexus
source .venv/bin/activate
set -a; source .env; set +a

# 2. Run the macOS & Gemma preflight smoke check
python -m privacygate.macos_check --smoke --timeout 75
```

**Expected output:**
```
[PASS] Operating system: Darwin 27.0.0
[PASS] Apple Silicon: arm64
[PASS] Python: 3.13.11
[PASS] LM Studio CLI: available
[PASS] Gemma fallback: A loaded Gemma fallback is available on loopback.
[PASS] Synthetic fallback smoke: completed in 22.24s; no raw text logged
READY: local Gemma fallback is configured.
```

---

## 🎬 5-Minute Live Demo Scenarios

### Scenario 1: Interactive Web Workbench (Visual Demo)

1. Open **[http://127.0.0.1:8765](http://127.0.0.1:8765)** in your browser.
2. In the **Source text** box, paste the following synthetic prompt:
   ```text
   Please summarize this scholarship application. My email is student@example.com,
   my PAN is ABCDE1234F, and my mobile number is +91 9876543210.
   My name is Aarav Kulkarni. Only use fields needed to explain the application.
   ```
3. Set **Scan mode** to `Rules + Gemma when uncertain` (`on-uncertain`).
4. Click **"Review locally"**.
5. **Show the judges:**
   - **Status Badge:** Changes to `REVIEW REQUIRED` (Orange badge).
   - **Sanitized Draft:** The email, PAN, and phone are masked by fast regex. The name "Aarav Kulkarni" — which regex cannot parse without context — is identified by on-device Gemma 4 and masked as `[PERSON_1]`.
   - **Approval Gate:** The **"Approve & copy sanitized draft"** button is **disabled** until the user reviews the findings list and explicitly checks *"I reviewed the entire result"*.
   - **Zero Leaks:** The raw personal data is never echoed in the findings metadata or anywhere in network logs.

---

### Scenario 2: Fail-Closed Security Demonstration

Show what happens when model analysis is turned off or unavailable:

```bash
python -m privacygate --mode off --text-file examples/sample.txt
```

**Show the judges:**
- Status: `BLOCKED_UNVERIFIED` (Exit code `2`).
- Warning: *"Possible contextual personal information not analyzed by a model."*
- **Takeaway:** The system **never silently approves** text that might contain hidden contextual PII. It fails closed to protect the user.

---

### Scenario 3: Multimodal Image & Document Review (Iteration 2)

Show that PrivacyGate inspects uploaded screenshots, photos, and PDFs locally without cloud uploading:

```bash
python scripts/smoke_local_uploads.py
```

**Show the judges:**
- **Synthetic Image:** Live Gemma 4 vision identifies the `PERSON` region `[174, 58, 216, 503]` in ~30s.
- **Synthetic PDF:** Automatically decodes in memory, extracts and masks text layer (`[EMAIL_1]`), and renders the page to run local vision for visual PII (`PERSON` + `EMAIL` regions).
- **Security:** In-memory only; no redacted file export is permitted until verified.

---

### Scenario 4: Command Line & Developer Automation

Run the comprehensive validator script to show all milestone deliverables passing:

```bash
python scripts/validate_iteration.py --record
```

**Results shown to judges:**
- **Required Files:** 31 / 31 present.
- **Unit Tests:** 46 / 46 PASS.
- **Rule Benchmark:** Precision 0.800, Recall 0.800.
- **Exit Code:** 0 (Clean pass).

---

## 🛡️ Security & Privacy Guarantees

1. **100% Local Execution:** Neither LM Studio nor PrivacyGate ever dial out to external endpoints. Local server binds strictly to `127.0.0.1`.
2. **SSRF & Proxy Defense:** Built-in `_NoRedirect` handler prevents loopback redirect attacks; proxy bypass prevents accidental corporate proxy leaks.
3. **Timing & Token Isolation:** Web UI uses high-entropy 24+ character bearer tokens and origin verification.
4. **Anti-Hallucination:** Gemma model spans are validated as exact substrings of the original input. Hallucinated spans trigger immediate fail-closed exceptions.

---

## 🏆 Milestone Summary

- **GitHub Repository:** [`https://github.com/yashwaghh/BeyondNexus.git`](https://github.com/yashwaghh/BeyondNexus.git)
- **Validation Report:** [`VALIDATION_REPORT.md`](VALIDATION_REPORT.md)
- **Implementation Status:** [`PROGRESS.md`](PROGRESS.md)
- **Target Hardware Tested:** Apple Silicon M1, 8 GB RAM, macOS Darwin 27.0.0
