const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require('playwright');
const { contexto, fixture, origen } = require('./estadisticas-descargas-helpers.cjs');

const evidencia = process.env.CUTLESS_TEST_EVIDENCE;
const auditoria = process.env.CUTLESS_TEST_AUDIT === '1';
const capturas = { material_entero: 390, material_admin_entero: 1280, presupuesto_entero: 1280, opt_fraccion: 390 };
const precioMaterial = { entero: '10000', medio: '12500.5', centavos: '12500.25', cero: '0', vacio: '', nuevo: '' };
const importes = { entero: ['10000', '5500'], fraccion: ['12500.5', '12500.25'], cero: ['0', '0'], vacio: ['', '0'] };
const campo = (page, nombre) => page.locator(`input[name="${nombre}"]`);

async function abrir(page, caso) {
  const url = origen + fixture.rutas[caso];
  assert.equal((await page.goto(url)).status(), 200, caso);
  assert.equal(page.url(), url, caso);
  return url;
}

function esperado(caso) {
  if (caso === 'opt_nueva') return ['', ''];
  const clave = caso.split('_').at(-1);
  if (caso.startsWith('material_')) return [precioMaterial[clave]];
  if (caso === 'perfil_admin') return importes.entero;
  if (caso === 'presupuesto_desde_cero') return importes.vacio;
  return importes[clave] || importes.vacio;
}

async function auditar(page, ancho) {
  for (const caso of Object.keys(fixture.rutas)) {
    await abrir(page, caso);
    const form = caso.startsWith('material_') ? ['precio'] : caso.startsWith('perfil_')
      ? ['precio_tablero_predeterminado', 'mano_obra_predeterminada'] : ['precio_tablero', 'mano_obra'];
    const valores = await Promise.all(form.map(nombre => campo(page, nombre).inputValue()));
    const tipos = await Promise.all(form.map(nombre => campo(page, nombre).getAttribute('type')));
    console.log(ancho, caso, JSON.stringify(valores), tipos.join(','));
    if (!auditoria) {
      assert.deepEqual(valores, esperado(caso), caso);
      const esTexto = caso.startsWith('material_') || (caso.startsWith('opt_') && !caso.startsWith('opt_admin_'));
      assert.deepEqual(tipos, form.map(() => esTexto ? 'text' : 'number'), caso);
      if (caso === 'material_entero' || caso === 'material_admin_entero' || caso === 'opt_entero') {
        assert.equal(await campo(page, 'ancho').inputValue(), '122.1234', caso);
      }
    }
    if (evidencia && capturas[caso] === ancho) {
      const entrada = campo(page, form[0]);
      await entrada.evaluate(e => e.scrollIntoView({ block: 'center', behavior: 'instant' }));
      await page.screenshot({ path: path.join(evidencia, `${caso}-${auditoria ? 'antes' : 'despues'}-${ancho}.png`) });
    }
  }
}

async function catalogo(page, ancho) {
  for (const caso of ['opt_nueva', 'opt_vacio', 'opt_entero']) {
    await abrir(page, caso);
    if (caso === 'opt_nueva') await page.locator('#btnCostosToggle').click();
    for (const [nombre, id] of Object.entries(fixture.materiales)) {
      await page.locator('#material_select').selectOption(String(id));
      const valor = await campo(page, 'precio_tablero').inputValue();
      const precio = caso === 'opt_entero' ? (auditoria ? '10000.00' : '10000') : precioMaterial[nombre];
      assert.equal(valor, precio, caso + ' ' + nombre);
      console.log(ancho, caso, 'selección', nombre, JSON.stringify(valor));
    }
  }
}

async function verificarError(page, caso, entradas, campoInvalido) {
  const url = await abrir(page, caso);
  for (const [nombre, valor] of Object.entries(entradas)) await campo(page, nombre).fill(valor);
  await campo(page, campoInvalido).fill('');
  const respuesta = page.waitForResponse(r => r.url() === url && r.request().method() === 'POST');
  await Promise.all([
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
    campo(page, campoInvalido).evaluate(e => e.form.submit()),
  ]);
  assert.equal((await respuesta).status(), 200);
  for (const [nombre, valor] of Object.entries(entradas)) assert.equal(await campo(page, nombre).inputValue(), valor);
  console.log(caso, 'POST inválido conservó', JSON.stringify(entradas));
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CUTLESS_TEST_CHROMIUM });
  try {
    console.log('Chromium', browser.version());
    for (const [width, height] of [[390, 844], [1280, 920]]) {
      const context = await contexto(browser, origen, { viewport: { width, height }, reducedMotion: 'reduce' });
      try {
        const page = await context.newPage();
        await auditar(page, width);
        await catalogo(page, width);
        if (!auditoria) {
          await verificarError(page, 'material_nuevo', { precio: '12500,50' }, 'ancho');
          await verificarError(page, 'material_admin_entero', { precio: '10000.00' }, 'ancho');
          await verificarError(page, 'opt_entero', { precio_tablero: '12500,50', mano_obra: '5500.00' }, 'ancho');
          await verificarError(page, 'presupuesto_desde_entero', { precio_tablero: '10000.00', mano_obra: '12500.50' }, 'fecha_validez');
        }
      } finally {
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
