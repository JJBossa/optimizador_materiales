const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {resolve} = require('node:path');
const {test} = require('node:test');
const {runInNewContext} = require('node:vm');

function load(script, context) {
  runInNewContext(readFileSync(resolve(__dirname, '../../static/cutless/js', script), 'utf8'), context);
}

test('el selector de presupuestos interpreta OPT como un código completo', () => {
  const rows = [
    {dataset: {code: 'OPT-0001', search: 'Cocina · OPT-0001'}, querySelector: () => ({checked: true})},
    {dataset: {code: 'OPT-10001', search: 'Sala · OPT-10001'}, querySelector: () => ({checked: false})},
    {dataset: {code: 'OPT-0002', search: 'Pieza OPT-0001 · OPT-0002'}, querySelector: () => ({checked: false})},
  ];
  const listeners = {};
  const input = {value: '', addEventListener: (event, callback) => { listeners[event] = callback; }};
  const nodes = new Map([['#budget-plan-search', input]]);
  const root = {
    dataset: {}, addEventListener() {},
    querySelectorAll: selector => selector === '[data-budget-plan]' ? rows : [],
    querySelector(selector) {
      if (!nodes.has(selector)) nodes.set(selector, {addEventListener() {}});
      return nodes.get(selector);
    },
  };
  load('budget-selection.js', {document: {querySelector: () => root}, window: {}});
  function visibles(value) {
    input.value = value;
    listeners.input();
    return rows.filter(row => !row.hidden).map(row => row.dataset.code);
  }
  assert.deepEqual(visibles('opt-1'), ['OPT-0001']);
  assert.deepEqual(visibles('OPT-10001'), ['OPT-10001']);
  assert.deepEqual(visibles('Pieza'), ['OPT-0002']);
  assert.match(nodes.get('#budget-selection-count').textContent, /^1 /);
});

test('el visor conserva el ID para descargar y el código para mostrar', async () => {
  const requests = [];
  const nodes = new Map();
  const document = {
    getElementById(id) {
      if (!nodes.has(id)) nodes.set(id, {
        addEventListener() {}, setAttribute() {}, replaceChildren() {}, classList: {remove() {}},
        content: {cloneNode: () => ({})},
      });
      return nodes.get(id);
    },
  };
  const window = {addEventListener() {}};
  load('history-board-viewer.js', {
    document, window, AbortController, matchMedia: () => ({matches: true}),
    bootstrap: {Modal: {getOrCreateInstance: () => ({show() {}})}},
    fetch: async url => { requests.push(url); return {ok: false, status: 500}; },
  });
  await window.abrirModalImagen('', 472, 'OPT-0001');
  assert.equal(nodes.get('modalImagenLabel').textContent, 'Tableros · OPT-0001');
  await window.abrirModalImagen('', 472);
  assert.equal(nodes.get('modalImagenLabel').textContent, 'Tableros');
  assert.ok(requests.every(url => url.startsWith('/cutless/api/tableros/472/')));
});
