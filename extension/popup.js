const $ = selector => document.querySelector(selector);
let latest = null;

$('#settings').addEventListener('click', () => chrome.runtime.openOptionsPage());
$('#source').addEventListener('input', resetApproval);
$('#reviewed').addEventListener('change', updateActions);

$('#capture').addEventListener('click', async () => {
  try {
    const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    const [{result}] = await chrome.scripting.executeScript({target: {tabId: tab.id}, func: readFocusedField});
    if (!result) throw new Error('Focus a text field or editable composer first.');
    $('#source').value = result;
    resetApproval();
    setMessage('Captured locally. Nothing has been sent.');
  } catch (error) { setMessage(error.message, true); }
});

$('#scan').addEventListener('click', async () => {
  if (!$('#source').value.trim()) return setMessage('Enter or capture text first.', true);
  const config = await chrome.storage.local.get({bridgeUrl: 'http://127.0.0.1:8765', bridgeToken: ''});
  if (!config.bridgeToken) return setMessage('Open settings and save the bridge token shown by the local server.', true);
  $('#scan').disabled = true;
  try {
    const response = await fetch(`${config.bridgeUrl.replace(/\/$/, '')}/v1/scan`, {
      method: 'POST', headers: {'Authorization': `Bearer ${config.bridgeToken}`, 'Content-Type': 'application/json'},
      body: JSON.stringify({text: $('#source').value, mode: $('#mode').value})
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || 'Local bridge rejected the scan.');
    latest = body;
    $('#output').hidden = false;
    $('#result').value = body.sanitized_text;
    $('#status').textContent = body.status.replaceAll('_', ' ');
    const counts = body.findings.reduce((all, finding) => ({...all, [finding.entity]: (all[finding.entity] || 0) + 1}), {});
    $('#summary').textContent = Object.entries(counts).map(([kind, amount]) => `${amount} ${kind}`).join(' · ') || 'No known findings; manual review is still required.';
    $('#warnings').textContent = body.warnings.join(' ');
    $('#reviewed').checked = false;
    $('#reviewed').disabled = body.status === 'BLOCKED_UNVERIFIED';
    updateActions();
    setMessage(body.status === 'BLOCKED_UNVERIFIED' ? 'Contextual verification is incomplete; copy and insert stay blocked.' : 'Review every character before approving.', body.status === 'BLOCKED_UNVERIFIED');
  } catch (error) { setMessage(error.message, true); }
  finally { $('#scan').disabled = false; }
});

$('#copy').addEventListener('click', async () => {
  await navigator.clipboard.writeText(latest.sanitized_text);
  setMessage('Sanitized draft copied. Paste it manually when ready.');
});

$('#insert').addEventListener('click', async () => {
  try {
    const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    const [{result}] = await chrome.scripting.executeScript({
      target: {tabId: tab.id}, func: replaceFocusedField, args: [latest.sanitized_text]
    });
    if (!result) throw new Error('The focused field is unavailable. Use Copy instead.');
    setMessage('Focused field replaced. PrivacyGate did not submit it.');
  } catch (error) { setMessage(error.message, true); }
});

function resetApproval() { latest = null; $('#reviewed').checked = false; $('#reviewed').disabled = true; updateActions(); }
function updateActions() { const allowed = Boolean(latest && $('#reviewed').checked && latest.status !== 'BLOCKED_UNVERIFIED'); $('#copy').disabled = !allowed; $('#insert').disabled = !allowed; }
function setMessage(text, error = false) { $('#message').textContent = text; $('#message').style.color = error ? '#a43131' : '#617068'; }

function readFocusedField() {
  const node = document.activeElement;
  if (node instanceof HTMLTextAreaElement || (node instanceof HTMLInputElement && /^(text|search|email|url|tel)$/.test(node.type))) return node.value;
  if (node?.isContentEditable) return node.innerText;
  return '';
}

function replaceFocusedField(value) {
  const node = document.activeElement;
  if (node instanceof HTMLTextAreaElement || (node instanceof HTMLInputElement && /^(text|search|email|url|tel)$/.test(node.type))) {
    const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(node), 'value')?.set;
    if (!setter) return false;
    setter.call(node, value); node.dispatchEvent(new Event('input', {bubbles: true})); return true;
  }
  if (node?.isContentEditable) {
    node.textContent = value; node.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText', data: value})); return true;
  }
  return false;
}
