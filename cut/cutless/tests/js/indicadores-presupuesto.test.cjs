const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../../static/cutless/js/indicadores-presupuesto.js'), 'utf8');

async function mostrar(respuesta, totalClp = '2400.00') {
  const estado = {};
  const lista = {hidden: true};
  const conversion = {textContent: 'Sin tipo de cambio'};
  const filas = new Map(['dolar', 'uf'].map(codigo => [codigo, {'[data-valor]': {}, '[data-referencia]': {}}]));
  const elementos = {
    '[data-indicadores-estado]': estado,
    '.indicadores-presupuesto__datos': lista,
    '[data-indicador="conversion"] [data-valor]': conversion,
  };
  for (const [codigo, campos] of filas) {
    elementos[`[data-indicador="${codigo}"]`] = {querySelector: selector => campos[selector]};
  }
  const url = '/cutless/presupuestos/indicadores/';
  const panel = {
    dataset: {indicadoresUrl: url, totalClp},
    querySelector: selector => elementos[selector],
  };
  const peticiones = [];
  vm.runInNewContext(script, {
    document: {querySelector: () => panel},
    fetch: async ruta => {
      peticiones.push(ruta);
      return {ok: true, json: async () => respuesta};
    },
  });
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(peticiones, [url]);
  assert.equal(panel.dataset.totalClp, totalClp);
  return {estado, lista, conversion, filas};
}

test('convierte el total CLP a USD con redondeo y muestra las fechas individuales', async () => {
  const {estado, lista, conversion, filas} = await mostrar({desde_cache: true, indicadores: {
    dolar: {valor: 800, fecha: '2026-01-09', fecha_anterior: true},
    uf: {valor: 40000.25, fecha: '2026-01-10', fecha_anterior: false},
  }}, '2410.00');
  assert.equal(lista.hidden, false);
  assert.match(conversion.textContent, /^≈ USD\s+3,01$/);
  assert.equal(estado.textContent, 'Valores en caché.');
  assert.equal(filas.get('dolar')['[data-referencia]'].dateTime, '2026-01-09');
  assert.match(filas.get('dolar')['[data-referencia]'].textContent, /^Dato del 9 ene 2026$/);
  assert.equal(filas.get('uf')['[data-referencia]'].dateTime, '2026-01-10');
  assert.match(filas.get('uf')['[data-referencia]'].textContent, /^Hoy, 10 ene 2026$/);
});

test('redondea solo las tarjetas CLP y convierte con el dólar original', async () => {
  const dolar = Object.freeze({valor: 800.75, fecha: '2026-01-09', fecha_anterior: true});
  const uf = Object.freeze({valor: 40000.25, fecha: '2026-01-10', fecha_anterior: false});
  const {conversion, filas} = await mostrar({desde_cache: false, indicadores: {dolar, uf}}, '80075.00');

  assert.match(filas.get('dolar')['[data-valor]'].textContent, /^≈ CLP\s+801$/);
  assert.match(filas.get('uf')['[data-valor]'].textContent, /^≈ CLP\s+40\.000$/);
  assert.match(conversion.textContent, /^≈ USD\s+100,00$/);
});

test('muestra la UF aún sin dólar y deja la conversión sin tipo de cambio', async () => {
  const {lista, conversion} = await mostrar({desde_cache: false, indicadores: {
    uf: {valor: 40000, fecha: '2026-01-10', fecha_anterior: false},
  }});
  assert.equal(lista.hidden, false);
  assert.equal(conversion.textContent, 'Sin tipo de cambio');
});

test('sin indicadores muestra el aviso y oculta los valores', async () => {
  const {lista, estado} = await mostrar({desde_cache: false, indicadores: {}});
  assert.equal(lista.hidden, true);
  assert.equal(estado.textContent, 'Indicadores no disponibles por el momento.');
});
