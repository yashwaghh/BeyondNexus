// Self-contained: Chrome serializes this function into the page's isolated world.
function chatgptComposer(action, expected, replacement) {
  if (location.origin !== 'https://chatgpt.com') return {error: 'Open https://chatgpt.com first.'};
  let candidates = [...document.querySelectorAll('#prompt-textarea')].filter(node =>
    node.getClientRects().length && (node instanceof HTMLTextAreaElement || node.isContentEditable));
  if (candidates.length > 1) {
    const visible = candidates.filter(node => {
      const rect = typeof node.getBoundingClientRect === 'function' ? node.getBoundingClientRect() : null;
      return (!rect || (rect.width > 0 && rect.height > 0)) && (node.offsetParent !== null || !('offsetParent' in node));
    });
    if (visible.length === 1) {
      candidates = visible;
    } else {
      const inForm = (visible.length ? visible : candidates).filter(node => typeof node.closest === 'function' && node.closest('form'));
      if (inForm.length === 1) candidates = inForm;
    }
  }
  if (!candidates.length) {
    const wrapper = document.querySelector('#prompt-textarea');
    if (wrapper) {
      const inner = wrapper.querySelector('textarea, [contenteditable="true"]');
      if (inner && inner.getClientRects().length) candidates = [inner];
    }
  }
  if (!candidates.length) {
    const fallback = [...document.querySelectorAll('form [contenteditable="true"], main [contenteditable="true"], form textarea')].filter(node =>
      node.getClientRects().length && (node instanceof HTMLTextAreaElement || node.isContentEditable) &&
      (node.offsetParent !== null || !('offsetParent' in node))
    );
    if (fallback.length === 1) candidates = fallback;
  }
  if (candidates.length !== 1) return {error: 'A unique ChatGPT composer was not found. Use Copy instead.'};
  const node = candidates[0];
  const text = () => node instanceof HTMLTextAreaElement ? node.value : node.innerText;
  if (node.disabled || node.readOnly || node.getAttribute('aria-disabled') === 'true')
    return {error: 'The composer is currently unavailable.'};
  if (action === 'read') return {text: text(), url: location.href};
  if (action !== 'insert' || typeof replacement !== 'string') return {error: 'Invalid composer action.'};
  if (text() !== expected) return {error: 'ChatGPT draft changed. Capture the target again before inserting.'};
  node.focus();
  if (node instanceof HTMLTextAreaElement) {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(node, replacement);
    node.dispatchEvent(new Event('input', {bubbles: true}));
  } else {
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(node);
    selection.removeAllRanges(); selection.addRange(range);
    if (!document.execCommand('insertText', false, replacement))
      return {error: 'The editor rejected insertion. Use Copy instead.'};
  }
  const actual = text().replace(/\r\n/g, '\n').replace(/\n$/, '');
  if (actual !== replacement.replace(/\r\n/g, '\n').replace(/\n$/, ''))
    return {error: 'Insertion could not be verified. Inspect ChatGPT before sending.'};
  return {inserted: true};
}
