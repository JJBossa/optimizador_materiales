const {test} = require('node:test');
const assert = require('node:assert/strict');
const {filaCsv, validarMedida} = require('../../static/cutless/js/template-piece-editor.js');

test('serializa nombres con comillas, comas, saltos y Unicode usando CSV reversible', () => {
  assert.equal(filaCsv(['"Puerta", Ω\nNorte', '12,50', '30', '2']),
    '"""Puerta"", Ω\nNorte",12.50,30,2');
});

test('valida límites físicos de piezas en las cinco unidades', () => {
  const contrato = {factores:{cm:1,mm:.1,m:100,in:2.54,ft:30.48},minCm:.1,maxCm:300};
  for (const [unidad, medida] of [['cm','40'], ['mm','400'], ['m','0,4'], ['in','16'], ['ft','1.3']]) {
    assert.equal(validarMedida(medida,unidad,contrato), true);
  }
  assert.equal(validarMedida('3000','mm',contrato), true);
  assert.equal(validarMedida('3001','mm',contrato), false);
  assert.equal(validarMedida('0.9','mm',contrato), false);
});
