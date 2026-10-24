# PrivacyGate — Durable Project Context (read before every iteration)

## Mission
Protect users **before** they share text/documents with cloud AI tools. Optimize for minimizing unnecessary disclosure **while preserving task utility**, not blindly deleting all numbers. Local-only inference for privacy-sensitive inspection. Open-source, auditable, human-controlled.

## Origin and non-negotiable constraints
- Hacktoberfest Hack Day 2026; organizer problem statement **#3: PII redaction for Indian documents and languages**.
- Project built from scratch in a new repository; main track requires public repo and open-source license; no real private documents in public repo.
- Mac with 8 GB unified memory; Gemma 4 **E2B** preferred through **LM Studio**; **E4B** conditional on actual hardware headroom. Model family name is *Gemma*, not Gamma/Gemini.
- Time-constrained demo. MVP = text prompts only, rule-first + optional local model + approval statuses.
- Local analysis must not send raw personal data to hosted AI services.
- No statements like 'fully safe', 'no PII remains', 'guaranteed anonymous', 'DPDP compliant'.

## Architecture decisions (ADRs)

| ID | Decision | Rationale | Revisit when |
|---|---|---|---|
| ADR-001 | Local Python regex/validation first | Fast, deterministic, testable | Robust baseline achieved |
| ADR-002 | Conditional Gemma E2B via loopback LM Studio | Cost and data locality on 8 GB hardware | More hardware or evaluation data |
| ADR-003 | Exact-span model candidates, not full-document rewrite | Prevent unrelated hallucinated edits | Stronger structured output evaluation |
| ADR-004 | Human approval required before any future external sharing | No detector proves absence of PII | Independently audited reliability |
| ADR-005 | Block if necessary model scan fails | No false green/safe status | Threat model review |
| ADR-006 | Python standard library for initial runtime | Minimal setup for hackathon | After first working demo |
| ADR-007 | Extension integration later | Browser/client internals are brittle, security-sensitive | V1 acceptance complete |
| ADR-008 | Implement a user-invoked MV3 prototype before a ChatGPT plugin | Pre-sharing review must happen before cloud chat context; `activeTab` limits access | After dummy-page and supported-site security tests |
| ADR-009 | Small uploads use deterministic PDF/text parsing plus rendered-page Gemma vision | Text extraction alone misses scanned/visual content; vision alone is untrusted | After target-Mac quality benchmark |
| ADR-010 | Iteration-two upload review produces no redacted file | Model regions and PDF overlays are not secure deletion | After verified object-level redaction design |
| ADR-011 | Use Pillow, pypdf and pypdfium2 for bounded local parsing/rendering | Cross-platform wheels and permissive PDFium bindings; avoids hosted conversion | Revisit after parser isolation/security audit |
| ADR-012 | Use extension-owned side-panel composition for ChatGPT pre-entry review | In-chat skills cannot establish a pre-submission boundary; website drafts may already be visible to the site | After live browser acceptance and packaging review |
| ADR-013 | Provide opt-in private page previews with numbered boxes and annotated PNG download | Users need to inspect model locations; annotation never constitutes redaction | After secure export design and localization benchmark |
| ADR-014 | Declare scoped ChatGPT host access; inject only on explicit user actions | Avoids expired activeTab and optional-permission setup failures for the extension's sole supported site; no all_urls or background capture | After live-site browser acceptance and permission review |

## Current implementation

- `privacygate/detectors.py`: EMAIL/PAN/AADHAAR/POSSIBLE_ID/PHONE/BANK_ACCOUNT rules.
- `privacygate/model.py`: optional localhost model client; accepts only literal substring proposals.
- `privacygate/pipeline.py`: chooses fallback, masks by character offsets, creates gate statuses.
- `privacygate/__main__.py`: CLI; no forwarding capability.
- `privacygate/web.py` + `privacygate/ui/`: authenticated loopback-only test UI; no forwarding capability.
- `extension/`: unpacked MV3 manual capture/review/copy/replace prototype; never submits.
- `privacygate/uploads.py`: memory-only image normalization and small-PDF text/metadata/render review.
- `privacygate/model.py`: strict local Gemma text and image finding adapters.
- `privacygate/web.py`: authenticated `/v1/scan-file` endpoint used by the local UI.
- `tests/`: synthetic data and fail-closed cases.
- `scripts/validate_iteration.py`: independent basic validation agent.

See `IMPLEMENTATION.md` for exact commands, confidence policy and acceptance criteria.

## V1 interface contract

Input: `review_text(text: str, mode: 'off'|'on-uncertain'|'always', model: Optional[GemmaLocalClient])`.

Output: `{sanitized_text, findings:[{start,end,entity,score_heuristic,source,rationale,decision}], status, requires_human_review, llm_attempted, llm_succeeded, warnings}`.

Metadata omits original matched values, but `sanitized_text` may still contain missed PII. Treat it as private until a user has reviewed it.

V1 statuses: `READY_FOR_MANUAL_APPROVAL`, `REVIEW_REQUIRED`, `BLOCKED_UNVERIFIED`. None means certified safe.

## Deferred scope / queue

- V2 task-aware selective minimization: `task_goal`, retain/drop recommendations and user review.
- V2 hardening of the implemented local bridge and Chrome MV3 prototype: token expiry, dummy-page/site matrix, offline network proof and security review. No guaranteed interception of every ChatGPT/Gemini/Claude request.
- Iteration 2 live Gemma vision benchmark on synthetic images/small PDFs, then parser isolation and secure export design.
- V3 larger documents, OCR benchmarks, secure PDF redaction, additional languages and person/address NER benchmarks.
- V3 existing baseline comparisons with Presidio, more robust evaluation, enterprise integration.

## Agent persistence protocol

1. Read `CONTEXT.md`, then `IMPLEMENTATION.md`, `AGENTS.md`, `PROGRESS.md`, `THREAT_MODEL.md`.
2. Make only changes assigned to the current iteration; record ADR if making a major architecture change.
3. Append a brief, sanitized entry to `PROGRESS.md`: timestamp, agent, files, test evidence, risk, next action.
4. Run `python scripts/validate_iteration.py --record`; attach summary, not private prompts.
5. Validation agent independently reviews requirements and signs off only on tested gates. Do not self-certify live LM Studio integration without running it locally.

## Open questions needing evidence

- Basic Gemma E2B text smoke passed on M1 8 GB (22-53s); general JSON compliance and detection accuracy remain unbenchmarked.
- Is a regex-only policy acceptable for certain identifiers? Needs test set.
- Chrome MV3 is the selected first target; supported-site evidence and store/distribution approach remain open.
- What Hindi/Marathi detection accuracy can we demonstrate? Not established.
- Mac synthetic image/PDF vision smoke passed (30.23s image, 37.77s one-page PDF), including regions. Recall, localization quality, memory pressure and 1-5-page latency remain unbenchmarked.

## Iteration 3 accepted scope (2026-10-25)
Local OCR + rules + Gemma vision with detection/localization benchmarks. OCR is required for upload verification; missing OCR blocks uploads. Every page still receives vision regardless of OCR confidence. See ITERATION_3.md; native target-Mac combined quality remains pending.

## Reviewed export decision (2026-10-25)
ADR-015: user authorized extension improvements, redaction and export. Use destructive raster masks and fresh lossless image-only PDFs, preserving rendered page dimensions and excluding all source PDF objects. Explicit masked-preview approval and a completed file-bound scan ticket gate local downloads; no automatic attachment/send. This supersedes the historical no-export restriction in ADR-010 for the new workflow. See REDACTION_EXPORT.md.

## Explicit extension file integration (2026-10-25)
ADR-016: user explicitly authorized an Attach button for reviewed redacted exports. Transfer only newly generated PNG/PDF bytes on an explicit click, bound to the active ChatGPT tab and exact review-time conversation URL. Never submit a message. Missing/ambiguous file pickers fail to manual download. This supersedes earlier no-attachment restrictions for this user-invoked action only. See extension/README.md v0.5.0.

## Common document refinement (2026-10-25)
User authorized expanding identification/redaction across common and standard documents. Added conservative English labelled-field recognition for uploads and PDF text layers, a 16-document synthetic matrix plus benign control, and required native OCR image/PDF benchmarking in macOS CI. This is not universal document support or an authenticity check. See DOCUMENT_COVERAGE.md for fields, evidence and limitations.
