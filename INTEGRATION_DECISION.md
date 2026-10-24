# PrivacyGate integration decision — 2026-10-24

## Decision

Use a **Chrome Manifest V3 extension plus an authenticated loopback bridge** as
the first pre-sharing integration. Keep a ChatGPT plugin as a possible later
workflow surface, not as the primary privacy boundary.

## Why the extension comes first

PrivacyGate's job is to inspect text *before* it is shared with a cloud AI. A
user-invoked browser extension can hold draft text in its own side panel, send it
only to `127.0.0.1`, and insert the sanitized draft after explicit approval.
The current extension declares access only to ChatGPT and the loopback bridge;
`scripting` runs targeted injection on explicit actions without `all_urls` access. Manifest
V3 also forbids remotely hosted extension code.

A ChatGPT plugin is useful for reusable instructions, tools, and connected
apps inside ChatGPT/Codex. It is not the right first interception boundary:
the user has already placed text into ChatGPT's composer/conversation context,
plugin availability varies by plan/workspace/surface, and automatic plugin
selection is not guaranteed on every request. A future desktop-only local MCP
app could expose PrivacyGate as an explicit tool, but it would complement—not
replace—the pre-entry browser workflow.

## Implemented prototype

- `privacygate/web.py`: loopback-only UI and authenticated `POST /v1/scan`.
- `privacygate/ui/`: local browser workbench with review-before-copy.
- `extension/`: unpacked MV3 side panel using `scripting`,
  `storage`, `sidePanel`, `clipboardWrite`, and the exact loopback host permission.
  ChatGPT insertion is user-invoked, target-checked and never submits.
  Scoped access to `https://chatgpt.com/*` is declared alongside the loopback
  host. Capture/insertion remain explicit actions; no background page collection.
- No automatic submit, request interception, cloud model call,
  telemetry, remote code, or broad host permission.
- File inspection and numbered previews are available in the side panel; file
  attachment transfer and secure redaction remain disabled.

## Not yet claimed

- Chrome Web Store packaging/review or signed distribution.
- Reliable support for every ChatGPT/editor DOM or native ChatGPT apps.
- Full network-monitor proof, penetration testing, or independent audit.
- Live Gemma 4 behavior/latency on the developer's Mac.
- A ChatGPT plugin/local MCP package.

## Primary references checked

- Chrome `scripting` and `activeTab`: https://developer.chrome.com/docs/extensions/reference/api/scripting
- Chrome MV3 service-worker/remote-code rules: https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/basics
- ChatGPT plugins overview and local-app constraints: https://help.openai.com/en/articles/20001256-plugins-in-chatgpt
