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

async function abrir(page, ruta) {
  assert.equal((await page.goto(origen.origin + ruta, { waitUntil: 'domcontentloaded' })).status(), 200);
}

async function guardar(page, ruta, nombreBoton, estado) {
  const [respuesta] = await Promise.all([
    page.waitForResponse(r => r.url() === origen.origin + ruta && r.request().method() === 'POST'),
    page.getByRole('button', { name: nombreBoton, exact: true }).press('Enter'),
  ]);
  assert.equal(respuesta.status(), estado);
  if (estado === 302) await page.waitForURL(url => url.origin === origen.origin && url.pathname === fixture.lista);
}

async function ubicacionChile(page, ruta, js) {
  const pais = page.locator('#id_direccion_pais');
  const region = page.locator('#id_direccion_region');
  const comuna = page.locator('#id_direccion_comuna');
  const actualizar = 'Actualizar opciones de ubicación';

  await pais.selectOption('PT');
  if (!js) await guardar(page, ruta, actualizar, 200);
  assert.equal(await region.evaluate(e => e.tagName), 'INPUT');
  await region.fill('Distrito sintético');
  await pais.selectOption('CL');
  if (!js) await guardar(page, ruta, actualizar, 200);
  assert.equal(await region.evaluate(e => e.tagName), 'SELECT');
  assert.equal(await region.inputValue(), '');
  await region.selectOption('13');
  if (!js) await guardar(page, ruta, actualizar, 200);
  assert.equal(await comuna.locator('option[value="08109"]').count(), 0);

  await region.selectOption('08');
  if (!js) await guardar(page, ruta, actualizar, 200);
  assert.equal(await comuna.locator('option[value="13101"]').count(), 0);
  assert.equal(await comuna.locator('option[value="08109"]').textContent(), 'Santa Juana');
  await comuna.selectOption('08109');
}

async function probar(context, ancho, modo) {
  const page = await context.newPage();
  const js = modo === 'js';
  const escenario = `${modo}-${ancho}`;
  await abrir(page, fixture.crear);
  const bloque = page.locator('[data-cliente-direccion]');
  await page.getByLabel('Nombre o Razón Social').fill(`CLI-02 Crear ${escenario}`);
  await ubicacionChile(page, fixture.crear, js);

  const numero = bloque.getByRole('textbox', { name: /^Número:?$/ });
  const calle = bloque.getByLabel('Calle, avenida o camino');
  await numero.fill('S/N');
  await calle.fill('Pasaje Sintético');
  await bloque.getByLabel('Código postal').fill('0001250');
  await bloque.getByLabel('Departamento, oficina o unidad').fill('Depto. 201');
  await bloque.getByLabel('Referencia adicional').fill('Referencia sintética');
  assert.equal(await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth), 0);
  if (evidencia && js && (ancho === 390 || ancho === 1280)) {
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(evidencia, `alta-${ancho}.png`), fullPage: true });
  }

  await calle.fill('');
  await guardar(page, fixture.crear, 'Crear cliente', 200);
  await page.getByText('Indica la calle, avenida o camino.').waitFor();
  assert.equal(await numero.inputValue(), 'S/N');
  assert.equal(await page.locator('#id_direccion_comuna').inputValue(), '08109');
  assert.equal(await bloque.locator('#id_direccion_calle').getAttribute('aria-invalid'), 'true');
  await calle.fill('Pasaje Sintético');
  await guardar(page, fixture.crear, 'Crear cliente', 302);
  await page.getByText(`CLI-02 Crear ${escenario}`, { exact: true }).waitFor();

  const ruta = fixture.ediciones[escenario];
  await abrir(page, ruta.editar);
  const aviso = page.locator('[data-aviso-direccion]');
  const continuar = aviso.getByRole('link', { name: 'Continuar al formulario' });
  const dialogo = page.getByRole('dialog');
  if (js) {
    await dialogo.waitFor();
    assert.equal(await continuar.evaluate(e => e === document.activeElement), true);
    await page.keyboard.press('Tab');
    assert.equal(await aviso.getByRole('link', { name: 'Volver al listado' }).evaluate(e => e === document.activeElement), true);
    await page.keyboard.press('Escape');
    await dialogo.waitFor({ state: 'detached' });
    assert.equal(await page.evaluate(() => document.activeElement.id), 'id_direccion_pais');
    const revisar = aviso.getByRole('button', { name: 'Revisar aviso' });
    await revisar.press('Enter');
    await dialogo.waitFor();
    await page.keyboard.press('Escape');
    await dialogo.waitFor({ state: 'detached' });
    assert.equal(await revisar.evaluate(e => e === document.activeElement), true);
    await abrir(page, ruta.editar);
    if (evidencia && (ancho === 390 || ancho === 1280)) {
      await dialogo.screenshot({ path: path.join(evidencia, `aviso-${ancho}.png`) });
    }
  } else {
    assert.equal(await dialogo.count(), 0);
    assert.equal(await aviso.isVisible(), true);
  }
  await aviso.getByRole('link', { name: 'Volver al listado' }).click();
  await page.waitForURL(url => url.origin === origen.origin && url.pathname === fixture.lista);
  await abrir(page, ruta.editar);
  await continuar.press('Enter');
  if (js) {
    await dialogo.waitFor({ state: 'detached' });
    assert.equal(await page.evaluate(() => document.activeElement.id), 'id_direccion_pais');
  }

  await page.getByLabel('Correo Electrónico').fill(`${escenario}@example.test`);
  await guardar(page, ruta.editar, 'Guardar cambios', 200);
  assert.equal(await dialogo.count(), 0);
  await aviso.waitFor();
  assert.equal(await page.getByLabel('Correo Electrónico').inputValue(), `${escenario}@example.test`);
  await ubicacionChile(page, ruta.editar, js);
  await bloque.getByLabel('Calle, avenida o camino').fill('Calle sintética');
  await numero.fill('12-B');
  await guardar(page, ruta.editar, 'Guardar cambios', 302);

  await abrir(page, ruta.historial);
  await page.getByText(/Calle sintética 12-B.*Santa Juana/s).waitFor();
  await abrir(page, ruta.editar);
  assert.equal(await aviso.count(), 0);
  assert.equal(await page.locator('#id_direccion_pais').inputValue(), 'CL');
  assert.equal(await page.locator('#id_direccion_region').inputValue(), '08');
  assert.equal(await page.locator('#id_direccion_comuna').inputValue(), '08109');
  console.log(`Aprobado ${escenario}: CUT, cambio de país y región, aviso, corrección y persistencia.`);
}

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CUTLESS_TEST_CHROMIUM || undefined,
    args: ['--no-sandbox'],
  });
  try {
    console.log(`Chromium ${browser.version()}`);
    for (const ancho of [320, 390, 768, 1280]) {
      for (const js of [true, false]) {
        const context = await browser.newContext({
          locale: 'es-CL', viewport: { width: ancho, height: 920 }, javaScriptEnabled: js,
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
          await probar(context, ancho, js ? 'js' : 'html');
        } finally {
          await context.close();
        }
      }
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
