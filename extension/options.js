const url = document.querySelector('#url');
const token = document.querySelector('#token');
const message = document.querySelector('#message');
document.querySelector('#command').textContent = `python -m privacygate.web --extension-origin chrome-extension://${chrome.runtime.id}`;
document.querySelector('#copy-command').addEventListener('click', async () => {
  try { await navigator.clipboard.writeText(document.querySelector('#command').textContent); message.textContent = 'Startup command copied. Run it in your project terminal.'; }
  catch { message.textContent = 'Copy the startup command above manually.'; }
});
document.querySelector('#test').addEventListener('click', async () => {
  const button = document.querySelector('#test'); button.disabled = true;
  const request = new AbortController(); const timer = setTimeout(() => request.abort(),8000);
  try {
    const response = await fetch('http://127.0.0.1:8765/v1/scan', {
      method: 'POST', signal:request.signal, headers: {Authorization: `Bearer ${token.value}`, 'Content-Type': 'application/json'},
      body: JSON.stringify({text: 'PrivacyGate synthetic connection check.', mode: 'off'})
    });
    if (!response.ok) throw new Error(response.status === 401 ? 'Token rejected. Paste the latest server token.'
      : response.status === 403 ? 'Origin rejected. Restart the bridge with the command above.' : `Server returned HTTP ${response.status}.`);
    message.textContent = 'Connected: token and extension origin accepted. Gemma readiness is reported in the server terminal.';
  } catch (error) { message.textContent = error.name === 'AbortError' ? 'Connection timed out. Start the local bridge using the command above.' : `Connection failed: ${error.message}. Ensure the local bridge is running.`; }
  finally { clearTimeout(timer); button.disabled = false; }
});
chrome.storage.local.get({bridgeUrl: 'http://127.0.0.1:8765', bridgeToken: ''}, values => { url.value = values.bridgeUrl; token.value = values.bridgeToken; });
document.querySelector('#save').addEventListener('click', async () => {
  const normalized = url.value.replace(/\/$/, '');
  if (normalized !== 'http://127.0.0.1:8765' || token.value.length < 24) {
    message.textContent = 'Use http://127.0.0.1:8765 and a token of at least 24 characters.'; return;
  }
  await chrome.storage.local.set({bridgeUrl: normalized, bridgeToken: token.value});
  message.textContent = 'Saved only in this browser profile.';
});
