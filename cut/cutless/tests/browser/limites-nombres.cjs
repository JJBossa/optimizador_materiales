const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');

const origen = new URL(process.env.CUTLESS_TEST_ORIGIN);
assert.equal(origen.protocol, 'http:');
assert.equal(origen.hostname, '127.0.0.1');
const fixture = JSON.parse(fs.readFileSync(process.env.CUTLESS_TEST_FIXTURE, 'utf8'));
const estilos = process.env.CUTLESS_TEST_BOOTSTRAP;
const scripts = process.env.CUTLESS_TEST_BOOTSTRAP_JS;
assert.ok(fs.existsSync(estilos) && fs.existsSync(scripts), 'Se requiere Bootstrap 5.3.0 local.');
const cdn = 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist';

async function probarMaximo(page, control, exacto) {
  assert.equal(await control.getAttribute('maxlength'), String(exacto.length));
  await control.fill('');
  await page.keyboard.insertText(exacto + 'X');
  assert.equal(await control.inputValue(), exacto);
  const caja = await control.boundingBox();
  assert.ok(caja && caja.x >= 0 && caja.x + caja.width <= page.viewportSize().width + 1);
}

async function probar(context, caso, ancho, tema) {
  const page = await context.newPage();
  await page.goto(fixture.registro);
  await probarMaximo(page, page.locator('#id_username'), 'ñ'.repeat(25) + '_@2.-');

  await context.addCookies([{ name: 'sessionid', value: fixture.sesion, url: origen.origin }]);
  await page.goto(fixture.perfil);
  assert.equal(await page.locator('html').getAttribute('data-theme'), tema);
  await page.locator('#seguridad-tab').click();
  const usuario = page.locator('#id_username');
  assert.equal(await usuario.getAttribute('maxlength'), '30');
  assert.equal(await usuario.inputValue(), fixture.usuario);
  assert.ok(await page.getByText('Puedes conservar el nombre guardado.', { exact: false }).isVisible());
  const email = `edicion${caso}@example.test`;
  await page.locator('#id_email').fill(email);
  await page.getByRole('button', { name: 'Guardar datos de cuenta' }).click();
  await page.waitForFunction(() => document.activeElement.id === 'cutlessModalDialogoOk');
  await Promise.all([
    page.waitForNavigation(),
    page.getByRole('button', { name: 'Sí, guardar' }).click(),
  ]);
  await page.locator('#seguridad-tab').click();
  assert.equal(await usuario.inputValue(), fixture.usuario);
  assert.equal(await page.locator('#id_email').inputValue(), email);

  const renombrar = fixture.renombrar[caso] + '?volver=historial';
  await page.goto(renombrar);
  const trabajo = page.locator('#nombre_optimizacion');
  assert.equal(await trabajo.inputValue(), fixture.trabajo);
  const exacto = 'ñ'.repeat(28) + '🪵';
  await probarMaximo(page, trabajo, exacto);
  await trabajo.evaluate(input => input.removeAttribute('maxlength'));
  await trabajo.fill(exacto + 'X');
  const guardar = page.getByRole('button', { name: 'Guardar nombre' });
  await Promise.all([page.waitForNavigation(), guardar.click()]);
  assert.equal(await trabajo.inputValue(), exacto + 'X');
  assert.equal(await trabajo.getAttribute('aria-invalid'), 'true');
  assert.match(await trabajo.getAttribute('aria-describedby'), /\bid_nombre_optimizacion_error\b/);
  assert.ok(await page.getByRole('alert').getByText(/Usa como máximo 30 caracteres/).isVisible());
  await trabajo.fill(exacto);
  await Promise.all([page.waitForURL(new URL(fixture.historial, origen).href), guardar.click()]);
  await page.goto(renombrar);
  assert.equal(await trabajo.inputValue(), exacto);

  await page.goto(fixture.presupuesto);
  await probarMaximo(page, page.locator('#id_nombre_cliente_nuevo'), 'É'.repeat(28) + '🪵');

  await page.goto(fixture.inicio);
  await page.locator('#add-pieza').click();
  await probarMaximo(page, page.locator('#id_form-1-nombre'), exacto);

  const urlPlantilla = fixture.plantillas[caso];
  await page.goto(urlPlantilla);
  const editor = page.locator('.template-piece-editor');
  const pieza = editor.locator('textarea').first();
  assert.equal(await pieza.inputValue(), fixture.nombre_pieza_visible);
  assert.equal(await pieza.getAttribute('maxlength'), '30');
  const descripcion = 'Descripción larga '.repeat(4) + tema;
  await page.locator('#id_descripcion').fill(descripcion);
  const [guardado] = await Promise.all([
    page.waitForResponse(response => response.request().method() === 'POST' && response.url() === new URL(urlPlantilla, origen).href),
    page.getByRole('button', { name: 'Guardar cambios' }).click(),
  ]);
  assert.equal(guardado.status(), 302);
  await page.goto(urlPlantilla);
  assert.equal(await pieza.inputValue(), fixture.nombre_pieza_visible);
  assert.equal(await page.locator('#id_descripcion').inputValue(), descripcion);
  await editor.getByRole('button', { name: 'Añadir tipo de pieza' }).click();
  await probarMaximo(page, editor.locator('textarea').last(), exacto);
  console.log(`VAL-01B · ${ancho} px · ${tema}`);
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CUTLESS_TEST_CHROMIUM });
  try {
    let caso = 0;
    for (const ancho of [320, 390, 1280]) {
      for (const tema of ['light', 'dark']) {
        const context = await browser.newContext({
          baseURL: origen.origin, viewport: { width: ancho, height: 950 },
          colorScheme: tema, reducedMotion: 'reduce',
        });
        try {
          await context.route('**/*', route => {
            const url = route.request().url();
            if (url === cdn + '/css/bootstrap.min.css') return route.fulfill({ path: estilos, contentType: 'text/css' });
            if (url === cdn + '/js/bootstrap.bundle.min.js') return route.fulfill({ path: scripts, contentType: 'application/javascript' });
            if (url.startsWith(origen.origin + '/') && !url.includes('/indicadores/')) return route.continue();
            return route.abort();
          });
          await probar(context, caso++, ancho, tema);
        } finally {
          await context.close();
        }
      }
    }
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
