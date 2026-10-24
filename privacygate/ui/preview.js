/* Shared upload preview. Boxes annotate suspected PII; pixels remain visible. */
globalThis.PrivacyGatePreview = (() => {
  const versions = new WeakMap();
  const cleanups = new WeakMap();
  const names = {
    PERSON: 'Person / identifying photograph', ADDRESS: 'Postal address',
    PHONE: 'Possible phone number', EMAIL: 'Email address', PAN: 'PAN identifier',
    AADHAAR: 'Aadhaar identifier', BANK_ACCOUNT: 'Bank account', OTHER_PII: 'Other identifying information',
    POSSIBLE_ID: 'Possible identity number', DATE_OF_BIRTH: 'Date of birth',
    FINANCIAL_ID: 'Financial identifier', HEALTH_INFO: 'Health information',
    FINANCIAL_INFO: 'Personal financial information'
  };
  function label(finding) { return names[finding.entity] || 'Possible personal information'; }
  function validBox(box) {
    return Array.isArray(box) && box.length === 4
      && box.every(value => Number.isInteger(value) && value >= 0 && value <= 1000)
      && box[0] < box[2] && box[1] < box[3];
  }
  function clear(root) { cleanups.get(root)?.(); cleanups.delete(root); versions.set(root, (versions.get(root) || 0) + 1); root.replaceChildren(); }
  async function render(root, body, options = {}) {
    clear(root);
    const version = versions.get(root);
    const heading = document.createElement('h3'); heading.textContent = 'Suspicious information preview';
    const note = document.createElement('p');
    note.textContent = 'Boxes show approximate OCR/rule or model locations, not verified identity types. This is NOT redaction: all original visible information remains. Missing boxes do not mean a page is safe.';
    if (options.exportFile) note.textContent = 'Detected boxes are approximate. Add or correct masks, then inspect the masked preview before export. Annotated PNG downloads retain original pixels and are NOT redacted.';
    root.append(heading, note);
    for (const page of body.ocr_pages || []) {
      const quality = document.createElement('p');
      quality.textContent = `Page ${page.page} OCR: ${page.failed ? 'failed - upload unverified' : `${page.word_count} words, mean recognition confidence ${page.mean_confidence ?? 'unavailable'}/100`}. ${page.uncertain ? 'Low-confidence or unreadable content needs manual inspection.' : 'Recognition confidence is not a privacy safety score.'}`;
      root.append(quality);
    }
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
    const rendered = [];
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
        item.textContent = `#${f.number} ${label(f)} · ${(f.evidence_sources || [f.source]).join(' + ')}${typeof f.ocr_confidence === 'number' ? ` / OCR confidence ${f.ocr_confidence.toFixed(1)}/100` : ''}; verify this region yourself.`;
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
        rendered.push({page: page.page, canvas, image, figure});
      } catch {
        message.textContent = 'Preview could not be decoded. Inspect the original page locally.';
      }
    }
    if (versions.get(root) === version && rendered.length === pages.length && options.exportFile)
      setupEditor(root, body, rendered, options, version);
  }
  function setupEditor(root, body, pages, options, version) {
    const {exportFile, attachFile} = options;
    const panel = document.createElement('section'); panel.className = 'redaction-tools';
    const heading = document.createElement('h3'); heading.textContent = 'Redact and export';
    const help = document.createElement('p');
    help.textContent = 'Drag on a page to add a black mask. Remove an incorrect mask below, then draw its replacement. Check every page, including findings without a location. Exports remove masked pixels; missed information may remain.';
    const toggleLabel = document.createElement('label');
    const toggle = document.createElement('input'); toggle.type = 'checkbox'; toggle.className = 'masked-toggle';
    toggleLabel.append(toggle, ' Show masked preview');
    const approvalLabel = document.createElement('label');
    const approval = document.createElement('input'); approval.type = 'checkbox'; approval.className = 'export-reviewed';
    approvalLabel.append(approval, ' I inspected every masked page and covered missed or unlocated personal information.');
    const list = document.createElement('ul'); list.className = 'mask-list';
    const message = document.createElement('p'); message.setAttribute('role', 'status');
    const guidance = document.createElement('p'); guidance.className = 'export-guidance';
    const downloads = document.createElement('div');
    const buttons = [];
    let regions = body.findings.filter(f => f.page && validBox(f.region_0_1000))
      .map(f => ({page: f.page, box: [...f.region_0_1000]}));
    const history = [];
    const undo = document.createElement('button'); undo.type = 'button'; undo.className = 'undo-mask'; undo.textContent = 'Undo last mask edit';
    let url = null, request = null, editVersion = 0, prepared = null, attached = false;
    const attach = document.createElement('button'); attach.type = 'button'; attach.className = 'attach-redacted';
    attach.textContent = 'Attach redacted copy to ChatGPT (uploads file)';
    const enabled = body.status !== 'BLOCKED_UNVERIFIED' && typeof body.export_ticket === 'string';
    function revoke() {
      editVersion++; approval.checked = false; prepared = null; attached = false; request?.abort(); request = null;
      if (url) URL.revokeObjectURL(url); url = null; downloads.replaceChildren(); message.textContent = "";
      update();
    }
    cleanups.set(root, revoke);
    function update() {
      undo.disabled = !history.length;
      attach.disabled = attached || !enabled || !approval.checked || !toggle.checked || regions.length > 500 || Boolean(request);
      guidance.textContent = '';
      if (regions.length > 500) guidance.textContent = 'Too many masks (maximum 500). Use Mask whole page to replace that page\'s masks, or remove excess masks.';
      else if (!toggle.checked) guidance.textContent = 'Enable "Show masked preview" to review and export.';
      else if (!approval.checked) guidance.textContent = 'Tick "I inspected every masked page..." above to enable export.';
      else if (!prepared && !request) guidance.textContent = 'Click "Prepare redacted PNG/PDF" to download, or click "Attach" to upload to ChatGPT.';
      for (const button of buttons) button.disabled = !enabled || !approval.checked || !toggle.checked || regions.length > 500 || Boolean(request);
    }
    function draw() {
      for (const {page, canvas, image, figure} of pages) {
        figure.querySelector("figcaption").textContent = `Page ${page} / ${toggle.checked ? "masked preview" : "original with mask outlines"}`;
        const ctx = canvas.getContext('2d'); ctx.drawImage(image, 0, 0);
        for (const region of regions.filter(r => r.page === page)) {
          const [top,left,bottom,right] = region.box;
          const x = Math.max(0, Math.floor(left*canvas.width/1000)-2);
          const y = Math.max(0, Math.floor(top*canvas.height/1000)-2);
          const endX = Math.min(canvas.width, Math.ceil(right*canvas.width/1000)+2);
          const endY = Math.min(canvas.height, Math.ceil(bottom*canvas.height/1000)+2);
          if (toggle.checked) { ctx.fillStyle = '#000'; ctx.fillRect(x, y, endX-x, endY-y); }
          else { ctx.strokeStyle = '#c21f30'; ctx.lineWidth = Math.max(2,canvas.width/350); ctx.strokeRect(x,y,endX-x,endY-y); }
        }
      }
    }
    function commit(next) {
      revoke();
      history.push(regions.map(r => ({page:r.page, box:[...r.box]})));
      if (history.length > 20) history.shift();
      regions = next; listMasks(); draw(); update();
    }
    undo.addEventListener('click', () => {
      if (!history.length) return;
      revoke(); regions = history.pop(); listMasks(); draw(); update();
    });
    function listMasks() {
      list.replaceChildren();
      regions.forEach((region, index) => {
        const row = document.createElement('li'); row.textContent = `Mask ${index+1} / page ${region.page} `;
        const remove = document.createElement('button'); remove.textContent = 'Remove'; remove.type = 'button';
        remove.addEventListener('click', () => commit(regions.filter((_, i) => i !== index)));
        row.append(remove); list.append(row);
      });
    }
    for (const {page, canvas, figure} of pages) {
      const fullPage = document.createElement('button'); fullPage.type = 'button'; fullPage.className = 'mask-page';
      fullPage.textContent = 'Mask whole page';
      fullPage.addEventListener('click', () => {
        commit([...regions.filter(r => r.page !== page), {page, box:[0,0,1000,1000]}]);
      });
      figure.append(fullPage);
      canvas.style.touchAction = 'none'; canvas.style.cursor = 'crosshair';
      let start = null, pointerId = null;
      const point = event => {
        const rect = canvas.getBoundingClientRect();
        return [Math.max(0,Math.min(1000,Math.round((event.clientY-rect.top)/rect.height*1000))),
                Math.max(0,Math.min(1000,Math.round((event.clientX-rect.left)/rect.width*1000)))];
      };
      canvas.addEventListener('pointerdown', event => {
        if (event.button !== 0 || start) return;
        pointerId = event.pointerId; revoke(); start = point(event); canvas.setPointerCapture(event.pointerId);
      });
      canvas.addEventListener('pointermove', event => {
        if (!start || event.pointerId !== pointerId) return;
        draw(); const end = point(event), ctx = canvas.getContext('2d');
        ctx.strokeStyle = '#c21f30'; ctx.lineWidth = Math.max(2,canvas.width/350);
        ctx.strokeRect(start[1]*canvas.width/1000, start[0]*canvas.height/1000,
                       (end[1]-start[1])*canvas.width/1000,(end[0]-start[0])*canvas.height/1000);
      });
      canvas.addEventListener('pointerup', event => {
        if (!start || event.pointerId !== pointerId) return;
        const end = point(event), box = [Math.min(start[0],end[0]),Math.min(start[1],end[1]),Math.max(start[0],end[0]),Math.max(start[1],end[1])];
        start = null; pointerId = null;
        if (validBox(box) && regions.length < 500) commit([...regions, {page,box}]);
        else draw();
      });
      canvas.addEventListener('pointercancel', () => { start = null; pointerId = null; revoke(); draw(); });
    }
    toggle.addEventListener('change', () => {
      revoke(); draw();
      if (toggle.checked) approvalLabel?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' });
    });
    approval.addEventListener('change', () => {
      if (!approval.checked) revoke(); update();
      if (approval.checked) (buttons[0] || attach)?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' });
    });
    panel.append(heading, help, toggleLabel, approvalLabel, undo, list);
    for (const format of pages.length === 1 ? ['png','pdf'] : ['pdf']) {
      const button = document.createElement('button'); button.type = 'button'; button.className = `export-${format}`;
      button.textContent = `Prepare redacted ${format.toUpperCase()}`; buttons.push(button);
      button.addEventListener('click', async () => {
        if (!enabled || !approval.checked || !toggle.checked || regions.length > 500 || request) return;
        if (url) URL.revokeObjectURL(url); url = null; prepared = null; attached = false; downloads.replaceChildren();
        const edit = editVersion; request = new AbortController(); const current = request;
        const timer = setTimeout(() => current.abort(), 60000); update(); message.textContent = 'Building a new file locally...';
        try {
          const blob = await exportFile({regions, output_format:format, reviewed:true}, current.signal);
          if (versions.get(root) !== version || editVersion !== edit) return;
          if (!blob.size || blob.type !== (format === 'png' ? 'image/png' : 'application/pdf')) throw new Error('Invalid export response; no download created.');
          prepared = {blob, format};
          if (url) URL.revokeObjectURL(url); url = URL.createObjectURL(blob);
          const link = document.createElement('a'); link.href = url; link.className = 'redacted-download';
          link.download = `privacygate-redacted.${format}`; link.textContent = `Download redacted ${format.toUpperCase()}`;
          downloads.replaceChildren(link); message.textContent = 'File ready. Inspect the downloaded copy before sharing; detection can miss information.';
          downloads?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' });
        } catch (error) {
          if (versions.get(root) === version && editVersion === edit) message.textContent = error.name === 'AbortError' ? 'Export cancelled or timed out.' : error.message;
        } finally { clearTimeout(timer); if (request === current) { request = null; update(); } }
      });
      panel.append(button);
    }
    if (typeof attachFile === 'function') {
      const sharing = document.createElement('p');
      sharing.textContent = 'Attach uploads the generated redacted copy to the connected ChatGPT conversation. It never clicks Send. Check the website for upload completion before sending.';
      attach.addEventListener('click', async () => {
        if (attach.disabled || attached || request) return;
        const defaultFormat = pages.length === 1 ? 'png' : 'pdf';
        const edit = editVersion;
        request = new AbortController(); const current = request;
        const timer = setTimeout(() => current.abort(), 60000); update();
        try {
          let file = prepared;
          if (!file) {
            message.textContent = `Building redacted ${defaultFormat.toUpperCase()} and preparing attachment...`;
            const blob = await exportFile({regions, output_format: defaultFormat, reviewed: true}, current.signal);
            if (versions.get(root) !== version || editVersion !== edit) return;
            if (!blob.size || blob.type !== (defaultFormat === 'png' ? 'image/png' : 'application/pdf'))
              throw new Error('Invalid export response; no file created.');
            prepared = {blob, format: defaultFormat};
            if (url) URL.revokeObjectURL(url); url = URL.createObjectURL(blob);
            const link = document.createElement('a'); link.href = url; link.className = 'redacted-download';
            link.download = `privacygate-redacted.${defaultFormat}`; link.textContent = `Download redacted ${defaultFormat.toUpperCase()}`;
            downloads.replaceChildren(link);
            downloads?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' });
            file = prepared;
          }
          message.textContent = 'Handing the reviewed redacted copy to ChatGPT...';
          await attachFile(file.blob, file.format, current.signal);
          if (versions.get(root) !== version || editVersion !== edit) return;
          attached = true;
          message.textContent = 'Redacted file handed to the ChatGPT picker. Verify the attachment and upload completion there. Send was not clicked.';
          message?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' });
        } catch (error) {
          if (versions.get(root) === version && editVersion === edit) message.textContent = error.message || 'Attachment failed. Download and attach manually.';
        } finally { clearTimeout(timer); if (request === current) { request = null; update(); } }
      });
      panel.append(sharing, attach);
    }
    if (!enabled) message.textContent = 'Export blocked: complete OCR and vision review first, then rescan. Export authorization expires after 15 minutes.';
    panel.append(guidance,message,downloads); root.append(panel); listMasks(); update();
    setTimeout(() => panel?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' }), 30);
  }
  return {render, clear, validBox, label};
})();
