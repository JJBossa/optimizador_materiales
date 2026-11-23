const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require('playwright');
const { contexto, fixture, origen, origenLocal } = require('./estadisticas-descargas-helpers.cjs');

const base = process.env.CUTLESS_TEST_BASE && origenLocal('CUTLESS_TEST_BASE');
const evidencia = process.env.CUTLESS_TEST_EVIDENCE;
const mensaje = 'La fecha de validez no puede ser anterior a hoy. Selecciona la fecha actual o una posterior.';
const fecha = page => page.getByLabel('Válido Hasta');
const notas = page => page.locator('#id_notas');

async function abrir(page, url) {
  assert.equal((await page.goto(url)).status(), 200);
  assert.equal(page.url(), url);
}

async function enviar(page, url, codigo) {
  const [respuesta] = await Promise.all([
    page.waitForResponse(r => r.url() === url && r.request().method() === 'POST'),
    page.getByRole('button', { name: 'Guardar cambios', exact: true }).click(),
  ]);
  assert.equal(respuesta.status(), codigo);
  if (codigo === 302) await page.waitForURL(new URL(respuesta.headers().location, url).href);
}

async function comprobarError(page, textoNotas) {
  const error = page.locator('#id_fecha_validez_error');
  await error.waitFor();
  assert.equal((await error.textContent()).trim(), mensaje);
  assert.equal(await fecha(page).getAttribute('aria-invalid'), 'true');
  assert.equal(await fecha(page).getAttribute('aria-describedby'), 'id_fecha_validez_helptext id_fecha_validez_error');
  assert.equal(await fecha(page).inputValue(), fixture.ayer);
  assert.equal(await notas(page).inputValue(), textoNotas);
  assert.ok(await page.locator('#opt_' + fixture.plan).isChecked());
  return error;
}

async function capturar(page, locator, nombre) {
  if (!evidencia) return;
  await locator.evaluate(e => e.scrollIntoView({ block: 'center', behavior: 'instant' }));
  await page.screenshot({ path: path.join(evidencia, nombre) });
}

async function comprobarBase(page, ruta, ancho) {
  const url = base + ruta;
  await abrir(page, url);
  assert.equal(await fecha(page).getAttribute('min'), null);
  assert.ok((await fecha(page).inputValue()) > fixture.hoy);
  await fecha(page).fill(fixture.ayer);
  assert.equal(await fecha(page).evaluate(e => e.validity.valid), true);
  await enviar(page, url, 302);
  const detalle = page.locator('p').filter({ hasText: 'Válido hasta:' });
  const [yyyy, mm, dd] = fixture.ayer.split('-');
  assert.match(await detalle.textContent(), new RegExp(dd + '/' + mm + '/' + yyyy));
  await capturar(page, detalle, 'antes-' + ancho + '.png');
  await abrir(page, url);
  assert.equal(await fecha(page).inputValue(), fixture.ayer);
  console.log(`Base ${ancho} px: POST 302 y fecha pasada persistida.`);
}

async function comprobarEdicion(page, casos, ancho, js) {
  const vigente = origen + casos.vigente;
  const vencido = origen + casos.vencido;
  const textoNotas = 'Notas sintéticas PRE-02';
  await abrir(page, vigente);
  assert.equal(await fecha(page).getAttribute('type'), 'date');
  assert.equal(await fecha(page).getAttribute('min'), fixture.hoy);
  await notas(page).fill(textoNotas);
  await fecha(page).fill(fixture.ayer);
  assert.ok(await fecha(page).evaluate(e => e.validity.rangeUnderflow));
  await fecha(page).evaluate(e => e.removeAttribute('min'));
  await enviar(page, vigente, 200);
  const error = await comprobarError(page, textoNotas);
  assert.equal(await fecha(page).getAttribute('min'), fixture.hoy);
  if (js) await capturar(page, error, 'despues-' + ancho + '.png');
  const nuevaFecha = js ? fixture.hoy : fixture.manana;
  await fecha(page).fill(nuevaFecha);
  await enviar(page, vigente, 302);
  await abrir(page, vigente);
  assert.equal(await fecha(page).inputValue(), nuevaFecha);

  await abrir(page, vencido);
  assert.equal(await fecha(page).inputValue(), fixture.vencida);
  assert.equal(await fecha(page).getAttribute('min'), null);
  assert.ok(await fecha(page).evaluate(e => e.validity.valid));
  assert.match(await page.locator('#id_fecha_validez_helptext').textContent(), /conservar la fecha vencida guardada/);
  if (ancho === 390 && js) await capturar(page, fecha(page), 'borrador-vencido-390.png');
  await notas(page).fill(textoNotas);
  await enviar(page, vencido, 302);
  await abrir(page, vencido);
  assert.equal(await fecha(page).inputValue(), fixture.vencida);
  assert.equal(await notas(page).inputValue(), textoNotas);
  await fecha(page).fill(fixture.ayer);
  await enviar(page, vencido, 200);
  await comprobarError(page, textoNotas);
  await fecha(page).fill(nuevaFecha);
  await enviar(page, vencido, 302);
  await abrir(page, vencido);
  assert.equal(await fecha(page).inputValue(), nuevaFecha);
  assert.equal(await fecha(page).getAttribute('min'), fixture.hoy);
  console.log(`Aprobado ${ancho} px, ${js ? 'con' : 'sin'} JavaScript: mínimo chileno, POST inválido, corrección y fecha vencida conservada.`);
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CUTLESS_TEST_CHROMIUM });
  try {
    console.log('Chromium', browser.version());
    for (const [indice, casos] of fixture.edicion.entries()) {
      const ancho = indice < 2 ? 390 : 1280;
      const js = indice % 2 === 0;
      const opciones = {
        viewport: { width: ancho, height: ancho === 390 ? 844 : 920 }, colorScheme: ancho === 390 ? 'light' : 'dark',
        javaScriptEnabled: js, reducedMotion: 'reduce', timezoneId: ancho === 390 ? 'Pacific/Kiritimati' : 'UTC',
      };
      const actual = await contexto(browser, origen, opciones);
      const anterior = base && js ? await contexto(browser, base, opciones) : null;
      try {
        if (anterior) await comprobarBase(await anterior.newPage(), casos.vigente, ancho);
        await comprobarEdicion(await actual.newPage(), casos, ancho, js);
      } finally {
        await actual.close();
        if (anterior) await anterior.close();
      }
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
