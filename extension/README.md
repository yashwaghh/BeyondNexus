# PrivacyGate browser plugin: ChatGPT pre-entry review

Unpacked Chrome 116+ Manifest V3 extension. Click its toolbar icon to open a
side panel beside ChatGPT. Compose privately in the panel, scan through the
authenticated local bridge, inspect and approve the result, then insert it.
It never clicks Send. This is a browser extension, not an in-chat skill.

## Install on the Mac or Windows

1. From the repository root run `python -m pip install -e .`.
2. Open `chrome://extensions`, enable **Developer mode**, select **Load unpacked**,
   and choose this `extension/` directory. Reload an existing install after updates.
3. Copy its extension ID. Start the bridge from the repository root:
   ```bash
   python -m privacygate.web --extension-origin chrome-extension://YOUR_EXTENSION_ID
   ```
   For a rules-only synthetic test, append `--no-model`. For Gemma, load it in
   LM Studio first and set `PII_MODEL_ID` to its exact model ID. The server
   prints a readiness status and a private bridge token.
4. Open `https://chatgpt.com` in Chrome. Click PrivacyGate's toolbar icon.
5. In the panel's settings (gear), paste the bridge token and save. Return to
   ChatGPT and reopen the panel if necessary. The token changes on server restart.
6. Click **Connect current ChatGPT tab**. This snapshots its composer; it does
   not capture text into the private draft unless you click **Capture ChatGPT draft**.
7. Write a synthetic prompt in the panel. For a rules-only first test use
   `Summarize this message for demo@example.org.` and select **Rules only**.
8. Click **Review locally**, inspect `[EMAIL_1]` in the result, tick the review
   checkbox, then **Insert into ChatGPT**. Inspect the actual composer. Send
   manually only if desired; no sending is needed to validate this integration.
9. With Gemma ready, test `My name is Aarav Kulkarni. Summarize this synthetic ticket.`
   using **Always use Gemma**. The complete local request can take a minute.

Settings shows the exact server startup command including your extension ID.
Use **Test local connection** to validate both the token and allowed origin.
An origin error means the server needs restarting with that command; a token
error means its current token needs saving again.

If access is denied after changing tabs, click the toolbar icon again on the
intended ChatGPT tab and reconnect. The extension requests access only to
ChatGPT and the loopback bridge during installation. No background content
script reads the page; capture/insertion happen only on your clicks. You can
restrict site access in Chrome extension settings. A changed website draft requires recapture/review; it is never
silently overwritten. Unknown editor layouts fail with a copy fallback.

## Privacy boundary and current limits

- Write sensitive content in the extension first. Text typed directly into
  ChatGPT is already accessible to that website, even before clicking Send.
- Insertion makes the reviewed draft accessible to ChatGPT. It is a deliberate
  sharing step; approval does not certify absence of PII.
- Source/result text stays in panel memory, not browser storage. Settings store
  the token locally. Clear the draft when finished; clipboard copies persist
  independently. Aborting a request does not necessarily cancel model computation.
- Exact loopback URL only; no analytics, remote model, remote code or history scan.
- The side panel also reviews image/PDF uploads through the local bridge.
  Numbered boxes use the same normalized page pixels sent to Gemma. Findings
  without a reliable box are explicitly listed as location unavailable.
  You can download each annotated page as a PNG for inspection. **It contains
  the original visible private content; it is NOT redacted or safe to share.**
  File results never authorize text insertion/copy, and files are never attached.
- No automatic interception, attachment transfer, native ChatGPT app support,
  Safari support, or secure file redaction. Basic live Mac vision smoke passed;
  recall and localization quality remain unbenchmarked.
- ChatGPT composer selectors and contenteditable editing are experimental.
  Synthetic tests pass; current live ChatGPT/Chrome end-to-end verification
  remains a manual acceptance gate. Never test with real private material first.

## Verification

Run `node --test extension/review.test.cjs` (Node 18+). Tests exercise approval
invalidation, late responses, blocked/error states, origin/target checks and
editor replacement with synthetic browser doubles. Run Python validation too:
`python scripts/validate_iteration.py`.

Manual acceptance: insert synthetic text without sending; change draft while
scanning; switch tabs; navigate conversation; edit the website composer before
inserting; stop the bridge; revoke token; verify all failed/stale cases block
insertion. Inspect browser Network tools for extension-origin requests to
`127.0.0.1:8765` only. A runtime network audit is not yet recorded.

Optional package: `python scripts/package_extension.py` writes
`dist/privacygate-extension.zip`; extract it before **Load unpacked**.

Developer browser smoke: install dev-only Playwright (`npm install --no-save
--package-lock=false playwright@1.62.1` and `npx playwright install chromium`), then run
`node scripts/smoke_browser.cjs` with Python dependencies installed. This loads
the actual extension in an isolated Chromium profile, uses a synthetic local
vision model and a simulated ChatGPT page, and does not send a chat message.
It is browser integration evidence, not live Gemma quality or live-site evidence.
The optional `--live-site` flag additionally checks the current unauthenticated
ChatGPT website in a disposable profile with a synthetic masked draft. It makes
website requests and never clicks Send; Cloudflare/login restrictions can block it.
