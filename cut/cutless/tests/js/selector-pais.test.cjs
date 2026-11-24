const { test } = require('node:test');
const assert = require('node:assert/strict');
const { buscar, iniciar } = require('../../static/cutless/js/selector-pais.js');

const telefono = [
  { codigo: '', etiqueta: 'Selecciona un país o territorio' },
  { codigo: 'CN', etiqueta: '🇨🇳 China (+86)', prefijo: '86' },
  { codigo: 'CL', etiqueta: '🇨🇱 Chile (+56)', prefijo: '56' },
  { codigo: 'ES', etiqueta: '🇪🇸 España (+34)', prefijo: '34' },
  { codigo: 'CA', etiqueta: '🇨🇦 Canadá (+1)', prefijo: '1' },
  { codigo: 'US', etiqueta: '🇺🇸 Estados Unidos (+1)', prefijo: '1' },
  { codigo: 'DO', etiqueta: '🇩🇴 República Dominicana (+1)', prefijo: '1' },
];
const codigos = opciones => opciones.map(opcion => opcion.codigo);

test('busca por nombre sin distinguir mayúsculas, tildes o espacios exteriores', () => {
  assert.deepEqual(codigos(buscar(telefono, ' CHi ', true)), ['CN', 'CL']);
  assert.deepEqual(codigos(buscar(telefono, 'Espana', true)), ['ES']);
  assert.deepEqual(codigos(buscar(telefono, 'CANADÁ', true)), ['CA']);
});

test('busca prefijos exactos con o sin + y devuelve todos los países que los comparten', () => {
  for (const consulta of ['+56', '56']) {
    assert.deepEqual(codigos(buscar(telefono, consulta, true)), ['CL']);
  }
  assert.deepEqual(codigos(buscar(telefono, '+1', true)), ['CA', 'US', 'DO']);
  assert.deepEqual(buscar(telefono, '+999', true), []);
});

test('prioriza códigos exactos y conserva el catálogo original al abrirlo completo', () => {
  const postal = [
    { codigo: '', etiqueta: 'Selecciona un país o territorio' },
    { codigo: 'EG', etiqueta: 'Egipto' },
    { codigo: 'PT', etiqueta: 'Portugal' },
    { codigo: 'AQ', etiqueta: 'Antártida' },
    { codigo: 'ZZ', etiqueta: '< & > (guardado anteriormente)' },
  ];
  assert.deepEqual(codigos(buscar(postal, 'pt', false)), ['PT', 'EG']);
  assert.deepEqual(codigos(buscar(postal, 'Antartida', false)), ['AQ']);
  assert.deepEqual(codigos(buscar(postal, '< & >', false)), ['ZZ']);
  assert.deepEqual(buscar(postal, '56', false), []);
  assert.deepEqual(buscar(postal, '', false), postal);
  assert.deepEqual(buscar(telefono, ' ', true), telefono);
});

test('omite instancias sin selector, etiqueta, ID u opciones', () => {
  for (const selector of [null, {}, { id: 'pais', labels: [] }, { id: 'pais', labels: [{}], options: [] }]) {
    assert.doesNotThrow(() => iniciar({ querySelector: () => selector }));
    assert.ok(!selector?.hidden);
  }
});
