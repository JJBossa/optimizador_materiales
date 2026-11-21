const {test} = require('node:test');
const assert = require('node:assert/strict');
const casos = require('../casos_formato_clp.json');
const {formatearCLP} = require('../../static/cutless/js/formato-clp.js');

test('Django y JavaScript comparten los mismos casos de lectura CLP', () => {
  for (const [monto, esperado, conSigno] of casos) {
    assert.equal(formatearCLP(monto, conSigno), esperado, String(monto));
  }
});

test('acepta números finitos y BigInt sin convertir valores ausentes a cero', () => {
  assert.equal(formatearCLP(1e-8), 'Menos de $1');
  assert.equal(formatearCLP(9007199254740993n), '$9.007.199.254.740.993');
  assert.equal(formatearCLP(-0), '$0');
  for (const monto of [undefined, true, Infinity, NaN]) {
    assert.equal(formatearCLP(monto), '—');
  }
});
