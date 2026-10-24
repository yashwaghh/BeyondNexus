const $ = selector => document.querySelector(selector);
const BRIDGE = 'http://127.0.0.1:8765';
let latest = null, target = null, revision = 0, controller = null;
const allowed = () => Boolean(latest && latest.export_available !== false && $('#reviewed').checked && latest.status !== 'BLOCKED_UNVERIFIED');
$('#cancel').addEventListener('click', () => { resetApproval(); setMessage('Review cancelled. A running local model request may finish on the bridge.'); });
$('#settings').addEventListener('click', () => chrome.runtime.openOptionsPage());
$('#source').addEventListener('input', resetApproval);
$('#mode').addEventListener('change', resetApproval);
$('#reviewed').addEventListener('change', updateActions);
$('#upload').addEventListener('change', resetApproval);
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
      throw new Error('Open https://chatgpt.com and reconnect. If access is disabled, allow this site in Chrome extension settings.');
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
  $('#scan-file').disabled = true;
  const request = new AbortController(); controller = request; $('#cancel').hidden = false;
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
    if (!response.ok) throw new Error(bridgeError(response.status));
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
      ? 'Local scan timed out. Nothing was inserted.' : (error.message || 'Local connection failed. Check Settings.'), true);
  } finally {
    clearTimeout(timer);
    if (controller === request) { controller = null; $('#cancel').hidden = true; $('#scan').disabled = false; $('#scan-file').disabled = false; }
  }
});
$('#scan-file').addEventListener('click', async () => {
  resetApproval();
  const version = revision, file = $('#upload').files[0];
  if (!file) return setMessage('Choose an image or PDF first.', true);
  if (file.size > 6 * 1024 * 1024) return setMessage('File exceeds 6 MB.', true);
  const request = new AbortController(); controller = request; $('#cancel').hidden = false;
  $('#scan-file').disabled = true; $('#scan').disabled = true;
  const timer = setTimeout(() => request.abort(), 840000);
  try {
    const config = await chrome.storage.local.get({bridgeToken: ''});
    if (!config.bridgeToken) throw new Error('Save the bridge token in Settings first.');
    const data = await new Promise((resolve, reject) => {
      const reader = new FileReader(); reader.onerror = () => reject(new Error('Cannot read file locally.'));
      reader.onload = () => resolve(String(reader.result).split(',', 2)[1]); reader.readAsDataURL(file);
    });
    if (version !== revision) return;
    setMessage('Rendering and inspecting locally. Multi-page PDFs may take several minutes.');
    const response = await fetch(`${BRIDGE}/v1/scan-file`, {
      method: 'POST', signal: request.signal,
      headers: {Authorization: `Bearer ${config.bridgeToken}`, 'Content-Type': 'application/json'},
      body: JSON.stringify({data_base64: data, media_type: file.type, vision_mode: 'always', include_previews: true})
    });
    if (!response.ok) throw new Error(bridgeError(response.status));
    const body = await response.json();
    if (version !== revision) return;
    $('#draft-actions').hidden = true; $('#result').hidden = true; $('#result-title').textContent = 'File review';
    $('#output').hidden = false; $('#status').textContent = body.status.replaceAll('_', ' ');
    $('#result').value = 'Review and edit masks below to export a redacted file. Nothing is attached to ChatGPT.';
    $('#summary').textContent = `${body.findings.length} finding(s). Inspect the numbered boxes below.`;
    $('#warnings').textContent = body.warnings.join(' ');
    // Never set latest: file results cannot authorize text insertion or copying.
    await PrivacyGatePreview.render($('#document-preview'), body, {exportFile: async (edits, signal) => {
      const response = await fetch(`${BRIDGE}/v1/redact-export`, {
        method:'POST', signal,
        headers:{Authorization:`Bearer ${config.bridgeToken}`, 'Content-Type':'application/json'},
        body:JSON.stringify({...edits, data_base64:data, media_type:file.type, export_ticket:body.export_ticket})
      });
      if (!response.ok) throw new Error('Export failed. Rescan if the 15-minute authorization expired.');
      return response.blob();
    }});
    if (version === revision) setMessage(body.status === 'BLOCKED_UNVERIFIED'
      ? 'Visual verification incomplete. Inspect the original; previews are not redaction.'
      : 'Suspected information is highlighted. Labels and locations may be wrong; inspect every page.');
  } catch (error) {
    if (version === revision) setMessage(error.name === 'AbortError' ? 'File review timed out.' : error.message, true);
  } finally {
    clearTimeout(timer);
    if (controller === request) { controller = null; $('#cancel').hidden = true; $('#scan-file').disabled = false; $('#scan').disabled = false; }
  }
});
function bridgeError(status) {
  if (status === 401) return 'Token rejected. Save the current server token in Settings.';
  if (status === 403) return 'Extension origin rejected. Restart the server using the command in Settings.';
  if (status === 429) return 'Local scanner busy. Wait for the previous review to finish.';
  if (status === 400) return 'Invalid file or request. Check format, 6 MB size and 5-page limit.';
  return `Local scanner returned HTTP ${status}. Check the server.`;
}
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
  $('#upload').value = '';
});
function resetApproval() {
  revision++; controller?.abort();
  latest = null; $('#output').hidden = true; $('#result').value = '';
  $('#draft-actions').hidden = false; $('#result').hidden = false; $('#result-title').textContent = 'Sanitized draft';
  $('#summary').textContent = ''; $('#warnings').textContent = '';
  $('#reviewed').checked = false; $('#reviewed').disabled = true; updateActions();
  PrivacyGatePreview.clear($('#document-preview'));
}
function updateActions() { $('#copy').disabled = !allowed(); $('#insert').disabled = !(allowed() && target); }
function setMessage(text, error = false) { $('#message').textContent = text; $('#message').style.color = error ? '#a43131' : '#617068'; }
resetApproval();
