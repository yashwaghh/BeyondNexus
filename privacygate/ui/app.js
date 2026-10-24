const source = document.querySelector('#source');
const result = document.querySelector('#result');
const scanButton = document.querySelector('#scan');
const scanFileButton = document.querySelector('#scan-file');
const upload = document.querySelector('#upload');
const copyButton = document.querySelector('#copy');
const reviewed = document.querySelector('#reviewed');
const statusNode = document.querySelector('#status');
const summary = document.querySelector('#summary');
const warnings = document.querySelector('#warnings');
const findingList = document.querySelector('#finding-list');
const count = document.querySelector('#char-count');
const token = document.querySelector('meta[name="privacygate-token"]').content;
let latest = null;
let revision = 0;
let activeRequest = null;
const cancelButton = document.querySelector("#cancel");
function setBusy(busy) {
  scanButton.disabled = busy; scanFileButton.disabled = busy; cancelButton.hidden = !busy;
  if (!busy) { scanButton.textContent = "Review locally"; scanFileButton.textContent = "Review file with local Gemma vision"; }
}
function beginRequest() { const request = new AbortController(); activeRequest = request; setBusy(true); return request; }
cancelButton.addEventListener("click", () => { invalidate(); summary.textContent = "Review cancelled. A running local model request may finish on the bridge."; });
const preview = document.querySelector('#document-preview');
function invalidate() {
  revision++; activeRequest?.abort(); activeRequest = null; setBusy(false); latest = null; result.value = '';
  reviewed.checked = false; reviewed.disabled = true; copyButton.disabled = true;
  findingList.replaceChildren(); warnings.replaceChildren();
  statusNode.textContent = 'Not scanned'; statusNode.className = 'status idle';
  summary.textContent = 'Review the current input to see findings.';
  PrivacyGatePreview.clear(preview);
}
document.querySelector('#mode').addEventListener('change', invalidate);

source.addEventListener('input', () => {
  invalidate();
  count.textContent = `${source.value.length.toLocaleString()} / 50,000`;
  latest = null;
  reviewed.checked = false;
  reviewed.disabled = true;
  copyButton.disabled = true;
});

upload.addEventListener('change', () => {
  invalidate();
  latest = null;
  reviewed.checked = false;
  reviewed.disabled = true;
  copyButton.disabled = true;
});

reviewed.addEventListener('change', () => {
  copyButton.disabled = !reviewed.checked || !latest || !latest.sanitized_text
    || latest.export_available === false || latest.status === 'BLOCKED_UNVERIFIED';
});

scanButton.addEventListener('click', async () => {
  invalidate(); const version = revision;
  if (!source.value.trim()) {
    showError('Enter text to review.');
    return;
  }
  const request = beginRequest();
  const timer = setTimeout(() => request.abort(), 180000);
  scanButton.textContent = 'Reviewing…';
  reviewed.checked = false;
  reviewed.disabled = true;
  copyButton.disabled = true;
  try {
    const response = await fetch('/v1/scan', {
      method: 'POST', signal:request.signal,
      headers: {'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json'},
      body: JSON.stringify({text: source.value, mode: document.querySelector('#mode').value})
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || 'Local scan failed');
    if (revision === version) await renderResult(body);
  } catch (error) {
    if (revision === version) showError(error.name === 'AbortError' ? 'Local review timed out or was cancelled.' : error.message);
  } finally {
    clearTimeout(timer); if (activeRequest === request) { activeRequest = null; setBusy(false); }
  }
});

scanFileButton.addEventListener('click', async () => {
  invalidate(); const version = revision;
  const file = upload.files[0];
  if (!file) return showError('Choose an image or PDF to review.');
  if (file.size > 6 * 1024 * 1024) return showError('File exceeds the 6 MB local review limit.');
  const request = beginRequest();
  const timer = setTimeout(() => request.abort(), 840000);
  scanFileButton.textContent = 'Rendering & reviewing…';
  reviewed.checked = false;
  reviewed.disabled = true;
  copyButton.disabled = true;
  try {
    const dataBase64 = await fileAsBase64(file);
    if (revision !== version) return;
    const response = await fetch('/v1/scan-file', {
      method: 'POST', signal:request.signal,
      headers: {'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json'},
      body: JSON.stringify({data_base64: dataBase64, media_type: file.type, vision_mode: 'always', include_previews: true})
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || 'Local file review failed');
    if (revision === version) await renderResult(body, async (edits, signal) => {
      const response = await fetch('/v1/redact-export', {
        method: 'POST', signal,
        headers: {'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json'},
        body: JSON.stringify({...edits, data_base64:dataBase64, media_type:file.type, export_ticket:body.export_ticket})
      });
      if (!response.ok) throw new Error('Export failed. Rescan if the 15-minute review authorization expired.');
      return response.blob();
    });
  } catch (error) {
    if (revision === version) showError(error.name === 'AbortError' ? 'Local review timed out or was cancelled.' : error.message);
  } finally {
    clearTimeout(timer); if (activeRequest === request) { activeRequest = null; setBusy(false); }
  }
});

copyButton.addEventListener('click', async () => {
  if (!latest || !reviewed.checked || latest.export_available === false || latest.status === 'BLOCKED_UNVERIFIED') return;
  try { await navigator.clipboard.writeText(result.value); }
  catch { summary.textContent = "Clipboard unavailable; copy the reviewed draft manually."; return; }
  copyButton.textContent = 'Copied — paste manually';
  setTimeout(() => copyButton.textContent = 'Approve & copy sanitized draft', 1800);
});

function showError(message) {
  invalidate();
  latest = null;
  statusNode.textContent = 'Scan failed';
  statusNode.className = 'status blocked_unverified';
  summary.textContent = message;
  warnings.replaceChildren();
  findingList.replaceChildren();
}

async function renderResult(body, exportFile) {
  latest = body;
  result.value = body.sanitized_text || 'Review and edit the file masks below, then prepare a redacted export.';
  statusNode.textContent = body.status.replaceAll('_', ' ');
  statusNode.className = `status ${body.status.toLowerCase()}`;
  const counts = body.findings.reduce((map, finding) => {
    map[finding.entity] = (map[finding.entity] || 0) + 1;
    return map;
  }, {});
  const labels = Object.entries(counts).map(([key, value]) => `${value} ${key}`).join(' · ');
  const pages = body.page_count ? `${body.page_count} page${body.page_count === 1 ? '' : 's'} · ` : '';
  summary.textContent = pages + (labels || 'No known findings. Manual review is still required.');
  findingList.replaceChildren(...body.findings.map(finding => {
    const item = document.createElement('p');
    const location = finding.page
      ? `Page ${finding.page}${finding.region_0_1000 ? ' · see numbered box below' : ' · location unavailable'}`
      : (Number.isInteger(finding.start) ? `Characters ${finding.start}-${finding.end}` : 'Document metadata');
    item.textContent = `#${body.findings.indexOf(finding) + 1} ${location} · ${PrivacyGatePreview.label(finding)} · ${finding.source}`;
    return item;
  }));
  warnings.replaceChildren(...body.warnings.map(message => {
    const item = document.createElement('p'); item.textContent = message; return item;
  }));
  reviewed.checked = false;
  reviewed.disabled = body.status === 'BLOCKED_UNVERIFIED' || !body.sanitized_text || body.export_available === false;
  copyButton.disabled = true;
  if (body.export_available === false) await PrivacyGatePreview.render(preview, body, {exportFile});
  else PrivacyGatePreview.clear(preview);
}

function fileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('The selected file could not be read locally.'));
    reader.onload = () => resolve(String(reader.result).split(',', 2)[1]);
    reader.readAsDataURL(file);
  });
}
