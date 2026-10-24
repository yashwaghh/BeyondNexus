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
