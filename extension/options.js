const url = document.querySelector('#url');
const token = document.querySelector('#token');
const message = document.querySelector('#message');
chrome.storage.local.get({bridgeUrl: 'http://127.0.0.1:8765', bridgeToken: ''}, values => { url.value = values.bridgeUrl; token.value = values.bridgeToken; });
document.querySelector('#save').addEventListener('click', async () => {
  const normalized = url.value.replace(/\/$/, '');
  if (normalized !== 'http://127.0.0.1:8765' || token.value.length < 24) {
    message.textContent = 'Use http://127.0.0.1:8765 and a token of at least 24 characters.'; return;
  }
  await chrome.storage.local.set({bridgeUrl: normalized, bridgeToken: token.value});
  message.textContent = 'Saved only in this browser profile.';
});
