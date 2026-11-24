// Ejecutar con la sesión de una instancia local y desechable de CutLess.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium, firefox, webkit } = require('playwright');
const motor = process.env.CUTLESS_TEST_BROWSER || 'chromium';

const origin = new URL(process.env.CUTLESS_TEST_ORIGIN || 'http://127.0.0.1:8791');
assert.equal(origin.protocol, 'http:');
assert.equal(origin.hostname, '127.0.0.1');
const fixture = JSON.parse(fs.readFileSync(process.env.CUTLESS_TEST_FIXTURE, 'utf8'));
const bootstrap = process.env.CUTLESS_TEST_BOOTSTRAP;
assert.ok(bootstrap && fs.existsSync(bootstrap), 'Indica la copia local de Bootstrap en CUTLESS_TEST_BOOTSTRAP.');
const evidence = process.env.CUTLESS_TEST_EVIDENCE;

async function contexto(browser, width, colorScheme, javaScriptEnabled = true) {
  const context = await browser.newContext({
    viewport: { width, height: 960 }, colorScheme, javaScriptEnabled, hasTouch: width === 390,
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
    const pais = bloque.querySelector('[role=combobox]').getBoundingClientRect();
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
        const pais = page.getByRole('combobox', { name: /^País o territorio:?$/ });
        assert.match(await pais.inputValue(), /🇨🇱 Chile \(\+56\)/u);
        assert.equal(await page.locator('#id_telefono_pais').isHidden(), true);
        assert.equal(await page.getByLabel('Número de teléfono').getAttribute('inputmode'), 'tel');
        await revisarDisposicion(page, width);
        const selectorPostal = page.getByRole('combobox', { name: /País o territorio de la dirección/ });
        await selectorPostal.click();
        assert.equal(await selectorPostal.getAttribute('aria-expanded'), 'true');
        assert.ok(await page.getByRole('listbox', { name: /País o territorio de la dirección/ }).evaluate(lista =>
          lista.scrollHeight > lista.clientHeight && lista.scrollWidth <= lista.clientWidth));
        if (theme === 'dark' && width === 1440) {
          await selectorPostal.fill('antartida');
          await captura(page, 'ux06-postal-escritorio.png');
        }
        await selectorPostal.press('Escape');
        if (theme === 'light' && (width === 390 || width === 1440)) await captura(page, `crear-cliente-${width}.png`);

        await abrir(page, fixture.edit);
        assert.equal(await page.getByLabel('Número de teléfono').inputValue(), 'Contacto antiguo');
        assert.equal(await page.getByLabel('RUT', { exact: true }).inputValue(), 'FISCAL-ANTERIOR');
        await revisarDisposicion(page, width);
        if (theme === 'dark' && (width === 390 || width === 1440)) await captura(page, `editar-cliente-${width}.png`);

        if (theme === 'light' && width === 390) {
          await abrir(page, fixture.create);
          const nativo = page.locator('#id_telefono_pais');
          const lista = page.getByRole('listbox', { name: /^País o territorio:?$/ });
          const telefono = page.getByLabel('Número de teléfono');
          const postal = page.getByRole('combobox', { name: 'País o territorio de la dirección' });
          await nativo.evaluate(select => {
            select.parentElement.dataset.cambios = '0';
            select.parentElement.addEventListener('change', () => select.parentElement.dataset.cambios++);
          });
          const cambios = () => nativo.evaluate(select => select.parentElement.dataset.cambios);
          const cantidad = await nativo.locator('option').count();
          await pais.click();
          assert.equal(await lista.getByRole('option').count(), cantidad);
          assert.ok(await lista.evaluate(e => e.scrollHeight > e.clientHeight));
          await pais.press('ArrowUp');
          assert.ok(await lista.evaluate(e => e.scrollTop > 0));
          await pais.fill('chi');
          await captura(page, 'ux06-telefono-movil.png');
          await lista.getByRole('option', { name: /Chile/ }).click();
          assert.equal(await cambios(), '0');
          await pais.fill('+56');
          assert.equal(await lista.getByRole('option').count(), 1);
          await pais.press('ArrowDown');
          await pais.press('Enter');
          assert.equal(await nativo.inputValue(), 'CL');
          await pais.fill('+999');
          assert.equal(await page.getByText('No hay coincidencias.').isVisible(), true);
          await pais.press('Escape');
          assert.equal(await pais.getAttribute('aria-expanded'), 'false');
          assert.match(await pais.inputValue(), /Chile/);
          await pais.fill('Espana');
          await pais.press('ArrowDown');
          const activa = await pais.getAttribute('aria-activedescendant');
          assert.equal(await page.locator(`#${activa}`).getAttribute('aria-selected'), 'true');
          await pais.press('Enter');
          assert.equal(await nativo.inputValue(), 'ES');
          assert.equal(await cambios(), '1');
          await pais.fill('+34');
          assert.equal(await lista.getByRole('option').count(), 1);
          await pais.fill('+1');
          assert.ok(await lista.getByRole('option').count() > 1);
          assert.equal(await nativo.inputValue(), 'ES');
          await lista.getByRole('option', { name: /Canadá/ }).tap();
          assert.equal(await nativo.inputValue(), 'CA');
          assert.equal(await cambios(), '2');
          await pais.fill('GB');
          await pais.press('Tab');
          assert.equal(await telefono.evaluate(elemento => elemento === document.activeElement), true);
          assert.match(await pais.inputValue(), /Canadá/);
          assert.equal(await cambios(), '2');
          assert.equal(await postal.inputValue(), '');
          assert.equal(await nativo.locator('option').count(), cantidad);
          assert.equal(await page.locator('input[name=telefono_pais]').count(), 0);
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
    assert.equal(await page.locator('input[role=combobox]').count(), 0);
    assert.equal(await page.locator('#id_direccion_pais').isVisible(), true);
    const pais = page.getByLabel(/^País o territorio:?$/);
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
      page.getByRole('button', { name: 'Crear cliente', exact: true }).press('Enter'),
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

async function probarEtiquetasEHidratacion(browser) {
  const page = await browser.newPage();
  try {
    await page.setContent(`
      <div data-selector-pais="postal"><select id="incompleto"><option>Sin etiqueta</option></select></div>
      <div data-selector-pais="postal"><label for="postal">Dirección</label>
        <select id="postal" name="direccion_pais"><option value="">Selecciona un país o territorio</option></select>
      </div>
    `);
    const etiqueta = '<img src=x> & País (guardado anteriormente)';
    await page.locator('#postal').evaluate((selector, texto) => {
      selector.add(new Option(texto, 'ZZ', true, true));
      selector.dataset.cambios = '0';
      selector.addEventListener('change', () => selector.dataset.cambios++);
    }, etiqueta);
    const script = path.join(__dirname, '../../static/cutless/js/selector-pais.js');
    await page.addScriptTag({ path: script });
    await page.addScriptTag({ path: script });
    assert.equal(await page.locator('#incompleto').isVisible(), true);
    assert.equal(await page.locator('input[role=combobox]').count(), 1);
    const entrada = page.getByRole('combobox', { name: 'Dirección' });
    assert.equal(await entrada.inputValue(), etiqueta);
    await entrada.click();
    assert.equal(await page.getByRole('option', { name: etiqueta }).textContent(), etiqueta);
    assert.equal(await page.locator('img').count(), 0);
    assert.equal(await page.locator('#postal').getAttribute('data-cambios'), '0');
    await page.getByRole('option', { name: 'Selecciona un país o territorio' }).click();
    assert.equal(await entrada.inputValue(), '');
    assert.equal(await page.locator('#postal').inputValue(), '');
    assert.equal(await page.locator('#postal').getAttribute('data-cambios'), '1');
  } finally {
    await page.close();
  }
}

(async () => {
  const browser = await { chromium, firefox, webkit }[motor].launch({
    executablePath: motor === 'chromium' ? process.env.CUTLESS_TEST_CHROMIUM : undefined,
  });
  try {
    await probarEtiquetasEHidratacion(browser);
    await probar(browser);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
