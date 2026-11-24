// Ejecutar con la sesión de una instancia local y desechable de CutLess.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const origin = new URL(process.env.CUTLESS_TEST_ORIGIN || 'http://127.0.0.1:8791');
assert.equal(origin.protocol, 'http:');
assert.equal(origin.hostname, '127.0.0.1');
const fixture = JSON.parse(fs.readFileSync(process.env.CUTLESS_TEST_FIXTURE, 'utf8'));
const bootstrap = process.env.CUTLESS_TEST_BOOTSTRAP;
assert.ok(bootstrap && fs.existsSync(bootstrap), 'Indica la copia local de Bootstrap en CUTLESS_TEST_BOOTSTRAP.');
const evidence = process.env.CUTLESS_TEST_EVIDENCE;

async function contexto(browser, width, colorScheme, javaScriptEnabled = true) {
  const context = await browser.newContext({
    viewport: { width, height: 960 }, colorScheme, javaScriptEnabled,
    reducedMotion: 'reduce', serviceWorkers: 'block',
  });
  await context.addCookies([{ name: 'sessionid', value: fixture.session, url: origin.origin }]);
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin === origin.origin) return route.continue();
    if (url.pathname.endsWith('/bootstrap.min.css')) {
      return route.fulfill({ path: bootstrap, contentType: 'text/css' });
    }
    return route.abort();
  });
  return context;
}

async function abrir(page, ruta) {
  const respuesta = await page.goto(origin.origin + ruta);
  assert.equal(respuesta.status(), 200);
  assert.equal(new URL(page.url()).pathname, ruta);
}

async function captura(page, nombre) {
  if (evidence) {
    await page.evaluate(() => document.fonts.ready.then(() => {}));
    await page.screenshot({ path: path.join(evidence, nombre), fullPage: true });
  }
}

async function revisarDisposicion(page, width) {
  const posicion = await page.locator('[data-cliente-telefono]').evaluate(bloque => {
    const pais = bloque.querySelector('select').getBoundingClientRect();
    const telefono = bloque.querySelector('[type="tel"]').getBoundingClientRect();
    return { pais: pais.toJSON(), telefono: telefono.toJSON(), ancho: document.documentElement.scrollWidth };
  });
  assert.ok(posicion.ancho <= width, `Desbordamiento a ${width} px`);
  assert.ok(posicion.telefono.right <= width && posicion.pais.right <= width);
  if (width < 768) {
    assert.ok(posicion.telefono.top > posicion.pais.bottom);
  } else {
    assert.ok(Math.abs(posicion.telefono.top - posicion.pais.top) < 2);
    assert.ok(posicion.telefono.left > posicion.pais.right);
  }
}

async function guardar(page, texto) {
  const invalidos = await page.locator('form :invalid').evaluateAll(campos => campos.map(campo => campo.name));
  assert.deepEqual(invalidos, []);
  const [respuesta] = await Promise.all([
    page.waitForResponse(respuesta => respuesta.request().method() === 'POST'),
    page.getByRole('button', { name: texto, exact: true }).press('Enter'),
  ]);
  assert.equal(respuesta.status(), 302);
  await page.waitForURL(origin.origin + fixture.list, { waitUntil: 'commit' });
}

async function probar(browser) {
  for (const width of [320, 390, 768, 1440]) {
    for (const theme of ['light', 'dark']) {
      const ctx = await contexto(browser, width, theme);
      try {
        const page = await ctx.newPage();
        await abrir(page, fixture.create);
        assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
        const pais = page.getByRole('combobox', { name: 'País o territorio', exact: true });
        assert.equal(await pais.inputValue(), 'CL');
        assert.match(await pais.locator('option:checked').textContent(), /🇨🇱 Chile \(\+56\)/u);
        assert.equal(await page.getByLabel('Número de teléfono').getAttribute('inputmode'), 'tel');
        await revisarDisposicion(page, width);
        if (theme === 'light' && (width === 390 || width === 1440)) await captura(page, `crear-cliente-${width}.png`);

        await abrir(page, fixture.edit);
        assert.equal(await page.getByLabel('Número de teléfono').inputValue(), 'Contacto antiguo');
        assert.equal(await page.getByLabel('RUT', { exact: true }).inputValue(), 'FISCAL-ANTERIOR');
        await revisarDisposicion(page, width);
        if (theme === 'dark' && (width === 390 || width === 1440)) await captura(page, `editar-cliente-${width}.png`);

        if (theme === 'light' && width === 390) {
          await abrir(page, fixture.create);
          const busqueda = page.getByRole('searchbox', { name: 'Buscar país o prefijo' });
          const telefono = page.getByLabel('Número de teléfono');
          await busqueda.fill('+999');
          assert.equal(await page.locator('[data-busqueda-pais] [role="status"]').textContent(), '0 coincidencias.');
          assert.equal(await pais.inputValue(), 'CL');
          await busqueda.fill('Espana');
          assert.equal(await pais.locator('option[value="ES"]').count(), 1);
          assert.ok((await pais.locator('option').count()) <= 3);
          await busqueda.press('Enter');
          assert.equal(await pais.evaluate(elemento => elemento === document.activeElement), true);
          await page.keyboard.press('End');
          assert.equal(await pais.inputValue(), 'ES');
          await page.keyboard.press('Tab');
          assert.equal(await telefono.evaluate(elemento => elemento === document.activeElement), true);
          await busqueda.fill('+34');
          assert.equal(await pais.inputValue(), 'ES');
          await busqueda.fill('');
          assert.ok((await pais.locator('option').count()) > 200);
        }
      } finally {
        await ctx.close();
      }
    }
  }
  console.log('Crear y editar en Chromium a 320, 390, 768 y 1440 px, en claro y oscuro. Búsqueda y teclado correctos.');

  const ctx = await contexto(browser, 390, 'light', false);
  try {
    const page = await ctx.newPage();
    await abrir(page, fixture.create);
    assert.equal(await page.locator('[data-busqueda-pais]').isVisible(), false);
    const pais = page.getByLabel('País o territorio', { exact: true });
    assert.equal(await pais.inputValue(), 'CL');
    await pais.selectOption('GB');
    await page.getByLabel('Nombre o Razón Social').fill('Cliente sin JavaScript');
    const rut = page.getByLabel('RUT', { exact: true });
    const telefono = page.getByLabel('Número de teléfono');
    await rut.fill('12.345.678-9');
    await telefono.fill('llamar luego');
    const invalidos = await page.locator('form input:invalid').evaluateAll(campos => campos.map(campo => campo.name));
    assert.deepEqual(invalidos, [], 'El navegador debe permitir que Django revise estos valores.');
    const [respuesta] = await Promise.all([
      page.waitForResponse(respuesta => respuesta.request().method() === 'POST'),
      page.getByRole('button', { name: 'Crear cliente', exact: true }).click(),
    ]);
    assert.equal(respuesta.status(), 200);
    await page.locator('#id_telefono_error').waitFor();
    assert.equal(new URL(page.url()).pathname, fixture.create);
    assert.equal(await telefono.inputValue(), 'llamar luego');
    assert.equal(await rut.inputValue(), '12.345.678-9');
    assert.equal(await pais.inputValue(), 'GB');
    assert.match(await page.locator('#id_telefono_error').textContent(), /No se admiten extensiones/);
    assert.match(await page.locator('#id_rut_error').textContent(), /dígito verificador del RUT no coincide/);
    await captura(page, 'crear-cliente-errores-sin-js-390.png');

    await telefono.fill('0121 234 5678');
    await rut.fill('12.345.678-5');
    await guardar(page, 'Crear cliente');
    await page.getByRole('row').filter({ hasText: 'Cliente sin JavaScript' })
      .getByRole('cell', { name: /\+441212345678/ }).waitFor();

    await abrir(page, fixture.edit);
    await page.getByLabel('Notas').fill('Edición sintética sin JavaScript');
    await guardar(page, 'Guardar cambios');
    await abrir(page, fixture.edit);
    assert.equal(await telefono.inputValue(), 'Contacto antiguo');
    assert.equal(await rut.inputValue(), 'FISCAL-ANTERIOR');
    assert.equal(await page.getByLabel('Notas').inputValue(), 'Edición sintética sin JavaScript');
    console.log('Sin JavaScript: selector disponible, errores con datos intactos, alta válida y edición de histórico.');
  } finally {
    await ctx.close();
  }
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CUTLESS_TEST_CHROMIUM });
  try {
    await probar(browser);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
