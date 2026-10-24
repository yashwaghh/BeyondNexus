const source = document.querySelector('#source');
const result = document.querySelector('#result');
const scanButton = document.querySelector('#scan');
const copyButton = document.querySelector('#copy');
const reviewed = document.querySelector('#reviewed');
const statusNode = document.querySelector('#status');
const summary = document.querySelector('#summary');
const warnings = document.querySelector('#warnings');
const count = document.querySelector('#char-count');
const token = document.querySelector('meta[name="privacygate-token"]').content;
let latest = null;

source.addEventListener('input', () => {
  count.textContent = `${source.value.length.toLocaleString()} / 50,000`;
  latest = null;
  reviewed.checked = false;
  reviewed.disabled = true;
  copyButton.disabled = true;
});

reviewed.addEventListener('change', () => {
  copyButton.disabled = !reviewed.checked || !latest || latest.status === 'BLOCKED_UNVERIFIED';
});

scanButton.addEventListener('click', async () => {
  if (!source.value.trim()) {
    showError('Enter text to review.');
    return;
  }
  scanButton.disabled = true;
  scanButton.textContent = 'Reviewing…';
  reviewed.checked = false;
  reviewed.disabled = true;
  copyButton.disabled = true;
  try {
    const response = await fetch('/v1/scan', {
      method: 'POST',
      headers: {'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json'},
      body: JSON.stringify({text: source.value, mode: document.querySelector('#mode').value})
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || 'Local scan failed');
    latest = body;
    result.value = body.sanitized_text;
    statusNode.textContent = body.status.replaceAll('_', ' ');
    statusNode.className = `status ${body.status.toLowerCase()}`;
    const counts = body.findings.reduce((map, finding) => {
      map[finding.entity] = (map[finding.entity] || 0) + 1;
      return map;
    }, {});
    const labels = Object.entries(counts).map(([key, value]) => `${value} ${key}`).join(' · ');
    summary.textContent = labels || 'No known rule or model findings. Manual review is still required.';
    warnings.replaceChildren(...body.warnings.map(message => {
      const item = document.createElement('p'); item.textContent = message; return item;
    }));
    reviewed.disabled = body.status === 'BLOCKED_UNVERIFIED';
  } catch (error) {
    showError(error.message);
  } finally {
    scanButton.disabled = false;
    scanButton.textContent = 'Review locally';
  }
});

copyButton.addEventListener('click', async () => {
  await navigator.clipboard.writeText(result.value);
  copyButton.textContent = 'Copied — paste manually';
  setTimeout(() => copyButton.textContent = 'Approve & copy sanitized draft', 1800);
});

function showError(message) {
  latest = null;
  statusNode.textContent = 'Scan failed';
  statusNode.className = 'status blocked_unverified';
  summary.textContent = message;
  warnings.replaceChildren();
}
