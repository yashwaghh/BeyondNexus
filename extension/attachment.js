// Explicit user action only. Chrome serializes this into the site's isolated world.
function chatgptAttachment(action, expectedUrl, payload) {
  if (location.origin !== 'https://chatgpt.com' || location.href !== expectedUrl)
    return {error: 'The ChatGPT conversation changed. Review again before attaching.'};
  let editors = [...document.querySelectorAll('#prompt-textarea')].filter(node => node.getClientRects().length);
  if (editors.length > 1) {
    const visible = editors.filter(node => {
      const rect = typeof node.getBoundingClientRect === 'function' ? node.getBoundingClientRect() : null;
      return (!rect || (rect.width > 0 && rect.height > 0)) && (node.offsetParent !== null || !('offsetParent' in node));
    });
    if (visible.length === 1) editors = visible;
    else {
      const inForm = (visible.length ? visible : editors).filter(node => typeof node.closest === 'function' && node.closest('form'));
      if (inForm.length === 1) editors = inForm;
    }
  }
  if (!editors.length) {
    const wrapper = document.querySelector('#prompt-textarea');
    if (wrapper) {
      const inner = wrapper.querySelector('textarea, [contenteditable="true"]');
      if (inner && inner.getClientRects().length) editors = [inner];
    }
  }
  if (!editors.length) {
    const fallback = [...document.querySelectorAll('form [contenteditable="true"], main [contenteditable="true"], form textarea')].filter(node =>
      node.getClientRects().length && (node.offsetParent !== null || !('offsetParent' in node))
    );
    if (fallback.length === 1) editors = fallback;
  }
  if (editors.length !== 1) return {error: 'A unique ChatGPT composer was not found. Download and attach manually.'};
  const type = payload?.type;
  if (!['image/png', 'application/pdf'].includes(type)) return {error: 'Unsupported redacted file type.'};
  const suffix = type === 'image/png' ? '.png' : '.pdf';
  const accepts = node => {
    const choices = (node.accept || '').toLowerCase().split(',').map(value => value.trim()).filter(Boolean);
    return !choices.length || choices.includes('*/*') || choices.includes(type) || choices.includes(suffix)
      || (type === 'image/png' && choices.includes('image/*'));
  };
  const form = editors[0].closest('form');
  const local = form ? [...form.querySelectorAll('input[type="file"]')].filter(accepts) : [];
  const compatible = (local.length ? local : [...document.querySelectorAll('input[type="file"]')].filter(accepts))
    .filter(node => !node.disabled && node.getAttribute('aria-disabled') !== 'true');
  const specificity = node => {
    const choices=(node.accept || '').toLowerCase().split(',').map(value=>value.trim());
    return choices.includes(type) || choices.includes(suffix) ? 2 : choices.includes('image/*') && type === 'image/png' ? 1 : 0;
  };
  const best = Math.max(-1,...compatible.map(specificity));
  let candidates = compatible.filter(node => specificity(node) === best);
  if (candidates.length > 1 && editors[0]) {
    let parent = editors[0].parentElement;
    while (parent && parent !== document.body) {
      const matches = candidates.filter(node => typeof parent.contains === 'function' && parent.contains(node));
      if (matches.length === 1) { candidates = matches; break; }
      if (matches.length > 1) break;
      parent = parent.parentElement;
    }
  }
  if (candidates.length !== 1)
    return {error: 'A unique compatible file picker was not found. Download and attach manually.'};
  const input = candidates[0];
  const fingerprint = `${input.id}|${input.accept}|${input.multiple}`;
  if (action === 'inspect') return {ready: true, fingerprint};
  if (action !== 'attach' || payload.fingerprint !== fingerprint || typeof payload.base64 !== 'string'
      || payload.base64.length > 14_000_000) return {error: 'Attachment state changed or file is too large. Download and attach manually.'};
  if (input.files?.length) return {error: 'The file picker already has a selection. Attach manually to avoid replacing it.'};
  try {
    const decoded = atob(payload.base64);
    if (!decoded.length || decoded.length > 10 * 1024 * 1024) return {error: 'Invalid attachment size. Download and attach manually.'};
    const bytes = Uint8Array.from(decoded, character => character.charCodeAt(0));
    // Only generated raster exports are accepted; never a source file or annotated preview.
    const valid = type === 'image/png'
      ? bytes.slice(0, 8).join(',') === '137,80,78,71,13,10,26,10'
      : String.fromCharCode(...bytes.slice(0, 5)) === '%PDF-';
    if (!valid) return {error: 'Invalid generated file signature.'};
    const file = new File([bytes], `privacygate-redacted${suffix}`, {type, lastModified: 0});
    const transfer = new DataTransfer(); transfer.items.add(file);
    input.files = transfer.files;
    if (input.files.length !== 1 || input.files[0].size !== file.size) return {error: 'File selection could not be verified. Use manual attachment.'};
    input.dispatchEvent(new Event('input', {bubbles: true}));
    input.dispatchEvent(new Event('change', {bubbles: true}));
    return {assigned: true, filename: file.name, size: file.size};
  } catch {
    return {error: 'The browser rejected attachment. Download and attach manually.'};
  }
}
