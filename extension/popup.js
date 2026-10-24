const $ = selector => document.querySelector(selector);
const BRIDGE = 'http://127.0.0.1:8765';
let latest = null, target = null, revision = 0, controller = null;
const allowed = () => Boolean(latest && $('#reviewed').checked && latest.status !== 'BLOCKED_UNVERIFIED');
$('#settings').addEventListener('click', () => chrome.runtime.openOptionsPage());
$('#source').addEventListener('input', resetApproval);
$('#mode').addEventListener('change', resetApproval);
$('#reviewed').addEventListener('change', updateActions);
chrome.tabs.onActivated.addListener(() => disconnect());
chrome.tabs.onUpdated.addListener((id, change) => {
  if (target?.id === id && (change.url || change.status === 'loading')) disconnect();
});
chrome.storage.onChanged.addListener(() => resetApproval());

function disconnect() {
  target = null; resetApproval();
  $('#target-label').textContent = 'Target disconnected. Reconnect the intended ChatGPT tab.';
}
async function composer(action, replacement, approvalRevision) {
  if (!target) throw new Error('Connect the intended ChatGPT tab first.');
  const [active] = await chrome.tabs.query({active: true, currentWindow: true});
  if (active?.id !== target.id) throw new Error('The active tab changed. Reconnect ChatGPT.');
  const tab = await chrome.tabs.get(target.id);
  if (tab.url !== target.url) throw new Error('The conversation changed. Reconnect ChatGPT.');
  if (action === 'insert' && (revision !== approvalRevision || !allowed()))
    throw new Error('Approval changed. Review again before inserting.');
  const [{result}] = await chrome.scripting.executeScript({
    target: {tabId: target.id}, func: chatgptComposer,
    args: [action, target.text, replacement ?? null]
  });
  if (!result || result.error) throw new Error(result?.error || 'Composer unavailable.');
  return result;
}
$('#target').addEventListener('click', async () => {
  disconnect();
  try {
    const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
    if (!tab?.url || new URL(tab.url).origin !== 'https://chatgpt.com')
      throw new Error('Open ChatGPT and click the PrivacyGate toolbar icon to grant access.');
    target = {id: tab.id, url: tab.url, text: ''};
    const result = await composer('read');
    target.text = result.text;
    $('#target-label').textContent = 'ChatGPT connected. Insertion replaces its captured draft.';
    setMessage('Write privately here, or capture the existing ChatGPT draft.');
  } catch (error) { target = null; setMessage(error.message, true); }
});
$('#capture').addEventListener('click', async () => {
  try {
    const result = await composer('read');
    target.text = result.text;
    $('#source').value = result.text; resetApproval();
    setMessage('Draft captured. Content already typed on ChatGPT may already be accessible to that website.');
  } catch (error) { setMessage(error.message, true); }
});
$('#scan').addEventListener('click', async () => {
  resetApproval();
  const text = $('#source').value, mode = $('#mode').value, version = revision;
  if (!text.trim()) return setMessage('Enter text first.', true);
  $('#scan').disabled = true;
  const request = new AbortController(); controller = request;
  const timer = setTimeout(() => request.abort(), 180000);
  try {
    const config = await chrome.storage.local.get({bridgeToken: ''});
    if (!config.bridgeToken) throw new Error('Save the local bridge token in Settings first.');
    if (revision !== version) return;
    setMessage('Reviewing locally. Gemma may take a minute; keep this panel open.');
    const response = await fetch(`${BRIDGE}/v1/scan`, {
      method: 'POST', signal: request.signal,
      headers: {Authorization: `Bearer ${config.bridgeToken}`, 'Content-Type': 'application/json'},
      body: JSON.stringify({text, mode})
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || 'Local scan rejected.');
    if (revision !== version) return;
    if (!['READY_FOR_MANUAL_APPROVAL', 'REVIEW_REQUIRED', 'BLOCKED_UNVERIFIED'].includes(body.status)
        || typeof body.sanitized_text !== 'string' || !Array.isArray(body.findings)
        || !Array.isArray(body.warnings)) throw new Error('Invalid bridge response.');
    latest = body;
    $('#output').hidden = false; $('#result').value = body.sanitized_text;
    $('#status').textContent = body.status.replaceAll('_', ' ');
    $('#summary').textContent = body.findings.map(f => `${f.entity} (${f.source})`).join(' · ')
      || 'No known findings; manual review is still required.';
    $('#warnings').textContent = body.warnings.join(' ');
    $('#reviewed').disabled = body.status === 'BLOCKED_UNVERIFIED';
    updateActions();
    setMessage(body.status === 'BLOCKED_UNVERIFIED' ? 'Verification incomplete. Copy and insertion blocked.' : 'Review the entire proposed draft before approving.');
  } catch (error) {
    if (revision === version) setMessage(error.name === 'AbortError'
      ? 'Local scan timed out. Nothing was inserted.' : 'Scan failed. Check the local server, token and extension origin.', true);
  } finally {
    clearTimeout(timer);
    if (controller === request) { controller = null; $('#scan').disabled = false; }
  }
});
$('#copy').addEventListener('click', async () => {
  if (!allowed()) return;
  try { await navigator.clipboard.writeText(latest.sanitized_text); setMessage('Reviewed draft copied.'); }
  catch { setMessage('Clipboard unavailable.', true); }
});
$('#insert').addEventListener('click', async () => {
  if (!allowed()) return;
  const value = latest.sanitized_text;
  $('#insert').disabled = true;
  try {
    await composer('insert', value, revision);
    resetApproval(); target = null;
    $('#target-label').textContent = 'Insertion complete. Reconnect before another insertion.';
    setMessage('Inserted into ChatGPT. Inspect the composer; click Send yourself when ready.');
  } catch (error) { disconnect(); setMessage(error.message, true); }
});
$('#clear').addEventListener('click', () => {
  $('#source').value = ''; disconnect(); setMessage('Private draft and result cleared from this panel.');
});
function resetApproval() {
  revision++; controller?.abort();
  latest = null; $('#output').hidden = true; $('#result').value = '';
  $('#summary').textContent = ''; $('#warnings').textContent = '';
  $('#reviewed').checked = false; $('#reviewed').disabled = true; updateActions();
}
function updateActions() { $('#copy').disabled = !allowed(); $('#insert').disabled = !(allowed() && target); }
function setMessage(text, error = false) { $('#message').textContent = text; $('#message').style.color = error ? '#a43131' : '#617068'; }
resetApproval();
