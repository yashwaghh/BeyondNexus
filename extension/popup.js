const $ = selector => document.querySelector(selector);
const BRIDGE = 'http://127.0.0.1:8765';
let latest = null, target = null, fileTarget = null, revision = 0, controller = null;
const allowed = () => Boolean(latest && latest.export_available !== false && $('#reviewed').checked && latest.status !== 'BLOCKED_UNVERIFIED');
$('#setup-command').textContent = `python -m privacygate.web --extension-origin chrome-extension://${chrome.runtime.id}`;
$('#check-bridge').addEventListener('click', async () => {
  const button = $('#check-bridge'); button.disabled = true;
  const request = new AbortController(); const timer = setTimeout(() => request.abort(), 8000);
  $('#connection-status').textContent = 'Checking local authentication...';
  try {
    const config = await chrome.storage.local.get({bridgeToken:''});
    if (!config.bridgeToken) throw new Error('Open Settings and save the current bridge token first.');
    const response = await fetch(`${BRIDGE}/v1/scan`, {
      method:'POST', signal:request.signal,
      headers:{Authorization:`Bearer ${config.bridgeToken}`, 'Content-Type':'application/json'},
      body:JSON.stringify({text:'PrivacyGate synthetic connection check.',mode:'off'})
    });
    if (!response.ok) throw new Error(bridgeError(response.status));
    const result = await response.json();
    if (result.status !== 'READY_FOR_MANUAL_APPROVAL' || !Array.isArray(result.findings)) throw new Error('Unexpected bridge response. Restart the current bridge version.');
    $('#connection-status').textContent = 'Connected: token and extension origin accepted. Text review is available; uploads also require local OCR and Gemma.';
  } catch (error) {
    $('#connection-status').textContent = error.name === 'AbortError' ? 'Bridge check timed out. Start the bridge using the command below.' : (error.message || 'Cannot reach local bridge. Start it using the command below.');
  } finally { clearTimeout(timer); button.disabled = false; }
});
$('#cancel').addEventListener('click', () => { resetApproval(); setMessage('Review cancelled. A running local model request may finish on the bridge.'); });
$('#settings').addEventListener('click', () => chrome.runtime.openOptionsPage());
$('#source').addEventListener('input', resetApproval);
$('#mode').addEventListener('change', resetApproval);
$('#reviewed').addEventListener('change', updateActions);
$('#upload').addEventListener('change', resetApproval);
chrome.tabs.onActivated.addListener(() => disconnect());
chrome.tabs.onUpdated.addListener((id, change) => {
  if ((target?.id === id || fileTarget?.id === id) && (change.url || change.status === 'loading')) disconnect();
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
    $('#target-label')?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' });
  } catch (error) { target = null; setMessage(error.message, true); }
});
$('#capture').addEventListener('click', async () => {
  try {
    const result = await composer('read');
    target.text = result.text;
    $('#source').value = result.text; resetApproval();
    setMessage('Draft captured. Content already typed on ChatGPT may already be accessible to that website.');
    $('#source')?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' });
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
    $('#output')?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' });
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
    const [tab] = await chrome.tabs.query({active:true,currentWindow:true});
    const attachmentTarget = tab?.url && new URL(tab.url).origin === 'https://chatgpt.com' ? {id:tab.id,url:tab.url} : null;
    fileTarget = attachmentTarget;
    const data = await new Promise((resolve, reject) => {
      const reader = new FileReader(); reader.onerror = () => reject(new Error('Cannot read file locally.'));
      reader.onload = () => resolve(String(reader.result).split(',', 2)[1]); reader.readAsDataURL(file);
    });
    if (version !== revision) return;
    setMessage('Rendering and inspecting locally. Multi-page PDFs may take several minutes.');
    $('#message')?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' });
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
    $('#result').value = 'Review and edit masks below to export a redacted file. An attachment is uploaded only when you explicitly click Attach.';
    $('#summary').textContent = `${body.findings.length} finding(s). Inspect the numbered boxes below.`;
    $('#warnings').textContent = body.warnings.join(' ');
    // Never set latest: file results cannot authorize text insertion or copying.
    await PrivacyGatePreview.render($('#document-preview'), body, {attachFile:(blob,format,signal) => attachRedacted(blob,format,signal,attachmentTarget), exportFile: async (edits, signal) => {
      const response = await fetch(`${BRIDGE}/v1/redact-export`, {
        method:'POST', signal,
        headers:{Authorization:`Bearer ${config.bridgeToken}`, 'Content-Type':'application/json'},
        body:JSON.stringify({...edits, data_base64:data, media_type:file.type, export_ticket:body.export_ticket})
      });
      if (!response.ok) throw new Error('Export failed. Rescan if the 15-minute authorization expired.');
      return response.blob();
    }});
    $('#document-preview')?.scrollIntoView?.({ behavior: 'smooth', block: 'start' });
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
    $('#target-label')?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' });
  } catch (error) { disconnect(); setMessage(error.message, true); }
});
$('#clear').addEventListener('click', () => {
  $('#source').value = ''; disconnect(); setMessage('Private draft and result cleared from this panel.');
  $('#upload').value = '';
});
function resetApproval() {
  revision++; controller?.abort(); fileTarget = null;
  latest = null; $('#output').hidden = true; $('#result').value = '';
  $('#draft-actions').hidden = false; $('#result').hidden = false; $('#result-title').textContent = 'Sanitized draft';
  $('#summary').textContent = ''; $('#warnings').textContent = '';
  $('#reviewed').checked = false; $('#reviewed').disabled = true; updateActions();
  PrivacyGatePreview.clear($('#document-preview'));
}
function updateActions() { $('#copy').disabled = !allowed(); $('#insert').disabled = !(allowed() && target); }
function setMessage(text, error = false) { $('#message').textContent = text; $('#message').style.color = error ? '#a43131' : '#617068'; }
resetApproval();

async function attachRedacted(blob, format, signal, intended) {
  const [active] = await chrome.tabs.query({active:true,currentWindow:true});
  const target = (active?.url && new URL(active.url).origin === 'https://chatgpt.com') ? active : intended;
  if (!target?.url || new URL(target.url).origin !== 'https://chatgpt.com')
    throw new Error('Open your intended ChatGPT conversation and keep it active, then click Attach.');
  if (!blob.size || blob.size > 10*1024*1024 || blob.type !== (format === 'png' ? 'image/png' : 'application/pdf'))
    throw new Error('Attachment exceeds the local 10 MB limit or has an invalid type. Download and attach manually.');
  async function verifyTarget() {
    if (signal.aborted) throw new Error('Attachment cancelled.');
    const [current] = await chrome.tabs.query({active:true,currentWindow:true});
    if (!current?.url || new URL(current.url).origin !== 'https://chatgpt.com')
      throw new Error('ChatGPT tab changed. Keep the ChatGPT tab active while attaching.');
    if (signal.aborted) throw new Error('Attachment cancelled.');
  }
  await verifyTarget();
  const [{result: picker}] = await chrome.scripting.executeScript({target:{tabId:target.id},func:chatgptAttachment,
    args:['inspect',target.url,{type:blob.type}]});
  if (!picker?.ready) throw new Error(picker?.error || 'Attachment picker unavailable. Download and attach manually.');
  const data = await new Promise((resolve,reject) => {
    const reader = new FileReader(); reader.onerror=() => reject(new Error('Cannot read generated export.'));
    reader.onload=() => resolve(String(reader.result).split(',',2)[1]); reader.readAsDataURL(blob);
  });
  await verifyTarget();
  const [{result}] = await chrome.scripting.executeScript({target:{tabId:target.id},func:chatgptAttachment,
    args:['attach',target.url,{type:blob.type,base64:data,fingerprint:picker.fingerprint}]});
  if (!result?.assigned) throw new Error(result?.error || 'Attachment could not be assigned. Download and attach manually.');
}
