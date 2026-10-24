// Synthetic browser/DOM doubles: these tests do not claim live ChatGPT support.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = name => fs.readFileSync(path.join(__dirname, name), 'utf8');
function panel(fetcher) {
  const nodes = new Map();
  const node = id => {
    if (!nodes.has(id)) nodes.set(id, {value: '', checked: false, disabled: false, hidden: true,
      textContent: '', style: {}, events: {}, addEventListener(name, fn) { this.events[name] = fn; }});
    return nodes.get(id);
  };
  const event = () => ({addListener(fn) { this.listener = fn; }});
  const chrome = {runtime: {openOptionsPage() {}},
    permissions: {request: async () => true},
    tabs: {onActivated: event(), onUpdated: event(),
      query: async () => [{id: 1, url: 'https://chatgpt.com/'}],
      get: async () => ({id: 1, url: 'https://chatgpt.com/'})},
    scripting: {executeScript: async () => [{result: {text: '', url: 'https://chatgpt.com/'}}]},
    storage: {onChanged: event(), local: {get: async () => ({bridgeToken: 'synthetic-test-token'})}}};
  let copies = 0;
  const context = vm.createContext({document: {querySelector: node}, chrome,
    navigator: {clipboard: {writeText: async () => { copies++; }}},
    fetch: fetcher, URL, AbortController, setTimeout, clearTimeout, chatgptComposer() {}, PrivacyGatePreview: {clear() {}}});
  vm.runInContext(source('popup.js'), context);
  node('#source').value = 'synthetic text'; node('#mode').value = 'off';
  return {node, chrome, copies: () => copies,
    fire: (id, event = 'click') => node(id).events[event]()};
}
const reply = status => ({ok: true, json: async () => ({status, sanitized_text: '[PERSON_1]', findings: [], warnings: []})});
test('blocked results cannot be copied even if checkbox is forced', async () => {
  const p = panel(async () => reply('BLOCKED_UNVERIFIED'));
  await p.fire('#scan'); p.node('#reviewed').checked = true;
  await p.fire('#copy'); assert.equal(p.copies(), 0);
});
test('source and scan mode edits revoke approved result', async () => {
  const p = panel(async () => reply('REVIEW_REQUIRED'));
  for (const id of ['#source', '#mode']) {
    await p.fire('#scan'); p.node('#reviewed').checked = true;
    await p.fire('#copy');
    await p.fire(id, id === '#source' ? 'input' : 'change');
    p.node('#reviewed').checked = true; await p.fire('#copy');
    assert.equal(p.node('#output').hidden, true);
  }
  assert.equal(p.copies(), 2);
});
test('late response cannot approve a changed draft', async () => {
  let resolve, started;
  const began = new Promise(r => { started = r; });
  const p = panel(() => { started(); return new Promise(r => { resolve = r; }); });
  const pending = p.fire('#scan'); await began;
  p.node('#source').value = 'changed'; await p.fire('#source', 'input');
  resolve(reply('READY_FOR_MANUAL_APPROVAL')); await pending;
  assert.equal(p.node('#output').hidden, true);
  p.node('#reviewed').checked = true; await p.fire('#copy'); assert.equal(p.copies(), 0);
});

test('cancelled review rejects its late response and keeps insertion blocked', async () => {
  let resolve, started;
  const began = new Promise(r => { started = r; });
  const p = panel(() => { started(); return new Promise(r => { resolve = r; }); });
  const pending = p.fire('#scan'); await began;
  await p.fire('#cancel');
  resolve(reply('READY_FOR_MANUAL_APPROVAL')); await pending;
  assert.equal(p.node('#output').hidden, true);
  p.node('#reviewed').checked = true; await p.fire('#copy');
  assert.equal(p.copies(), 0);
});

test('late cancelled scan cannot re-enable controls during a newer review', async () => {
  const resolves = [];
  const p = panel(() => new Promise(resolve => resolves.push(resolve)));
  const first = p.fire('#scan');
  await new Promise(resolve => setImmediate(resolve));
  await p.fire('#source', 'input');
  const second = p.fire('#scan');
  await new Promise(resolve => setImmediate(resolve));
  resolves[0](reply('READY_FOR_MANUAL_APPROVAL')); await first;
  assert.equal(p.node('#scan').disabled, true);
  assert.equal(p.node('#output').hidden, true);
  resolves[1](reply('REVIEW_REQUIRED')); await second;
  assert.equal(p.node('#scan').disabled, false);
  assert.equal(p.node('#output').hidden, false);
});
test('failed rescan removes old approval', async () => {
  let fail = false;
  const p = panel(async () => { if (fail) throw new Error(); return reply('REVIEW_REQUIRED'); });
  await p.fire('#scan'); p.node('#reviewed').checked = true;
  fail = true; await p.fire('#scan'); await p.fire('#copy');
  assert.equal(p.copies(), 0); assert.equal(p.node('#output').hidden, true);
});
test('tab switch disconnects target and revokes approval', async () => {
  const p = panel(async () => reply('REVIEW_REQUIRED'));
  await p.fire('#target'); await p.fire('#scan'); p.node('#reviewed').checked = true;
  p.chrome.tabs.onActivated.listener({tabId: 2});
  await p.fire('#insert'); assert.equal(p.node('#insert').disabled, true);
});
function composer(origin = 'https://chatgpt.com', count = 1) {
  class Textarea {
    constructor() { this._value = 'original'; this.events = []; }
    get value() { return this._value; } set value(value) { this._value = value; }
    getClientRects() { return [1]; } getAttribute() { return null; }
    focus() {} dispatchEvent(event) { this.events.push(event); }
  }
  const node = new Textarea();
  const context = vm.createContext({location: {origin, href: origin + '/'},
    document: {querySelectorAll: () => Array(count).fill(node)},
    HTMLTextAreaElement: Textarea, Event: class {constructor(type) { this.type = type; }}});
  vm.runInContext(source('composer.js'), context);
  return {node, call: (...args) => context.chatgptComposer(...args)};
}
test('composer rejects other origins and ambiguous editors', () => {
  assert.ok(composer('https://example.org').call('read').error);
  assert.ok(composer('https://chatgpt.com', 2).call('read').error);
});
test('composer refuses to overwrite changed website text', () => {
  const p = composer(); assert.ok(p.call('insert', 'old text', 'new').error);
  assert.equal(p.node.value, 'original');
});
test('textarea insertion emits only input and verifies inserted draft', () => {
  const p = composer(); assert.equal(p.call('insert', 'original', '[PERSON_1]').inserted, true);
  assert.equal(p.node.value, '[PERSON_1]');
  assert.deepEqual(p.node.events.map(event => event.type), ['input']);
});
function richEditor(accepts) {
  const node = {innerText: 'original', isContentEditable: true,
    getClientRects: () => [1], getAttribute: () => null, focus() {}};
  const commands = [];
  const context = vm.createContext({location: {origin: 'https://chatgpt.com'},
    HTMLTextAreaElement: class {},
    window: {getSelection: () => ({removeAllRanges() {}, addRange() {}})},
    document: {querySelectorAll: () => [node], createRange: () => ({selectNodeContents() {}}),
      execCommand: (command, ui, value) => {
        commands.push(command); if (accepts) node.innerText = value; return accepts;
      }}});
  vm.runInContext(source('composer.js'), context);
  return {node, commands, call: (...args) => context.chatgptComposer(...args)};
}
test('contenteditable uses editing transaction without submit', () => {
  const p = richEditor(true);
  assert.equal(p.call('insert', 'original', 'reviewed draft').inserted, true);
  assert.equal(p.node.innerText, 'reviewed draft');
  assert.deepEqual(p.commands, ['insertText']);
});
test('contenteditable rejection does not report success', () => {
  const p = richEditor(false);
  assert.ok(p.call('insert', 'original', 'reviewed draft').error);
  assert.equal(p.node.innerText, 'original');
});
test('connecting on an unrelated website leaves insertion disconnected', async () => {
  const p = panel(async () => reply('REVIEW_REQUIRED'));
  p.chrome.tabs.query = async () => [{id: 1, url: 'https://example.org/'}];
  await p.fire('#target'); await p.fire('#scan'); p.node('#reviewed').checked = true;
  await p.fire('#reviewed', 'change');
  assert.equal(p.node('#insert').disabled, true);
});
test('shared visual renderer rejects invalid boxes', () => {
  const context = vm.createContext({}); vm.runInContext(source('preview.js'), context);
  const preview = context.PrivacyGatePreview;
  assert.equal(preview.validBox([100, 200, 400, 800]), true);
  for (const value of [null, [1, 2, 3], [-1, 0, 300, 400], [400, 200, 100, 800], [1, 2, 3, 1001]])
    assert.equal(preview.validBox(value), false);
  assert.equal(source('preview.js'), fs.readFileSync(path.join(__dirname, '../privacygate/ui/preview.js'), 'utf8'));
});
