# PrivacyGate — Browser / Chat Application Integration Roadmap

**Status:** PROTOTYPE IMPLEMENTED, HARDENING INCOMPLETE. A scan-only bridge, local UI, and unpacked user-invoked Chrome MV3 prototype now exist. Do not claim supported-site or distribution readiness until the remaining acceptance tests pass.

Image and small-PDF work has moved into the active iteration-two contract in
`ITERATION_2.md`; this document remains the browser-integration roadmap.

## Goal

Provide a user-initiated, open-source privacy review **before** text is placed into a web chatbot such as ChatGPT. The browser extension should communicate with a **local-only** PrivacyGate process, display sanitized candidates and policy warnings, and let the user approve a copy/insert action.

Do **not** claim that arbitrary browser extensions can reliably intercept every send request in ChatGPT, native ChatGPT applications or every chat service. Website internals can change, file uploads may follow separate paths, and extension APIs have permission limitations. Official ChatGPT plugins/connectors are not the same as third-party browser extensions and should not be conflated.

## Milestones / acceptance criteria

### V2-A: Stable core bridge (localhost HTTP API) — prototype complete

**Build** `privacygate/bridge.py` (suggested FastAPI/uvicorn or conservative stdlib HTTP implementation). Expose only `POST /v1/scan` for plain text and `GET /health`; use the same V1 result JSON. Do not persist inputs.

- Bind `127.0.0.1` only; reject `0.0.0.0` and LAN IPs.
- Require short-lived locally generated bearer token for scan requests. Never place tokens in a web page DOM or query string.
- Implement explicit CORS allowlist for extension ID/origin and authenticated browser extension messaging; reject unauthorized web origins. **CORS alone is not authentication.**
- Reject oversized payloads, limit concurrency, disable disk request logs, forbid outbound proxy forwarding.
- Expose `scan` only; **do not provide an endpoint that forwards raw text to an AI service**.
- Tests: unauthenticated, wrong origin, CSRF-style requests, payload size, invalid UTF-8, model failure, repeat token expiry, malformed input.

### V2-B: Chrome Manifest V3 extension (manual workflow) — prototype complete

Suggested directory: `extension/manifest.json`, `service_worker.js`, `sidepanel.html`, `sidepanel.js`, `content_script.js`, `styles.css`, and tests. The extension should only request minimum browser privileges needed (e.g. `activeTab`, `scripting`, `storage` if necessary, `sidePanel` optional). Avoid broad host permissions when possible; local bridge origin may need an explicitly scoped permission.

The implemented version uses a side panel, a worker that configures toolbar
opening, and on-demand `chrome.scripting` calls. No persistent content script
collects drafts. The ChatGPT adapter targets one visible composer and checks
its text and conversation before insertion. Live browser acceptance is pending.

**MVP user journey:**
1. User writes or pastes a prompt in the extension's side panel or manually selects text from a website and invokes PrivacyGate.
2. Extension sends data **only** to loopback bridge over authenticated, permission-scoped messaging.
3. User sees matches, model-confidence limitations, remaining warnings and a sanitized draft.
4. User explicitly chooses `Review & Copy sanitized text` or `Insert sanitized draft into current composer`.
5. Extension replaces only the chosen composer content, never clicks the application's Send button.
6. On bridge error or unknown DOM, do not insert or transmit anything; provide local copy-only fallback.

**ChatGPT integration claim:** A browser extension operating alongside the ChatGPT *website* may offer user-invoked paste/replace; it is not necessarily a supported ChatGPT plugin. The native app, file uploads, Voice mode and other sites require separate research and testing. No guaranteed pre-send interception.

**Do not** build automatic DOM submit interception first. It can be bypassed by keyboard shortcuts, file uploads, changed React event handling, service workers or other UI paths. It may also mislead users that every submission is protected.

### V2-C: Task-aware selective redaction

Extend request schema to:

```json
{
  "text": "...",
  "task_goal": "summarize salary trends without employee names",
  "policy": "conservative",
  "allowed_entity_types": [],
  "user_approved_exceptions": []
}
```

The model **suggests** task relevance, rather than independently allowing sensitive data through. Deterministic high-risk rules stay enforced unless user explicitly confirms an exception in a clear UI, with risk warning. Measure whether tasks remain answerable and the number of unnecessary disclosures reduced.

### V3: Document support and connectors

- DOCX/PDF text extraction with offsets and metadata hygiene.
- OCR for photographed/scanned pages, language benchmarks (Hindi/Marathi).
- True secure PDF redaction rather than overlays.
- Reproducible benchmark against existing PII tools (e.g. Presidio), with synthetic data.
- Optional integration with other chat tools through their documented extension/API surfaces; each service has different constraints.

## Bridge API response contract (proposed, unchanged semantics)

```json
{
  "sanitized_text": "Hello [PERSON_1]",
  "findings": [{"start": 6, "end": 10, "entity": "PERSON", "score_heuristic": 0.55, "source": "gemma_local", "decision": "mask_and_review"}],
  "status": "REVIEW_REQUIRED",
  "requires_human_review": true,
  "llm_attempted": true,
  "llm_succeeded": true,
  "warnings": ["Review unverified spans before copying"]
}
```

Positions and text here are illustrative; actual UI may display a human-readable label without exact raw substrings. Minimize bridge logs and ensure extension output never reveals original PII to the website before approval.

## Definition of integration complete

- Demonstrate the full flow on a local dummy textarea page with synthetic text.
- Demonstrate manual sanitization on one supported website without automatic send.
- Prove no cloud network requests originate from the extension/bridge prior to user approval.
- Test wrong-website selection, wrong composer, missing bridge, large prompt, model timeout and page DOM changes.
- Pass security review of token lifetime, origin restrictions, permissions and failure behavior.
- Record evidence in `PROGRESS.md`, then update `CONTEXT.md` and `IMPLEMENTATION.md` for the new iteration.

## Outside scope / do not promise

Automatic capture of ChatGPT desktop/native input, guaranteed blocking of every chat message, interception of every upload, universal DOM compatibility, prevention of screenshots, device malware detection, certified compliance, perfect PII detection or zero false negatives.

## References

- Chrome MV3 permissions: https://developer.chrome.com/docs/extensions/mv3/declare_permissions
- Chrome scripting/activeTab: https://developer.chrome.com/docs/extensions/reference/api/scripting
- LM Studio local server: https://lmstudio.ai/docs/developer/core/server
