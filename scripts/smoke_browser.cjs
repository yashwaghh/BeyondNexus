/* Real Chromium + installed extension smoke, with synthetic model and page fixtures.
 * Requires dev-only `playwright` and `playwright install chromium`. No cloud calls.
 */
const {chromium} = require('playwright');
const {spawn, spawnSync} = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const token = 'synthetic-browser-token-1234567890';

async function startServer(origin, port = 0) {
  const child = spawn(process.env.PYTHON || 'python', [path.join(root, 'tests/browser_fixture.py'), origin, String(port)], {cwd: root});
  let text = '';
  const address = await new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('exit', code => reject(new Error(`Synthetic server exited: ${code}`)));
    child.stdout.on('data', data => {
      text += data.toString();
      if (text.includes('\n')) resolve(JSON.parse(text.split('\n')[0]).origin);
    });
  });
  return {child, address};
}

(async () => {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'privacygate-browser-'));
  let context, server;
  try {
    context = await chromium.launchPersistentContext(profile, {
      headless: true,
      channel: 'chromium',
      ignoreDefaultArgs: ['--disable-extensions'],
      ...(process.env.BROWSER_EXECUTABLE ? {executablePath: process.env.BROWSER_EXECUTABLE} : {}),
      args: [`--disable-extensions-except=${path.join(root, 'extension')}`, `--load-extension=${path.join(root, 'extension')}`]
    });
    context.setDefaultTimeout(20000);
    const worker = context.serviceWorkers()[0] || await context.waitForEvent('serviceworker', {timeout: 20000});
    const id = new URL(worker.url()).host;
    server = await startServer(`chrome-extension://${id}`, 8765);
    const errors = [], outbound = [];
    context.on('request', request => {
      if (/^https?:/.test(request.url()) && !request.url().startsWith(server.address)
          && !request.url().startsWith('https://chatgpt.com/')) outbound.push(request.url());
    });
    const panel = await context.newPage();
    panel.on('pageerror', error => errors.push(error.message));
    await panel.goto(`chrome-extension://${id}/options.html`);
    await panel.locator('#token').fill(token);
    await panel.locator('#save').click();
    await panel.locator('#test').click();
    await panel.waitForFunction(() => document.querySelector('#message').textContent.startsWith('Connected:'));
    await panel.goto(`chrome-extension://${id}/popup.html`);
    await panel.locator('#source').fill('Email demo@example.org');
    await panel.locator('#mode').selectOption('off');
    await panel.locator('#scan').click();
    await panel.waitForFunction(() => document.querySelector('#result').value.includes('[EMAIL_1]'));
    await panel.locator('#reviewed').check();
    assert.equal(await panel.locator('#copy').isEnabled(), true);
    await panel.locator('#source').fill('changed');
    assert.equal(await panel.locator('#copy').isDisabled(), true);
    console.log('PASS: installed extension authenticates to actual bridge, scans and invalidates approval.');

    // Exercise actual contenteditable editing in the browser, with no cloud request.
    await context.route('https://chatgpt.com/**', route => route.fulfill({contentType: 'text/html',
      body: '<!doctype html><div id="prompt-textarea" contenteditable="true">original</div><button id="send">Send</button><script>window.sent=0;document.querySelector("#send").onclick=()=>window.sent++;</script>'}));
    const chat = await context.newPage(); await chat.goto('https://chatgpt.com/');
    await chat.addScriptTag({path: path.join(root, 'extension/composer.js')});
    const insertion = await chat.evaluate(() => chatgptComposer('insert', 'original', 'Reviewed synthetic draft'));
    assert.equal(insertion.inserted, true);
    assert.equal(await chat.evaluate(() => window.sent), 0);
    assert.equal(await chat.locator('#prompt-textarea').innerText(), 'Reviewed synthetic draft');
    const stale = await chat.evaluate(() => chatgptComposer('insert', 'original', 'wrong'));
    assert.ok(stale.error);
    console.log('PASS: real Chromium contenteditable insertion; stale draft rejected; Send untouched (synthetic ChatGPT page).');

    // Exercise actual extension script injection with declared, scoped host access.
    const chatId = await panel.evaluate(async () => {
      const tabs = await chrome.tabs.query({url: 'https://chatgpt.com/*'}); return tabs[0].id;
    });
    const injected = await panel.evaluate(async tabId => {
      const [{result}] = await chrome.scripting.executeScript({target: {tabId},
        func: chatgptComposer, args: ['insert', 'Reviewed synthetic draft', 'Extension-reviewed draft']});
      return result;
    }, chatId);
    assert.equal(injected.inserted, true); assert.equal(await chat.evaluate(() => window.sent), 0);
    console.log('PASS: actual extension permission and isolated-world composer insertion on synthetic ChatGPT page.');

    // Evaluate the panel while ChatGPT stays the active tab, as it does with a
    // sidebar. This exercises the actual controller, without mocking chrome APIs.
    await chat.bringToFront();
    await panel.evaluate(() => document.querySelector('#target').click());
    await panel.waitForFunction(() => document.querySelector('#target-label').textContent.startsWith('ChatGPT connected'));
    await panel.evaluate(() => {
      const source = document.querySelector('#source'); source.value = 'Email demo@example.org';
      source.dispatchEvent(new Event('input', {bubbles: true})); document.querySelector('#scan').click();
    });
    await panel.waitForFunction(() => !document.querySelector('#output').hidden && document.querySelector('#result').value.includes('[EMAIL_1]'));
    await panel.evaluate(() => {
      const review = document.querySelector('#reviewed'); review.checked = true;
      review.dispatchEvent(new Event('change', {bubbles: true})); document.querySelector('#insert').click();
    });
    await panel.waitForFunction(() => document.querySelector('#message').textContent.startsWith('Inserted into ChatGPT'));
    assert.equal(await chat.locator('#prompt-textarea').innerText(), 'Email [EMAIL_1]');
    assert.equal(await chat.evaluate(() => window.sent), 0);
    console.log('PASS: full panel connect → scan → approval → real extension insertion flow; no Send.');

    // Request an opt-in preview through the actual installed extension fetch path.
    await panel.bringToFront();
    const image = await panel.evaluate(() => {
      const canvas = document.createElement('canvas'); canvas.width = 900; canvas.height = 550;
      const ctx = canvas.getContext('2d'); ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, 900, 550);
      ctx.fillStyle = '#18261e'; ctx.font = '32px sans-serif';
      ctx.fillText('SYNTHETIC ID - NOT A REAL DOCUMENT', 40, 70);
      ctx.fillText('Example identity number: 0000 0000 0000', 90, 320);
      return canvas.toDataURL('image/png').split(',')[1];
    });
    await panel.locator('#upload').setInputFiles({name: 'synthetic.png', mimeType: 'image/png', buffer: Buffer.from(image, 'base64')});
    await panel.locator('#scan-file').click();
    await panel.locator('.preview-download').waitFor();
    assert.equal(await panel.locator('canvas').count(), 1);
    assert.equal(await panel.locator('#copy').isDisabled(), true);
    assert.equal(await panel.locator('#insert').isDisabled(), true);
    assert.ok((await panel.locator('#document-preview').innerText()).includes('location unavailable'));
    const pixel = await panel.locator('canvas').evaluate(canvas => [...canvas.getContext('2d').getImageData(90, 300, 1, 1).data]);
    assert.ok(pixel[0] > 150 && pixel[1] < 100, 'Expected red box at normalized left boundary');
    fs.mkdirSync(path.join(root, 'reports'), {recursive: true});
    await panel.setViewportSize({width: 450, height: 1200});
    await panel.screenshot({path: path.join(root, 'reports/extension-boxes.png'), fullPage: true});
    await panel.setViewportSize({width: 320, height: 900});
    assert.equal(await panel.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    console.log('PASS: real extension file upload, aligned visible box, unlocated finding and annotated download.');


    // Exercise the actual redaction editor, binary export endpoint and download.
    assert.equal(await panel.locator('.export-png').isDisabled(), true);
    await panel.locator('.masked-toggle').check();
    await panel.locator('.export-reviewed').check();
    await panel.locator('.export-png').click();
    await panel.locator('.redacted-download').waitFor();
    const redactedPixels = await panel.evaluate(async () => {
      const blob = await (await fetch(document.querySelector('.redacted-download').href)).blob();
      const image = await createImageBitmap(blob);
      const canvas = document.createElement('canvas'); canvas.width=image.width; canvas.height=image.height;
      const ctx=canvas.getContext('2d'); ctx.drawImage(image,0,0);
      return [...ctx.getImageData(100,300,1,1).data];
    });
    assert.deepEqual(redactedPixels, [0,0,0,255]);
    const redactedReceived = panel.waitForEvent('download'); await panel.locator('.redacted-download').click();
    const redactedFile = await redactedReceived;
    assert.equal(redactedFile.suggestedFilename(), 'privacygate-redacted.png');
    await redactedFile.saveAs(path.join(root,'reports/redacted-example.png')); await redactedFile.delete();
    await panel.locator('.masked-toggle').uncheck(); await panel.locator('.masked-toggle').check();
    await panel.locator('.export-reviewed').check();
    await panel.route('**/v1/redact-export', route => route.fulfill({status:200,contentType:'application/json',body:'{}'}));
    await panel.locator('.export-png').click();
    await panel.getByText('Invalid export response; no download created.').waitFor();
    assert.equal(await panel.locator('.redacted-download').count(),0);
    await panel.unroute('**/v1/redact-export');
    await panel.locator('.mask-list button').first().click();
    await panel.locator('.undo-mask').click();
    assert.equal(await panel.locator('.mask-list li').count(),1);
    assert.equal(await panel.locator('.export-reviewed').isChecked(),false);
    await panel.locator('.mask-list button').first().click();
    assert.equal(await panel.locator('.export-reviewed').isChecked(), false);
    assert.equal(await panel.locator('.redacted-download').count(), 0);
    const bounds = await panel.locator('canvas').boundingBox();
    await panel.mouse.move(bounds.x+bounds.width*.1,bounds.y+bounds.height*.5);
    await panel.mouse.down();
    // Approval acquired during a drag must still be revoked when the new mask commits.
    await panel.evaluate(() => { const box=document.querySelector('.export-reviewed'); box.checked=true; box.dispatchEvent(new Event('change')); });
    await panel.mouse.move(bounds.x+bounds.width*.85,bounds.y+bounds.height*.65); await panel.mouse.up();
    assert.equal(await panel.locator('.export-reviewed').isChecked(),false);
    assert.equal(await panel.locator('.mask-list li').count(), 1);
    assert.equal(await panel.locator('.export-png').isDisabled(), true);
    await panel.locator('.export-reviewed').check();
    await panel.locator('.export-pdf').click(); await panel.locator('.redacted-download').waitFor();
    await panel.screenshot({path:path.join(root,'reports/redaction-editor.png'),fullPage:true});
    await panel.locator('.mask-page').click();
    assert.equal(await panel.locator('.export-reviewed').isChecked(), false);
    assert.equal(await panel.locator('.mask-list li').count(), 1);
    await panel.locator('#source').fill('changed input');
    assert.equal(await panel.locator('.redacted-download').count(),0);
    console.log('PASS: edited masks, destructive PNG pixels, approved PDF export and stale-download invalidation.');

    const ui = await context.newPage(); await ui.goto(server.address);
    ui.on('pageerror', error => errors.push(error.message));
    await ui.locator('#upload').setInputFiles({name: 'synthetic.png', mimeType: 'image/png', buffer: Buffer.from(image, 'base64')});
    await ui.locator('#scan-file').click(); await ui.locator('.preview-download').waitFor();
    assert.equal(await ui.locator('#copy').isDisabled(), true);
    await ui.screenshot({path: path.join(root, 'reports/local-boxes.png'), fullPage: true});
    const download = await ui.locator('.preview-download').getAttribute('href');
    assert.ok(download.startsWith('data:image/png;base64,'));
    fs.writeFileSync(path.join(root, 'reports/annotated-example.png'), Buffer.from(download.split(',')[1], 'base64'));
    const received = ui.waitForEvent('download'); await ui.locator('.preview-download').click();
    const file = await received;
    assert.ok(file.suggestedFilename().includes('NOT-REDACTED')); await file.delete();
    // Cancel a delayed local-UI scan and reject its late completion.
    let started, release;
    const began=new Promise(resolve => {started=resolve;});
    const held=new Promise(resolve => {release=resolve;});
    await ui.route('**/v1/scan', async route => { started(); await held; try { await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({status:'READY_FOR_MANUAL_APPROVAL',sanitized_text:'late result',findings:[],warnings:[]})}); } catch {} });
    await ui.locator('#source').fill('synthetic text'); await ui.locator('#mode').selectOption('off');
    await ui.locator('#scan').click(); await began;
    assert.equal(await ui.locator('#scan-file').isDisabled(),true);
    await ui.locator('#cancel').click(); release();
    await ui.unroute('**/v1/scan');
    assert.equal(await ui.locator('#result').inputValue(),'');
    assert.equal(await ui.locator('#scan-file').isDisabled(),false);
    assert.equal(await ui.locator('#copy').isDisabled(),true);
    console.log('PASS: local UI cancellation, mutually exclusive scans, undo, drag-approval reset and invalid export rejection.');
    const fixture = spawnSync(process.env.PYTHON || 'python', ['-c',
      "import runpy,base64; m=runpy.run_path('tests/test_uploads.py'); print(base64.b64encode(m['make_pdf'](2)).decode())"], {cwd: root, encoding: 'utf8'});
    assert.equal(fixture.status, 0);
    await ui.locator('#upload').setInputFiles({name: 'synthetic.pdf', mimeType: 'application/pdf', buffer: Buffer.from(fixture.stdout.trim(), 'base64')});
    await ui.locator('#scan-file').click();
    await ui.waitForFunction(() => document.querySelectorAll('.preview-download').length === 2);
    assert.equal(await ui.locator('canvas').count(), 2);
    await ui.screenshot({path: path.join(root, 'reports/pdf-boxes.png'), fullPage: true});
    await ui.locator('.masked-toggle').check(); await ui.locator('.export-reviewed').check();
    await ui.locator('.export-pdf').click(); await ui.locator('.redacted-download').waitFor();
    const pdfReceived = ui.waitForEvent('download'); await ui.locator('.redacted-download').click();
    const pdfFile = await pdfReceived; await pdfFile.saveAs(path.join(root,'reports/redacted-two-pages.pdf')); await pdfFile.delete();
    const verified = spawnSync(process.env.PYTHON || 'python', ['-c',
      "from pypdf import PdfReader; import pypdfium2 as p; r=PdfReader('reports/redacted-two-pages.pdf'); assert len(r.pages)==2; assert not any(x.extract_text() for x in r.pages); assert r.metadata is None; d=p.PdfDocument('reports/redacted-two-pages.pdf'); d[0].render().to_pil().save('reports/redacted-pdf-page.png')"], {cwd:root,encoding:'utf8'});
    assert.equal(verified.status,0,verified.stderr);
    console.log('PASS: two rendered PDF pages with per-page boxes; actual annotated PNG download works.');
    assert.deepEqual(errors, []); assert.deepEqual(outbound, []);
    console.log('PASS: local UI annotated preview; no page errors or unexpected test requests.');
    if (process.argv.includes('--live-site')) {
      // Explicit optional check: fresh unauthenticated page; synthetic text only;
      // no Send click. Never run against the user's existing browser profile.
      await context.unroute('https://chatgpt.com/**');
      const live = await context.newPage();
      await live.goto('https://chatgpt.com/', {waitUntil: 'domcontentloaded', timeout: 30000});
      try {
        await live.locator('#prompt-textarea').waitFor({timeout: 20000});
      } catch (error) {
        await live.screenshot({path: path.join(root, 'reports/live-site-check.png'), fullPage: true});
        console.log('Live-site title:', await live.title());
        console.log('Live editor candidates:', await live.locator('textarea,[contenteditable]').evaluateAll(nodes => nodes.map(node => ({tag: node.tagName, id: node.id, editable: node.getAttribute('contenteditable')}))));
        throw error;
      }
      await live.bringToFront();
      await panel.evaluate(() => document.querySelector('#target').click());
      await panel.waitForFunction(() => document.querySelector('#target-label').textContent.startsWith('ChatGPT connected'));
      await panel.evaluate(() => {
        const source = document.querySelector('#source'); source.value = 'Email demo@example.org';
        source.dispatchEvent(new Event('input', {bubbles: true})); document.querySelector('#scan').click();
      });
      await panel.waitForFunction(() => !document.querySelector('#output').hidden && document.querySelector('#result').value.includes('[EMAIL_1]'));
      await panel.evaluate(() => {
        const review = document.querySelector('#reviewed'); review.checked = true;
        review.dispatchEvent(new Event('change', {bubbles: true})); document.querySelector('#insert').click();
      });
      await panel.waitForFunction(() => document.querySelector('#message').textContent.startsWith('Inserted into ChatGPT'));
      assert.equal(await live.locator('#prompt-textarea').innerText(), 'Email [EMAIL_1]');
      console.log('PASS: current live unauthenticated ChatGPT composer accepted reviewed synthetic draft; no Send action invoked.');
    }
  } finally {
    if (server) server.child.kill();
    if (context) await context.close();
    // Test-only browser profile lives in OS temp; leave cleanup to OS to avoid locked files.
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
