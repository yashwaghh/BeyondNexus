# PrivacyGate — Threat Model & Residual Risks

**Trust goal:** reduce accidental disclosure when a user prepares input for a third-party AI chat. The local pipeline is not an anonymity or security guarantee.

## Assets and trust boundaries

| Asset | Location | Threat |
|---|---|---|
| Original prompt/document | Local process memory, source file | Unnecessary disclosure, logs, accidental file persistence |
| Detected PII spans | Local process memory | Logs or reports reconstruct identifiers |
| Local model requests | LM Studio loopback | Accidental LAN/cloud routing; model echoes sensitive text |
| Sanitized draft | Stdout / future UI | Missed PII, unreviewed sharing |
| Browser integration (prototype) | Extension and page | Host permissions, cross-origin leaks, external access, bypasses |
| Image/PDF upload | Local process memory | Parser exploits, decompression bombs, hidden content, metadata/attachment leaks |
| Rendered page sent to Gemma | LM Studio loopback | Model misses, hallucinated regions, prompt injection embedded in image |

## Attack and failure cases

1. **False negative:** unrecognized name, indirect identifier, novel account format. Countermeasure: explicit warning, review, curated benchmarks, later task-aware scanning. Residual: inherently possible.
2. **False positive:** ordinary number masked as phone/account, reducing utility. Countermeasure: heuristics and human review; task-aware minimization deferred.
3. **Prompt injection:** input contains instructions such as 'ignore previous instructions'. Countermeasure: prompt treats input as data, exact substring JSON validation, no tool execution; does not fully prevent manipulation.
4. **Model unavailable or malformed response:** block auto-forwarding; still show masked candidate draft for review.
5. **Endpoint exfiltration:** reject base URLs outside HTTP loopback; no remote fallback. LM Studio must be bound to 127.0.0.1/localhost and not exposed to LAN; test runtime host settings.
6. **Data leak in logs:** never persist original text, model response, matched literal or screenshots containing IDs. CLI output is sanitized draft but remains sensitive; do not copy into issue trackers.
7. **Misleading approved status:** statuses do not mean 'PII-free'. User must explicitly approve in future UI even when automated checks pass.
8. **Unsafe document redaction:** V1 only outputs modified text. PDF overlays do not constitute permanent removal. Secure document export needs separate implementation and hidden-metadata checks.
9. **Local malicious process:** other code on the same Mac may access local services. The prototype uses bearer-token authentication, exact origin controls, loopback binding, request-size/concurrency limits and no request logs. Token expiry and independent penetration testing remain open.
10. **Browser DOM changes:** input targets change; extension must fail closed/disable injection rather than inserting content into the wrong field.
11. **Extension overreach:** avoid `all_urls`, broad webRequest interception and background collection. Prefer user-triggered permissions (`activeTab`) and review-before-insert.
12. **Unicode confusion:** unusual scripts/normalized digits may bypass ASCII rules. Document which scripts are supported; add tests before claiming Indian-language coverage.
13. **Overlapping models:** overlapping regex/model spans can mask more or less than intended; deterministic longest-match merge still needs evaluation.
14. **Malicious upload:** malformed PDFs/images may target native parsers or exhaust resources. Current byte/page/pixel limits reduce but do not eliminate risk; public/untrusted deployment requires process isolation and OS resource limits.
15. **Incomplete PDF view:** rendered pixels can omit hidden layers, prior revisions, attachment contents, JavaScript, metadata or stale form values. Structural warnings and no-export policy keep these files in manual review.
16. **Unsafe visual redaction:** a bounding box or overlay can leave underlying pixels/text recoverable. Iteration two does not generate redacted files.
17. **Vision hallucination/miss:** Gemma regions and entity labels are uncalibrated. Strict JSON validation prevents malformed data from being trusted, but cannot establish recall.
18. **Annotated preview mistaken for redaction:** opt-in preview responses contain normalized source pixels, and downloaded annotated PNGs still reveal identifying content. Display an explicit NOT REDACTED notice and never attach them automatically. Exclude these responses/downloads from logs and public reports.

## Data retention policy (V1)

- No telemetry, database, analytics, raw input logging or upload.
- No automatic report files with source text.
- Process one input synchronously and discard Python objects on process exit.
- Use only fabricated identifiers in tests and README examples.
- `private_samples/`, `.env`, `reports/` are gitignored.
- Developers must verify LM Studio privacy/settings independently.

## Security sign-off checklist

- [ ] `python scripts/validate_iteration.py` passes
- [ ] Actual LM Studio bound to loopback
- [ ] Network monitor confirms no hosted model calls on smoke test
- [ ] Text containing an explicit person-name cue is not cleared when model is unavailable
- [ ] Ambiguous numbers demand review
- [ ] No raw PII in error logs or JSON finding metadata
- [ ] Human inspects sanitized draft before external sharing
- [ ] Known limitations appear in README and demo

Status: implementation-oriented threat model; **not** a security audit or independent certification.

## Iteration 3 OCR risks
OCR can misread identifiers with high confidence or miss whole regions; recognition confidence is not a privacy probability and never bypasses vision. Default English does not establish multilingual coverage. Local Tesseract is an additional native parser/subprocess with a 30-second timeout; output/word limits are validated after capture, not OS-enforced memory isolation. No shell or application-created transcript/image files; transcripts stay internal and subprocess diagnostics are discarded. Executable/language environment configuration is trusted local configuration. Failure blocks uploads. Boxes, including OCR-derived boxes, remain review guidance and annotated exports retain original pixels.

## Reviewed raster exports
A new authenticated export endpoint rebuilds files from rendered pixels after destructive black masks; no source PDF object/text/metadata/attachment is copied. Signed file-hash/media/expiry tickets prevent completed scans being reused for different bytes and expire in 15 minutes or on restart. Required-scan failures issue no ticket. Unlocated/missed information can survive outside user masks: explicit all-page masked-preview approval remains mandatory in the UI and does not prove privacy. Source and generated bytes are memory-only on the bridge; actual downloads persist on user disk. Original annotated PNG links are still NOT redacted. Raster export intentionally removes PDF interactivity, signatures, searchability and accessibility. Native parser/process memory isolation and independent audit remain pending.

## Concurrent PDF processing
All application PDFium creation/render/dimension/close operations share one process-wide lock. The two-request HTTP semaphore alone does not protect this non-thread-safe native library. Rendering and export dimensions use one shared entry point; model/OCR inference runs outside the lock. Native process isolation and memory limits remain separate pending work. Export response MIME/size checks, commit-time mask approval revocation and invalidation prevent stale or malformed downloads from being presented as current reviewed results.

## Explicit website file transfer
The user-authorized Attach action crosses the local-only review boundary by passing only the generated reviewed raster export to ChatGPT. Preparation/download never auto-attaches. Bind to the exact active tab/conversation captured before file review; recheck before injection and inside the page. Unique compatible input and matching picker fingerprint are mandatory; existing selections block replacement. Transfer uses generic filenames, strict PNG/PDF signatures/types and a local 10 MB bound. No Send, persistent content script or extra permission. Mask/input/tab/config changes invalidate prepared attachment state. Once file input events fire, the site may upload immediately; cancellation cannot retract it. Picker assignment is not server upload acceptance, and missed PII outside masks remains a risk.

## Upload identifier recall refinement
Checksum failures cannot establish that an upload identifier is harmless: OCR substitutions and lost labels cause false negatives. Conservative upload-only shape rules now produce masks despite these uncertainties and recover spatially separated groups. False positives on other 12-digit references are possible; human review remains required. This does not establish real-card recall, QR decoding, or multilingual accuracy.

## Common document field rules
Labelled-field candidates cover English printed names, DOB, addresses, selected document/customer/account IDs, health and financial fields. Labels/values can be missed or misread; unlabelled fields, multilingual layouts, handwriting, signatures, QR data and MRZ decoding have no newly verified deterministic coverage (MRZ-shaped lines are conservatively flagged). Business/institution fields can be conservatively masked. PDF text-layer candidates without geometry require manual masks; no regions are fabricated. Benign date/amount controls reduce indiscriminate masking but do not establish false-positive rates. Early rejected HTTP POST bodies are discarded without parsing in bounded chunks (9 MB maximum, 250 ms total wait) so Windows clients can receive errors before socket closure; authorization still precedes scanning.
