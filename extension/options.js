const url = document.querySelector('#url');
const token = document.querySelector('#token');
const message = document.querySelector('#message');
document.querySelector('#command').textContent = `python -m privacygate.web --extension-origin chrome-extension://${chrome.runtime.id}`;
document.querySelector('#test').addEventListener('click', async () => {
  try {
    const response = await fetch('http://127.0.0.1:8765/v1/scan', {
      method: 'POST', headers: {Authorization: `Bearer ${token.value}`, 'Content-Type': 'application/json'},
      body: JSON.stringify({text: 'PrivacyGate synthetic connection check.', mode: 'off'})
    });
    if (!response.ok) throw new Error(response.status === 401 ? 'Token rejected. Paste the latest server token.'
      : response.status === 403 ? 'Origin rejected. Restart the bridge with the command above.' : `Server returned HTTP ${response.status}.`);
    message.textContent = 'Connected: token and extension origin accepted. Gemma readiness is reported in the server terminal.';
  } catch (error) { message.textContent = `Connection failed: ${error.message}. Ensure the local bridge is running.`; }
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
