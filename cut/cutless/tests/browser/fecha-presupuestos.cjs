const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const origen = new URL(process.env.CUTLESS_TEST_ORIGIN);
assert.equal(origen.protocol, 'http:');
assert.equal(origen.hostname, '127.0.0.1');
const fixture = JSON.parse(fs.readFileSync(process.env.CUTLESS_TEST_FIXTURE, 'utf8'));
const cdn = 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist';
const estilos = process.env.CUTLESS_TEST_BOOTSTRAP;
assert.ok(fs.existsSync(estilos), 'Se requiere la copia local de Bootstrap 5.3.0.');
const scripts = process.env.CUTLESS_TEST_BOOTSTRAP_JS;
const evidencia = process.env.CUTLESS_TEST_EVIDENCE;
const errorFecha = 'La fecha de validez no puede ser anterior a hoy. Selecciona la fecha actual o una posterior.';

async function probar(page, ancho, js) {
  const alta = origen.origin + fixture.crear;
  assert.equal((await page.goto(alta, { waitUntil: 'domcontentloaded' })).status(), 200);
  const fecha = page.getByLabel('Válido Hasta');
  const guardar = page.getByRole('button', { name: 'Guardar borrador', exact: true });
  const valores = {
    cliente: String(fixture.cliente), proyecto: String(fixture.proyecto),
    precio_tablero: '150.50', mano_obra: '25.25', notas: 'Notas sintéticas PRE-01',
  };
  const plan = page.locator(`#opt_${fixture.plan}`);
  assert.equal(await fecha.getAttribute('type'), 'date');
  assert.equal(await fecha.getAttribute('min'), fixture.hoy);
  assert.equal(await fecha.inputValue(), fixture.hoy);
  assert.equal(await fecha.evaluate(e => e.required), true);
  for (const campo of ['cliente', 'proyecto']) {
    await page.locator(`#id_${campo}`).selectOption(valores[campo]);
  }
  for (const campo of ['precio_tablero', 'mano_obra', 'notas']) {
    await page.locator(`#id_${campo}`).fill(valores[campo]);
  }
  await plan.check();
  await fecha.fill(fixture.ayer);
  assert.equal(await fecha.evaluate(e => e.validity.rangeUnderflow), true);

  // Quita la restricción HTML para probar la respuesta real del servidor.
  await fecha.evaluate(e => e.removeAttribute('min'));
  const [respuesta] = await Promise.all([
    page.waitForResponse(r => r.url() === alta && r.request().method() === 'POST'),
    guardar.click(),
  ]);
  assert.equal(respuesta.status(), 200);
  const error = page.locator('#id_fecha_validez_error');
  await error.waitFor();
  assert.equal((await error.textContent()).trim(), errorFecha);
  assert.equal(await fecha.getAttribute('aria-invalid'), 'true');
  assert.match(await fecha.getAttribute('aria-describedby'), /\bid_fecha_validez_error\b/);
  assert.equal(await fecha.inputValue(), fixture.ayer);
  assert.equal(await fecha.getAttribute('min'), fixture.hoy);
  for (const [campo, valor] of Object.entries(valores)) {
    assert.equal(await page.locator(`#id_${campo}`).inputValue(), valor, campo);
  }
  assert.equal(await plan.isChecked(), true);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth), 0);
  if (evidencia && js) {
    await fecha.evaluate(e => e.scrollIntoView({ block: 'center', behavior: 'instant' }));
    assert.ok(await error.evaluate(e => e.getBoundingClientRect().bottom <= visualViewport.height));
    await page.screenshot({ path: path.join(evidencia, `pre-despues-${ancho}.png`) });
  }

  await fecha.fill(fixture.hoy);
  const [valida] = await Promise.all([
    page.waitForResponse(r => r.url() === alta && r.request().method() === 'POST'),
    guardar.click(),
  ]);
  assert.equal(valida.status(), 302);
  await page.waitForURL(new URL(valida.headers().location, origen.origin).href);
  console.log(`Aprobado ${ancho} px ${js ? 'con JS' : 'sin JS'}: mínimo, POST manipulado, datos conservados y alta corregida.`);
}

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CUTLESS_TEST_CHROMIUM || undefined,
    args: ['--no-sandbox'],
  });
  try {
    console.log(`Chromium ${browser.version()}`);
    for (const [ancho, alto] of [[390, 844], [1280, 920]]) {
      for (const js of [true, false]) {
        const context = await browser.newContext({
          locale: 'es-CL', viewport: { width: ancho, height: alto }, javaScriptEnabled: js,
          colorScheme: ancho === 1280 ? 'dark' : 'light', reducedMotion: 'reduce', serviceWorkers: 'block',
        });
        try {
          await context.addCookies([{ name: 'sessionid', value: fixture.session, url: origen.origin }]);
          await context.route('**/*', ruta => {
            const url = ruta.request().url();
            if (url.startsWith(origen.origin + '/')) return ruta.continue();
            if (url === cdn + '/css/bootstrap.min.css') return ruta.fulfill({ path: estilos, contentType: 'text/css' });
            if (scripts && url === cdn + '/js/bootstrap.bundle.min.js') {
              return ruta.fulfill({ path: scripts, contentType: 'application/javascript' });
            }
            return ruta.abort();
          });
          await probar(await context.newPage(), ancho, js);
        } finally {
          await context.close();
        }
      }
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
