const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');

const origin = new URL(process.env.CUTLESS_TEST_ORIGIN || 'http://127.0.0.1:8797');
assert.equal(origin.protocol, 'http:');
assert.equal(origin.hostname, '127.0.0.1');
const { session, rutas, plan } = JSON.parse(fs.readFileSync(process.env.CUTLESS_TEST_FIXTURE, 'utf8'));
const bootstrap = process.env.CUTLESS_TEST_BOOTSTRAP;

async function abrir(page, ruta) {
  const respuesta = await page.goto(origin.origin + ruta, { waitUntil: 'domcontentloaded' });
  assert.equal(respuesta.status(), 200);
}

async function enviarMaterial(page, estado) {
  const [respuesta] = await Promise.all([
    page.waitForResponse(res => res.request().method() === 'POST'),
    page.locator('form:has([name="precio"]) button[type="submit"]').press('Enter'),
  ]);
  assert.equal(respuesta.status(), estado);
  if (estado === 302) await page.waitForURL(origin.origin + rutas.lista_materiales);
}

async function probarMateriales(page, javaScriptEnabled) {
  const titulo = `NUM-01 ${javaScriptEnabled ? 'con JS' : 'sin JS'}`;
  await abrir(page, rutas.crear_material);
  const nombre = page.locator('[name="nombre"]');
  const ancho = page.locator('[name="ancho"]');
  const alto = page.locator('[name="alto"]');
  const precio = page.locator('[name="precio"]');
  await nombre.fill(titulo);
  await ancho.fill('301');
  await alto.fill('244.25');
  await precio.fill('1_2');
  assert.equal(await precio.inputValue(), '1_2');
  assert.equal(await precio.evaluate(input => input.validity.patternMismatch), true);
  for (const agrupado of ['1.000', '1,000']) {
    await ancho.fill(agrupado);
    assert.equal(await ancho.inputValue(), agrupado);
    assert.equal(await ancho.evaluate(input => input.validity.patternMismatch), true);
  }
  await ancho.fill('301');
  await precio.fill('');
  await precio.pressSequentially('12,5');
  assert.equal(await precio.inputValue(), '12,5');
  assert.equal(await precio.evaluate(input => input.validity.valid), true);
  await enviarMaterial(page, 200);
  await page.getByText('Cada lado debe medir entre 10 y 300 cm', { exact: false }).first().waitFor();
  assert.equal(await nombre.inputValue(), titulo);
  assert.equal(await alto.inputValue(), '244.25');
  assert.equal(await precio.inputValue(), '12,5');
  await ancho.fill('122,1250');
  await enviarMaterial(page, 302);

  const editar = page.getByRole('row').filter({ hasText: titulo }).getByRole('link', { name: 'Editar' });
  const rutaEdicion = await editar.getAttribute('href');
  await abrir(page, rutaEdicion);
  assert.equal(await precio.inputValue(), '12.50');
  assert.equal(await ancho.inputValue(), '122.1250');
  await precio.fill('0,345');
  await enviarMaterial(page, 200);
  await page.locator('#id_precio_error').waitFor();
  assert.equal(await precio.inputValue(), '0,345');
  assert.equal(await ancho.inputValue(), '122.1250');
  assert.equal(await nombre.inputValue(), titulo);
  await precio.fill('');
  await precio.pressSequentially('0,50');
  assert.equal(await precio.inputValue(), '0,50');
  await enviarMaterial(page, 302);
  await abrir(page, rutaEdicion);
  assert.equal(await precio.inputValue(), '0.50');
}

async function probarFechaYPreseleccion(page) {
  await abrir(page, rutas.historial);
  const hasta = page.getByLabel('Hasta', { exact: true });
  await hasta.fill('9999-12-31');
  const [respuesta] = await Promise.all([
    page.waitForResponse(res => res.request().isNavigationRequest() && new URL(res.url()).searchParams.has('fecha_hasta')),
    page.getByRole('button', { name: 'Buscar', exact: true }).press('Enter'),
  ]);
  assert.equal(respuesta.status(), 200);
  await page.getByText('Hasta: 9999-12-31', { exact: true }).waitFor();
  await abrir(page, rutas.crear_presupuesto + '?optimizacion=' + plan);
  assert.equal(await page.locator(`[name="optimizaciones"][value="${plan}"]`).isChecked(), true);
  await abrir(page, rutas.crear_plantilla + '?optimizacion=' + plan);
  assert.match(await page.locator('#id_piezas').inputValue(), /Puerta,20(?:\.0)?,30(?:\.0)?,1/);
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CUTLESS_TEST_CHROMIUM, args: ['--lang=es-CL'] });
  try {
    for (const javaScriptEnabled of [true, false]) {
      const context = await browser.newContext({ locale: 'es-CL', javaScriptEnabled, serviceWorkers: 'block' });
      try {
        await context.addCookies([{ name: 'sessionid', value: session, url: origin.origin }]);
        await context.route('**/*', route => {
          const url = new URL(route.request().url());
          if (url.origin === origin.origin) return route.continue();
          if (bootstrap && url.pathname.endsWith('/bootstrap.min.css')) {
            return route.fulfill({ path: bootstrap, contentType: 'text/css' });
          }
          return route.abort();
        });
        const page = await context.newPage();
        await probarMateriales(page, javaScriptEnabled);
        await probarFechaYPreseleccion(page);
        console.log(`Chromium ${javaScriptEnabled ? 'con JS' : 'sin JS'}: alta y edición exactas, errores con datos conservados, fecha máxima y preselecciones propias.`);
      } finally {
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
