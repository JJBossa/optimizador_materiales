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
  if (estado === 302) await page.waitForURL(origen.origin + fixture.lista);
}

async function abrirDireccion(page) {
  const bloque = page.locator('[data-cliente-direccion]');
  const resumen = bloque.locator('summary');
  await resumen.focus();
  assert.equal(await resumen.evaluate(e => e === document.activeElement), true);
  await page.keyboard.press('Enter');
  assert.equal(await bloque.evaluate(e => e.open), true);
  await page.keyboard.press('Tab');
  const esperado = await bloque.locator('select').first().getAttribute('id');
  assert.equal(await page.evaluate(() => document.activeElement.id), esperado);
  assert.equal(await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth), 0);
  return bloque;
}

async function probar(context, ancho, modo) {
  const page = await context.newPage();
  const escenario = `${modo}-${ancho}`;
  await abrir(page, fixture.crear);
  const bloque = await abrirDireccion(page);
  await page.getByLabel('Nombre o Razón Social').fill(`CLI-01 Crear ${escenario}`);
  const numero = bloque.getByRole('textbox', { name: /^Número:?$/ });
  await numero.fill('S/N');
  await guardar(page, fixture.crear, 'Crear cliente', 200);
  assert.equal(await bloque.evaluate(e => e.open), true);
  await page.getByText('Indica calle, región, comuna o localidad para guardar la dirección.').waitFor();
  assert.equal(await numero.inputValue(), 'S/N');
  assert.equal(await numero.getAttribute('aria-describedby'), 'id_direccion_numero_helptext');

  const calle = bloque.getByLabel('Calle, avenida o camino');
  await calle.fill('Avenida Sintética  Árvore');
  const dimensiones = await calle.evaluate(e => {
    const caja = e.getBoundingClientRect();
    return caja.left >= 0 && caja.right <= document.documentElement.clientWidth;
  });
  assert.equal(dimensiones, true);
  await bloque.getByLabel('País o territorio de la dirección').selectOption('PT');
  await bloque.getByLabel('Ciudad o localidad').fill('Localidad ficticia');
  await bloque.getByLabel('Referencia adicional (solo en la ficha)').fill('Referencia privada de prueba');
  if (evidencia && modo === 'js' && (ancho === 390 || ancho === 1280)) {
    await bloque.scrollIntoViewIfNeeded();
    await bloque.screenshot({ path: path.join(evidencia, `alta-${ancho}.png`) });
  }
  await guardar(page, fixture.crear, 'Crear cliente', 302);
  await page.getByText(`CLI-01 Crear ${escenario}`, { exact: true }).waitFor();

  const ruta = fixture.ediciones[escenario];
  await abrir(page, ruta.editar);
  await page.getByLabel('Correo Electrónico').fill(`${escenario}@example.test`);
  const texto = page.getByLabel('Dirección legada editable');
  assert.equal(await texto.inputValue(), fixture.direccion.replaceAll('\r\n', '\n'));
  await guardar(page, ruta.editar, 'Guardar cambios', 302);

  await abrir(page, ruta.editar);
  const editar = await abrirDireccion(page);
  await editar.getByLabel('Qué hacer con la dirección').selectOption('estructurada');
  await editar.getByLabel('Calle, avenida o camino').fill('Pasaje Sintético');
  await editar.getByRole('textbox', { name: /^Número:?$/ }).fill('12-B');
  await editar.getByLabel('Referencia adicional (solo en la ficha)').fill('Referencia de edición');
  await guardar(page, ruta.editar, 'Guardar cambios', 302);

  await abrir(page, ruta.historial);
  await page.getByText('Pasaje Sintético 12-B', { exact: true }).waitFor();
  await page.getByText('Referencia de edición', { exact: true }).waitFor();
  await abrir(page, ruta.editar);
  const original = page.getByText('Ver dirección histórica original');
  await original.focus();
  await page.keyboard.press('Enter');
  const literal = await original.locator('xpath=following-sibling::p').textContent();
  assert.equal(literal, fixture.direccion.replaceAll('\r\n', '\n'));
  if (evidencia && modo === 'js' && (ancho === 390 || ancho === 1280)) {
    await original.locator('xpath=..').screenshot({ path: path.join(evidencia, `legado-${ancho}.png`) });
  }
  console.log(`Aprobado ${escenario}: alta, error retenido, teclado, correo, estructuración e historial.`);
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
