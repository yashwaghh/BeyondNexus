/* Shared upload preview. Boxes annotate suspected PII; pixels remain visible. */
globalThis.PrivacyGatePreview = (() => {
  const versions = new WeakMap();
  const names = {
    PERSON: 'Person / identifying photograph', ADDRESS: 'Postal address',
    PHONE: 'Possible phone number', EMAIL: 'Email address', PAN: 'PAN identifier',
    AADHAAR: 'Aadhaar identifier', BANK_ACCOUNT: 'Bank account', OTHER_PII: 'Other identifying information',
    POSSIBLE_ID: 'Possible identity number'
  };
  function label(finding) { return names[finding.entity] || 'Possible personal information'; }
  function validBox(box) {
    return Array.isArray(box) && box.length === 4
      && box.every(value => Number.isInteger(value) && value >= 0 && value <= 1000)
      && box[0] < box[2] && box[1] < box[3];
  }
  function clear(root) { versions.set(root, (versions.get(root) || 0) + 1); root.replaceChildren(); }
  async function render(root, body) {
    clear(root);
    const version = versions.get(root);
    const heading = document.createElement('h3'); heading.textContent = 'Suspicious information preview';
    const note = document.createElement('p');
    note.textContent = 'Boxes show approximate model locations, not verified identity types. This is NOT redaction: all original visible information remains. Missing boxes do not mean a page is safe.';
    root.append(heading, note);
    const pages = body.preview_pages || [];
    if (!pages.length) {
      const message = document.createElement('p'); message.textContent = 'No visual preview was returned. Review the original locally.';
      root.append(message); return;
    }
    // Keep original finding indices stable across the list and all page boxes.
    const findings = body.findings.map((finding, index) => ({...finding, number: index + 1}));
    const unlocated = findings.filter(f => !f.page || !validBox(f.region_0_1000));
    if (unlocated.length) {
      const list = document.createElement('ul');
      for (const f of unlocated) {
        const item = document.createElement('li');
        item.textContent = `#${f.number} ${label(f)} · ${f.page ? `Page ${f.page}` : 'Document'} · location unavailable (${f.source}). Inspect manually.`;
        list.append(item);
      }
      root.append(list);
    }
    for (const page of pages) {
      if (versions.get(root) !== version) return;
      if (typeof page.image_data_url !== 'string' || !page.image_data_url.startsWith('data:image/png;base64,')) continue;
      const figure = document.createElement('figure'); figure.className = 'preview-page';
      const caption = document.createElement('figcaption'); caption.textContent = `Page ${page.page} · original visible content`;
      const canvas = document.createElement('canvas'); canvas.setAttribute('aria-label', `Page ${page.page} with numbered suspected personal information boxes`);
      const items = findings.filter(f => f.page === page.page && validBox(f.region_0_1000));
      const legend = document.createElement('ul');
      for (const f of items) {
        const item = document.createElement('li');
        item.textContent = `#${f.number} ${label(f)} · model suggestion; verify this region yourself.`;
        legend.append(item);
      }
      const message = document.createElement('p');
      message.textContent = items.length ? `${items.length} approximate region(s) highlighted.` : 'No reliable region boxes on this page. Inspect the entire page manually.';
      const link = document.createElement('a'); link.className = 'preview-download';
      link.textContent = `Download annotated page ${page.page} (NOT redacted)`;
      link.download = `privacygate-page-${page.page}-annotated-NOT-REDACTED.png`;
      figure.append(caption, canvas, message, legend); root.append(figure);
      try {
        const image = new Image();
        image.src = page.image_data_url;
        await image.decode();
        if (versions.get(root) !== version) return;
        canvas.width = image.naturalWidth; canvas.height = image.naturalHeight;
        const ctx = canvas.getContext('2d'); ctx.drawImage(image, 0, 0);
        const line = Math.max(2, canvas.width / 350);
        const font = Math.max(16, canvas.width / 50);
        ctx.lineWidth = line; ctx.font = `bold ${font}px sans-serif`;
        for (const f of items) {
          const [top, left, bottom, right] = f.region_0_1000;
          const x = left * canvas.width / 1000, y = top * canvas.height / 1000;
          const width = (right - left) * canvas.width / 1000;
          const height = (bottom - top) * canvas.height / 1000;
          ctx.strokeStyle = '#c21f30'; ctx.strokeRect(x, y, width, height);
          const text = `#${f.number} ${f.entity}`;
          const labelWidth = Math.min(canvas.width, ctx.measureText(text).width + 12);
          const labelX = Math.max(0, Math.min(x, canvas.width - labelWidth));
          const labelY = Math.max(0, y - font - 8);
          ctx.fillStyle = '#c21f30'; ctx.fillRect(labelX, labelY, labelWidth, font + 8);
          ctx.fillStyle = '#fff'; ctx.fillText(text, labelX + 6, labelY + font);
        }
        link.href = canvas.toDataURL('image/png'); figure.append(link);
      } catch {
        message.textContent = 'Preview could not be decoded. Inspect the original page locally.';
      }
    }
  }
  return {render, clear, validBox, label};
})();
