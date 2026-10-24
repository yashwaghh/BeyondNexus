# PrivacyGate — Local Validation Report

**Scope of this report:** static package layout, synthetic tests, rule-only CLI behavior, authenticated local bridge, image normalization, and small-PDF parsing/rendering. **No access to the user's Mac or loaded LM Studio model; no live model inference was performed.**

## Result

- Files and documentation present: **31 / 31 required** by the validation script.
- Python unit tests: **46 passed** on the latest local run.
- CLI fail-closed smoke test: **passed** on the synthetic example.
- Rule-only synthetic benchmark: **7 sample texts**, exact-span **4 TP, 1 FP, 1 FN**; precision = **0.80** and recall = **0.80** on this **tiny artificial dataset only**. These are *not* reliability estimates.
- Loopback-only base URL checks: covered by unit tests; client additionally disables system HTTP proxies and redirects.
- Live Gemma E2B/E4B inference via LM Studio: **not tested**, must be run on target hardware.
- Local UI and unpacked Chrome extension prototype: **implemented**; supported-site and distribution validation remain incomplete.
- Image/small-PDF parsing and rendered-page vision adapter: **implemented with synthetic mocks**; live Gemma vision is unverified.
- Privacy/security certification: **not performed and not claimed**.

## Validator actions for the next team member

1. On the Mac, install dependencies, load Gemma E2B and set the exact LM Studio model ID.
2. Run `python scripts/smoke_local_model.py` and `python scripts/smoke_local_uploads.py`. Record only elapsed time, status, and detected entity categories (no PII values).
3. Run the six code-independent PII test prompts from a curated *synthetic* set; check false negatives and false positives manually.
4. Confirm process binds to loopback and no cloud AI calls occur.
5. Run `python scripts/validate_iteration.py --record` after any source changes.
6. Mark the milestone accepted in `PROGRESS.md` only after the above evidence exists.

## Known bugs/limitations to fix in future iterations

- Rules-only misses ordinary names lacking structured patterns; there is no complete contextual PII detector.
- Phone-shaped ticket IDs may be flagged; without context such candidates require review.
- Rule-only detection favors ASCII digit/formats and English context hints; other scripts require careful Unicode and locale work.
- Larger documents require parser isolation, chunking, and origin mapping; iteration two caps uploads at 6 MB and PDFs at 5 pages.
- A sanitized extracted text draft is not a securely redacted PDF; upload export is intentionally unavailable.
- LLM responses are not guaranteed valid JSON; failures deliberately block automated approval.
- Model output is untrusted; even literal substring checks do not prove that a claimed entity type is correct.
