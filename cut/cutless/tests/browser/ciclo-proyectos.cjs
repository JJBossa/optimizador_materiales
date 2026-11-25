const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium, firefox, webkit } = require('playwright');
const { contexto, fixture, origen } = require('./estadisticas-descargas-helpers.cjs');

const motor = process.env.CUTLESS_TEST_BROWSER || 'chromium';
const evidencia = process.env.CUTLESS_TEST_EVIDENCE;
const estado = (page, codigo) => page.locator(`[data-proyecto-estado="${codigo}"]`);
const exacta = '🪵'.repeat(75);

async function abrir(page, ruta) {
  assert.equal((await page.goto(origen + ruta)).status(), 200);
}

async function guardar(page, etiqueta, codigo = 302) {
  const boton = page.getByRole('button', { name: etiqueta, exact: true });
  const ruta = await boton.evaluate(elemento => elemento.form.action);
  const [respuesta] = await Promise.all([
    page.waitForResponse(r => r.url() === ruta && r.request().method() === 'POST'),
    boton.press('Enter'),
  ]);
  assert.equal(respuesta.status(), codigo);
  if (codigo === 302) await page.waitForURL(new URL(respuesta.headers().location, ruta).href);
}

async function confirmar(page, accion, boton, destino, aviso) {
  const resumen = page.locator('summary').filter({ hasText: accion });
  await resumen.press('Enter');
  assert.ok(await page.getByText(aviso).isVisible());
  await guardar(page, boton);
  await estado(page, destino).waitFor();
}

async function crearYCompletar(page) {
  await abrir(page, fixture.alta);
  assert.ok(await page.getByText('Estado inicial', { exact: true }).isVisible());
  assert.equal(await page.locator('select[name="estado"]').count(), 0);
  await page.locator('#id_nombre').fill('Proyecto nuevo sintético');
  await page.locator('#id_cliente').selectOption(String(fixture.cliente));
  await page.locator('#id_fecha_inicio').fill(fixture.manana);
  await guardar(page, 'Crear proyecto');
  await estado(page, 'planificacion').waitFor();
  await confirmar(page, 'Iniciar proyecto', 'Confirmar inicio', 'en_proceso', /El inicio está previsto para el/);
  await confirmar(page, 'Completar proyecto', 'Confirmar finalización', 'completado', /Se conservarán las fechas/);
  assert.equal(await page.locator('summary').filter({ hasText: 'Cancelar proyecto' }).count(), 0);
  assert.ok(await page.getByRole('link', { name: 'Editar Proyecto', exact: true }).isVisible());
}

async function comprobarAtraso(page, caso) {
  await abrir(page, fixture.lista);
  await page.locator('#proyectosEstado').selectOption('atrasado');
  await Promise.all([
    page.waitForURL(url => url.searchParams.get('estado') === 'atrasado'),
    page.getByRole('button', { name: 'Buscar', exact: true }).press('Enter'),
  ]);
  const fila = () => page.getByRole('row').filter({ hasText: caso.nombre }).locator('[data-proyecto-estado="atrasado"]');
  await fila().waitFor();
  await abrir(page, fixture.historial);
  await fila().waitFor();
  await abrir(page, caso.detalle);
  assert.ok(await estado(page, 'atrasado').isVisible());
  assert.ok(await page.getByText(/La fecha de finalización estimada ya pasó/).isVisible());
}

async function reprogramarYCancelar(page, caso, ancho, js) {
  await abrir(page, caso.editar);
  const descripcion = page.locator('#id_descripcion');
  const inicio = page.locator('#id_fecha_inicio');
  const final = page.locator('#id_fecha_fin');
  assert.equal(await final.inputValue(), fixture.ayer);
  assert.equal(await final.getAttribute('min'), null);
  assert.equal(await descripcion.getAttribute('maxlength'), '150');
  assert.ok(await estado(page, 'atrasado').isVisible());

  await descripcion.evaluate(e => e.removeAttribute('maxlength'));
  await descripcion.fill(exacta + 'a');
  if (js) assert.match(await descripcion.locator('xpath=following-sibling::small[1]').textContent(), /151\/150/);
  await inicio.fill(fixture.manana);
  await final.fill(fixture.hoy);
  await guardar(page, 'Guardar cambios', 200);
  await page.locator('#id_fecha_fin_error').waitFor();
  assert.match(await page.locator('#id_fecha_fin_error').textContent(), /anterior al inicio/);
  assert.ok(await page.locator('#id_descripcion_error').isVisible());
  assert.match(await final.getAttribute('aria-describedby'), /id_fecha_fin_error/);
  assert.equal(await descripcion.inputValue(), exacta + 'a');
  assert.equal(await final.inputValue(), fixture.hoy);
  assert.equal(await inicio.inputValue(), fixture.manana);
  if (ancho === 390 && evidencia) {
    await final.scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(evidencia, 'pro03-reprogramacion-movil.png') });
  }

  await inicio.fill('');
  await descripcion.fill(exacta);
  if (js) assert.equal(await descripcion.locator('xpath=following-sibling::small[1]').textContent(), '150/150 caracteres');
  await guardar(page, 'Guardar cambios');
  await estado(page, caso.operativo).waitFor();
  if (ancho === 1440 && evidencia) {
    await page.screenshot({ path: path.join(evidencia, 'pro03-reprogramado-escritorio.png') });
  }
  await confirmar(page, 'Cancelar proyecto', 'Confirmar cancelación', 'cancelado', /seguirán disponibles/);
  assert.ok(await page.getByRole('heading', { name: `Proyecto: ${caso.nombre}` }).isVisible());
  assert.equal(await page.locator('summary').filter({ hasText: 'Iniciar proyecto' }).count(), 0);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth), 0);
}

async function main() {
  const browser = await { chromium, firefox, webkit }[motor].launch(motor === 'chromium' ? {
    executablePath: process.env.CUTLESS_TEST_CHROMIUM || undefined,
  } : {});
  try {
    for (const [ancho, tema, js] of [[320, 'dark', false], [390, 'light', true],
      [768, 'light', true], [1440, 'dark', true]]) {
      const context = await contexto(browser, origen, {
        viewport: { width: ancho, height: 900 }, colorScheme: tema, javaScriptEnabled: js,
        timezoneId: 'Pacific/Kiritimati', reducedMotion: 'reduce',
      });
      try {
        const page = await context.newPage();
        await crearYCompletar(page);
        const caso = fixture.proyectos[ancho];
        await comprobarAtraso(page, caso);
        await reprogramarYCancelar(page, caso, ancho, js);
        if (js) assert.equal(await page.locator('html').getAttribute('data-theme'), tema);
        console.log(`${motor} · ${ancho} px · ${js ? 'con' : 'sin'} JS · ciclo completo aprobado`);
      } finally {
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
