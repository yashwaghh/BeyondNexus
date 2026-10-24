# PrivacyGate Chrome prototype

This unpacked Manifest V3 extension is a user-invoked companion to the local
PrivacyGate bridge. It can capture the currently focused editable field, scan
text through `127.0.0.1`, and—after explicit review—copy or replace that field.
It never clicks Send and does not claim to intercept every submission path.

## Local setup

1. Start the UI once with `python -m privacygate.web --no-model` and open
   `http://127.0.0.1:8765` to test the rules-only workflow.
2. In Chrome, open `chrome://extensions`, enable Developer mode, choose
   **Load unpacked**, and select this `extension/` folder.
3. Copy the extension ID and restart the bridge with:
   `python -m privacygate.web --no-model --extension-origin chrome-extension://EXTENSION_ID`
4. Open the extension settings and paste the bridge token printed in the
   terminal. The token is generated fresh on every start unless supplied via
   `PRIVACYGATE_BRIDGE_TOKEN` or `--token`.
5. Focus a normal text field on a local dummy page, open the extension, and use
   **Capture focused field**. Review before copying or replacing it.

For local Gemma fallback, omit `--no-model`, load Gemma in LM Studio on
loopback, and optionally set `PII_MODEL_ID` to its exact model ID.

## Intentional limits

- No `all_urls`, `webRequest`, automatic collection, submit interception, file
  upload scanning, analytics, or remote code.
- Chrome-internal pages and some sandboxed/cross-origin editors cannot be read.
- Site DOM changes can break replacement; copy is the safe fallback.
- A blocked/unverified result cannot be copied or inserted by extension buttons.
