const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium, firefox, webkit } = require('playwright');

const origen = new URL(process.env.CUTLESS_TEST_ORIGIN);
assert.equal(origen.protocol, 'http:');
assert.equal(origen.hostname, '127.0.0.1');
const fixture = JSON.parse(fs.readFileSync(process.env.CUTLESS_TEST_FIXTURE, 'utf8'));
const motor = process.env.CUTLESS_TEST_BROWSER || 'chromium';
const evidencia = process.env.CUTLESS_TEST_EVIDENCE;

async function abrir(page, ruta) {
  assert.equal((await page.goto(origen.origin + ruta)).status(), 200);
}

const estadoVisible = (page, estado) => page.locator(`[data-presupuesto-estado="${estado}"]`);

async function guardar(page, etiqueta, codigo = 302) {
  const url = page.url();
  const [respuesta] = await Promise.all([
    page.waitForResponse(r => r.url() === url && r.request().method() === 'POST'),
    page.getByRole('button', { name: etiqueta, exact: true }).press('Enter'),
  ]);
  assert.equal(respuesta.status(), codigo);
  if (codigo === 302) await page.waitForURL(new URL(respuesta.headers().location, url).href);
}

async function prepararAlta(page, notas) {
  await abrir(page, fixture.alta);
  assert.equal(await page.locator('select[name="estado"]').count(), 0);
  await page.locator('#id_cliente').selectOption(String(fixture.cliente));
  await page.locator('#id_precio_tablero').fill('1000');
  await page.locator('#id_mano_obra').fill('200');
  await page.locator('#id_notas').fill(notas);
  const plan = page.locator(`#opt_${fixture.plan}`);
  await plan.press('Space');
  assert.ok(await plan.isChecked());
}

async function confirmar(page, codigo = 302) {
  const resumen = page.locator('summary').filter({ hasText: /^Emitir presupuesto$/ });
  if (!await resumen.evaluate(e => e.parentElement.open)) await resumen.press('Enter');
  assert.ok(await page.getByText(/Al emitir, quedarán cerrados los precios/).isVisible());
  await guardar(page, 'Confirmar emisión', codigo);
}

async function descargar(page, estado) {
  const enlace = page.getByRole('link', { name: 'Generar PDF' });
  const pdf = await page.request.get(new URL(await enlace.getAttribute('href'), page.url()).href);
  assert.equal(pdf.headers()['content-type'], 'application/pdf');
  assert.ok((await pdf.body()).subarray(0, 4).equals(Buffer.from('%PDF')));
  await page.reload();
  assert.ok(await estadoVisible(page, estado).isVisible());
}

async function registrar(page, accion, esperado) {
  await page.getByRole('link', { name: 'Registrar estado' }).press('Enter');
  await page.getByRole('heading', { name: /^Estado de / }).waitFor();
  await guardar(page, accion);
  assert.ok(await estadoVisible(page, esperado).isVisible());
}

async function probar(page, ancho, js) {
  const borrador = fixture.borradores[ancho];
  const notas = `Cambios sintéticos a ${ancho} px`;
  await prepararAlta(page, notas);
  await guardar(page, 'Guardar borrador');
  assert.ok(await estadoVisible(page, 'borrador').isVisible());
  await descargar(page, 'borrador');

  await prepararAlta(page, 'Emisión directa sintética');
  await confirmar(page);
  assert.ok(await estadoVisible(page, 'emitido').isVisible());
  assert.equal(await page.getByRole('link', { name: 'Editar presupuesto' }).count(), 0);
  assert.equal(await page.getByRole('link', { name: 'Agregar optimizaciones' }).count(), 0);
  await descargar(page, 'emitido');

  if (ancho === 1440 && evidencia) {
    await page.screenshot({ path: path.join(evidencia, 'pre03-emitido-escritorio.png'), fullPage: true });
  }
  await registrar(page, 'Registrar envío', 'enviado');
  await registrar(page, 'Registrar aceptación', 'aceptado');
  assert.equal(await page.getByRole('link', { name: 'Registrar estado' }).count(), 0);

  await abrir(page, borrador.editar);
  const fecha = page.getByLabel('Válido Hasta');
  const entradaNotas = page.locator('#id_notas');
  assert.equal(await fecha.inputValue(), fixture.ayer);
  await entradaNotas.fill(notas);
  await guardar(page, 'Guardar cambios');
  assert.ok(await estadoVisible(page, 'borrador').isVisible());
  await abrir(page, borrador.editar);
  await confirmar(page, 200);
  const error = page.locator('#id_fecha_validez_error');
  await error.waitFor();
  assert.match(await error.textContent(), /Para emitir/);
  assert.match(await fecha.getAttribute('aria-describedby'), /id_fecha_validez_error/);
  assert.equal(await entradaNotas.inputValue(), notas);
  assert.ok(await page.locator(`#opt_${fixture.plan}`).isChecked());
  if (ancho === 390 && evidencia) {
    await error.scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(evidencia, 'pre03-emision-movil.png') });
  }
  await fecha.fill(fixture.hoy);
  await confirmar(page);
  assert.ok(await estadoVisible(page, 'emitido').isVisible());
  assert.ok(await page.getByRole('heading', { name: new RegExp(borrador.numero) }).isVisible());
  await registrar(page, 'Registrar rechazo', 'rechazado');
  assert.equal(await page.getByRole('link', { name: 'Registrar estado' }).count(), 0);

  await abrir(page, fixture.lista);
  const filtro = page.locator('#presupuestosEstado');
  for (const estado of ['emitido', 'vencido']) {
    await filtro.selectOption(estado);
    await Promise.all([
      page.waitForURL(url => url.searchParams.get('estado') === estado),
      page.getByRole('button', { name: 'Buscar', exact: true }).press('Enter'),
    ]);
    if (estado === 'vencido') {
      const fila = page.getByRole('row').filter({ hasText: fixture.numero_vencido });
      assert.ok(await fila.locator('[data-presupuesto-estado="vencido"]').isVisible());
      assert.equal(await fila.getByRole('link', { name: 'Registrar estado' }).count(), 0);
    } else {
      const fila = page.getByRole('row').filter({ hasText: fixture.numero_vigente });
      assert.ok(await fila.locator('[data-presupuesto-estado="emitido"]').isVisible());
      assert.equal(await estadoVisible(page, 'vencido').count(), 0);
    }
  }
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth), 0);
  console.log(`${motor} · ${ancho} px · ${js ? 'con' : 'sin'} JS · ciclo completo aprobado`);
}

async function main() {
  const browser = await { chromium, firefox, webkit }[motor].launch(motor === 'chromium' ? {
    executablePath: process.env.CUTLESS_TEST_CHROMIUM || undefined,
  } : {});
  try {
    for (const [ancho, tema, js] of [[320, 'dark', false], [390, 'light', true],
      [768, 'light', true], [1440, 'dark', true]]) {
      const context = await browser.newContext({
        viewport: { width: ancho, height: 900 }, colorScheme: tema, javaScriptEnabled: js,
        reducedMotion: 'reduce', locale: 'es-CL', serviceWorkers: 'block',
      });
      try {
        await context.addCookies([{ name: 'sessionid', value: fixture.session, url: origen.origin }]);
        await context.route('**/*', ruta => {
          const url = new URL(ruta.request().url());
          if (url.origin === origen.origin) {
            if (url.pathname.endsWith('/presupuestos/indicadores/')) {
              return ruta.fulfill({ json: { disponible: false } });
            }
            return ruta.continue();
          }
          if (url.pathname.endsWith('/bootstrap.min.css')) {
            return ruta.fulfill({ path: process.env.CUTLESS_TEST_BOOTSTRAP, contentType: 'text/css' });
          }
          if (url.pathname.endsWith('/bootstrap.bundle.min.js') && process.env.CUTLESS_TEST_BOOTSTRAP_JS) {
            return ruta.fulfill({ path: process.env.CUTLESS_TEST_BOOTSTRAP_JS, contentType: 'application/javascript' });
          }
          return ruta.abort();
        });
        await probar(await context.newPage(), ancho, js);
      } finally {
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
