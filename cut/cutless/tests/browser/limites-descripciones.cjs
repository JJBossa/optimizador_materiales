const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium, firefox, webkit } = require('playwright');

const origen = new URL(process.env.CUTLESS_TEST_ORIGIN);
assert.equal(origen.protocol, 'http:');
assert.equal(origen.hostname, '127.0.0.1');
const fixture = JSON.parse(fs.readFileSync(process.env.CUTLESS_TEST_FIXTURE, 'utf8'));
const texto = fixture.texto.replace(/\r\n?/g, '\n');
const evidencia = process.env.CUTLESS_TEST_EVIDENCE;
const motor = process.env.CUTLESS_TEST_BROWSER || 'chromium';
const entidades = ['material', 'proyecto', 'plantilla', 'cliente', 'presupuesto'];
const campoDe = entidad => ['cliente', 'presupuesto'].includes(entidad) ? 'notas' : 'descripcion';
const contadorDe = campo => campo.locator('xpath=following-sibling::small[1]');
const exacto = '🪵'.repeat(75);

async function abrir(page, ruta) {
  assert.equal((await page.goto(origen.origin + ruta)).status(), 200);
}

async function guardar(page, ruta, etiqueta, estado) {
  const [respuesta] = await Promise.all([
    page.waitForResponse(r => r.url() === origen.origin + ruta && r.request().method() === 'POST'),
    page.getByRole('button', { name: etiqueta, exact: true }).press('Enter'),
  ]);
  assert.equal(respuesta.status(), estado);
  if (estado === 302) await page.waitForURL(url => url.pathname !== ruta);
  else await page.locator('textarea[data-limite-texto][aria-invalid="true"]').waitFor();
}

async function altas(page, ancho) {
  for (const entidad of entidades) {
    await abrir(page, fixture.rutas[entidad].alta);
    const campo = page.locator(`#id_${campoDe(entidad)}`);
    assert.equal(await campo.getAttribute('maxlength'), '150');
    assert.equal(await page.locator('textarea[data-limite-texto]').count(), 1);
    assert.equal(await contadorDe(campo).textContent(), '0/150 caracteres');
    assert.ok(await campo.evaluate(e => e.getBoundingClientRect().right <= document.documentElement.clientWidth));
  }
  if (ancho === 1440 && evidencia) {
    const campo = page.locator('#id_notas');
    await campo.fill('Notas del presupuesto sintético.');
    await campo.locator('..').screenshot({ path: path.join(evidencia, 'val03-escritorio.png') });
  }
}

async function editar(page) {
  for (const entidad of entidades) {
    const ruta = fixture.rutas[entidad].edicion;
    const nombre = campoDe(entidad);
    const campo = page.locator(`#id_${nombre}`);
    await abrir(page, ruta);
    assert.equal(await campo.inputValue(), texto);
    assert.equal(await campo.getAttribute('maxlength'), null);
    assert.match(await contadorDe(campo).textContent(), new RegExp(`^${texto.length}/150 .*Supera el máximo`));
    assert.ok(await page.getByText(/Puedes conservar el texto guardado/).isVisible());

    if (entidad === 'material') {
      await page.locator('#id_precio').fill('750');
      await guardar(page, ruta, 'Guardar cambios', 302);
      await abrir(page, ruta);
      assert.equal(await campo.inputValue(), texto);
      if (evidencia) await campo.locator('..').screenshot({ path: path.join(evidencia, 'val03-movil.png') });
      await campo.fill('ñ'.repeat(151));
      await guardar(page, ruta, 'Guardar cambios', 200);
      assert.equal(await campo.inputValue(), 'ñ'.repeat(151));
      assert.match(await campo.getAttribute('aria-describedby'), /id_descripcion_error/);
      assert.ok(await page.locator('#id_descripcion_error').isVisible());
    }

    await campo.fill(exacto);
    assert.equal(await contadorDe(campo).textContent(), '150/150 caracteres');
    await guardar(page, ruta, 'Guardar cambios', 302);
    await abrir(page, ruta);
    assert.equal(await campo.inputValue(), exacto);
    assert.equal(await campo.getAttribute('maxlength'), '150');
  }
}

async function probarAltaManipulada(page) {
  const ruta = fixture.rutas.cliente.alta;
  await abrir(page, ruta);
  const campo = page.locator('#id_notas');
  await page.locator('#id_nombre').fill('Alta sintética VAL-03');
  if (motor === 'chromium') {
    await page.context().grantPermissions(['clipboard-read', 'clipboard-write']);
    await page.evaluate(texto => navigator.clipboard.writeText(texto), exacto + 'a');
    await campo.press('Control+v');
    assert.equal(await campo.inputValue(), exacto);
    await campo.press('End');
    await campo.press('b');
    assert.equal(await campo.inputValue(), exacto);
    assert.equal(await contadorDe(campo).textContent(), '150/150 caracteres');
  }
  await campo.evaluate(e => e.removeAttribute('maxlength'));
  await campo.fill(exacto + 'b');
  await guardar(page, ruta, 'Crear cliente', 200);
  assert.equal(await campo.inputValue(), exacto + 'b');
  assert.equal(await page.locator('#id_nombre').inputValue(), 'Alta sintética VAL-03');
  assert.ok(await page.locator('#id_notas_error').isVisible());
  await campo.fill(exacto);
  await guardar(page, ruta, 'Crear cliente', 302);
}

async function sinJS(page) {
  const ruta = fixture.rutas.sin_js;
  await abrir(page, ruta);
  const campo = page.locator('#id_descripcion');
  assert.equal(await campo.inputValue(), texto);
  assert.equal(await campo.getAttribute('maxlength'), null);
  assert.equal(await page.getByText(/Supera el máximo/).count(), 0);
  await page.locator('#id_precio').fill('750');
  await guardar(page, ruta, 'Guardar cambios', 302);
  await abrir(page, ruta);
  assert.equal(await campo.inputValue(), texto);
  await campo.fill('ñ'.repeat(151));
  await guardar(page, ruta, 'Guardar cambios', 200);
  await campo.fill('ñ'.repeat(150));
  await guardar(page, ruta, 'Guardar cambios', 302);
  await abrir(page, ruta);
  assert.equal(await campo.inputValue(), 'ñ'.repeat(150));
}

async function main() {
  const browser = await { chromium, firefox, webkit }[motor].launch(motor === 'chromium' ? {
    executablePath: process.env.CUTLESS_TEST_CHROMIUM || undefined,
  } : {});
  try {
    for (const [ancho, tema, js] of [[320, 'dark', false], [390, 'light', true],
      [768, 'light', true], [1440, 'dark', true]]) {
      const contexto = await browser.newContext({ viewport: { width: ancho, height: 900 }, colorScheme: tema,
        javaScriptEnabled: js, reducedMotion: 'reduce', serviceWorkers: 'block' });
      try {
        await contexto.addCookies([{ name: 'sessionid', value: fixture.session, url: origen.origin }]);
        await contexto.route('**/*', ruta => {
          const url = new URL(ruta.request().url());
          if (url.origin === origen.origin) return ruta.continue();
          if (url.pathname.endsWith('/bootstrap.min.css')) {
            return ruta.fulfill({ path: process.env.CUTLESS_TEST_BOOTSTRAP, contentType: 'text/css' });
          }
          return ruta.abort();
        });
        const page = await contexto.newPage();
        if (js) {
          await altas(page, ancho);
          assert.equal(await page.locator('html').getAttribute('data-theme'), tema);
          if (ancho === 390) {
            await editar(page);
            await probarAltaManipulada(page);
          }
        } else await sinJS(page);
        console.log(`${motor} ${browser.version()} · ${ancho}px · ${tema} · JS ${js ? 'activo' : 'inactivo'} · aprobado`);
      } finally {
        await contexto.close();
      }
    }
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
