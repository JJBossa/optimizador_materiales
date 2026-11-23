const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');
const { contexto, fixture, origen } = require('./estadisticas-descargas-helpers.cjs');

const evidencia = process.env.CUTLESS_TEST_EVIDENCE;
const nombres = {
  pdf: ['Generando documento PDF...', '.pdf', '255044462d', 'application/pdf'],
  excel: ['Preparando archivo Excel...', '.xlsx', '504b0304', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
  png: ['Generando imagen...', '.png', '89504e470d0a1a0a', 'image/png'],
};

const casos = [
  ['historial', 'pdf'], ['historial', 'excel'], ['historial', 'png'],
  ['resultado', 'pdf'], ['resultado', 'excel'], ['resultado', 'png'],
  ['presupuestos', 'pdf'], ['presupuesto', 'pdf'], ['tiempo', 'pdf'],
  ['estadisticas', 'excel', '.export-actions'], ['estadisticas', 'pdf', '.export-actions'],
  ['estadisticas', 'pdf', 'tbody'], ['costos', 'excel'],
];

async function abrir(page, lugar) {
  const url = origen + fixture.rutas[lugar];
  assert.equal((await page.goto(url)).status(), 200, lugar);
  assert.equal(page.url(), url);
  if (lugar === 'estadisticas') {
    const tabla = page.locator('table');
    await tabla.waitFor();
  }
  return url;
}

async function boton(page, lugar, tipo, selector = '', js = true) {
  if (lugar === 'historial' && js) await page.getByRole('button', { name: 'Más opciones' }).first().click();
  if (lugar === 'resultado' && tipo === 'png') {
    const detalles = page.locator('.result-details');
    if (await detalles.count() && !await detalles.evaluate(e => e.open)) await detalles.locator('summary').click();
  }
  let caja = selector ? page.locator(selector).first() : page;
  if (lugar === 'presupuestos') caja = page.getByRole('row').filter({ hasText: 'PRE-UX03' })
    .filter({ hasNotText: 'ARCHIVADO' });
  return caja.locator(`a[data-descarga="${tipo}"]`).first();
}

function solicitudObservable(url) {
  return url.origin === origen && url.searchParams.has('_cutless_download');
}

async function comprobarArchivo(descarga, tipo) {
  const [, extension, firma] = nombres[tipo];
  assert.ok(descarga.suggestedFilename().endsWith(extension), descarga.suggestedFilename());
  assert.equal(await descarga.failure(), null);
  const archivo = await fs.open(await descarga.path());
  try {
    const inicio = Buffer.alloc(firma.length / 2);
    const { bytesRead } = await archivo.read(inicio, 0, inicio.length, 0);
    assert.equal(bytesRead, inicio.length);
    assert.equal(inicio.toString('hex'), firma);
  } finally {
    await archivo.close();
  }
}

async function verificarDescarga(page, context, caso, { js = true, doble = false, captura, reutilizar = false } = {}) {
  const [lugar, tipo, selector] = caso;
  const url = reutilizar ? page.url() : await abrir(page, lugar);
  const enlace = await boton(page, lugar, tipo, selector, js);
  const ruta = new URL(await enlace.getAttribute('href'), origen);
  // La solicitud original mantiene su nombre de archivo y tipo de contenido.
  const directa = await context.request.get(ruta.href);
  assert.equal(directa.status(), 200, caso.join(' '));
  assert.equal(directa.headers()['content-type'], nombres[tipo][3]);
  assert.match(directa.headers()['content-disposition'], /^attachment; filename/i);
  await directa.dispose();

  let continuar;
  const espera = new Promise(resolve => { continuar = resolve; });
  let solicitudes = 0;
  const esperarServidor = async route => {
    solicitudes++;
    await espera;
    await route.continue();
  };
  if (js) await context.route(solicitudObservable, esperarServidor);
  const recepcion = page.waitForEvent('download');
  try {
    // Enter recorre el mismo enlace que la persona usa con el teclado.
    await enlace.press('Enter');
    if (js) {
      const overlay = page.locator('#loading-overlay');
      await overlay.getByText(nombres[tipo][0], { exact: true }).waitFor();
      assert.equal(await page.locator('#cutless-download-status').textContent(), nombres[tipo][0]);
      assert.equal(await enlace.getAttribute('aria-busy'), 'true');
      if (doble) {
        await enlace.evaluate(elemento => elemento.click());
        assert.equal(solicitudes, 1);
        await page.clock.fastForward(17000);
        assert.ok(await overlay.isVisible(), 'La preparación sigue pendiente después de 15 segundos.');
      }
      if (captura && evidencia) {
        await page.screenshot({ path: path.join(evidencia, `descarga-${captura}.png`) });
      }
      if (captura === 'movil') {
        assert.equal(await overlay.locator('.cutless-loading__piece').first()
          .evaluate(e => getComputedStyle(e).animationName), 'none');
      }
    }
  } finally {
    continuar();
  }
  await comprobarArchivo(await recepcion, tipo);
  await page.locator('#loading-overlay').waitFor({ state: 'detached', timeout: 5000 });
  assert.equal(await page.locator('#cutless-download-status').textContent(), '');
  assert.equal(page.url(), url);
  if (js) {
    assert.equal(solicitudes, 1);
    assert.equal(await enlace.getAttribute('aria-busy'), null);
    await context.unroute(solicitudObservable, esperarServidor);
  }
  console.log(`Archivo recibido: ${caso.join(' ')}${js ? '' : ' sin JavaScript'}.`);
}

async function verificarHistorico(page, context) {
  const url = await abrir(page, 'historico');
  const pdf = await boton(page, 'historico', 'pdf');
  const ruta = await pdf.getAttribute('href');
  const respuesta = await context.request.get(origen + ruta);
  assert.match(respuesta.headers()['content-disposition'], /^inline; filename="ux03-archivado.pdf"/);
  assert.equal(respuesta.headers()['content-type'], 'application/pdf');
  await respuesta.dispose();
  const [pestana] = await Promise.all([context.waitForEvent('page'), pdf.press('Enter')]);
  await pestana.waitForURL(destino => destino.pathname === ruta);
  await page.locator('#loading-overlay').waitFor({ state: 'detached', timeout: 5000 });
  assert.equal(page.url(), url);
  await pestana.close();
  console.log('El PDF archivado abrió su pestaña con Content-Disposition inline.');
}

async function errorVisible(page, texto) {
  await page.locator('#loading-overlay').waitFor({ state: 'detached', timeout: 6000 });
  const alerta = page.locator('#cutless-download-error').getByRole('alert');
  await alerta.waitFor();
  assert.match(await alerta.textContent(), texto);
  await page.getByRole('button', { name: 'Cerrar aviso de descarga' }).press('Enter');
  await alerta.waitFor({ state: 'hidden' });
}

async function verificarErrores(page, context) {
  await abrir(page, 'resultado');
  const pdf = await boton(page, 'resultado', 'pdf');
  for (const [codigo, texto] of [[401, /sesión ha expirado/], [403, /No tienes permiso/],
    [404, /no está disponible/], [500, /No se pudo preparar/]]) {
    const forzar = route => {
      const token = new URL(route.request().url()).searchParams.get('_cutless_download');
      return route.fulfill({
        status: codigo, body: 'Respuesta de prueba',
        headers: { 'Set-Cookie': `cutless_descarga_${token}=${codigo}; Path=/; SameSite=Lax` },
      });
    };
    await context.route(solicitudObservable, forzar);
    await pdf.press('Enter');
    await errorVisible(page, texto);
    await context.unroute(solicitudObservable, forzar);
    assert.equal(await pdf.getAttribute('aria-busy'), null);
  }

  const interrumpir = route => route.abort('failed');
  await context.route(solicitudObservable, interrumpir);
  await pdf.press('Enter');
  await page.clock.fastForward(20000);
  await page.clock.fastForward(101000);
  await errorVisible(page, /se pudo confirmar la preparación|interrumpió la solicitud/);
  await context.unroute(solicitudObservable, interrumpir);

  await context.clearCookies({ name: 'sessionid' });
  await pdf.press('Enter');
  await errorVisible(page, /sesión ha expirado/);
  console.log('Recuperación aprobada para 401, 403, 404, 500, interrupción y sesión expirada.');
}

async function verificarRegreso(page, context) {
  await abrir(page, 'resultado');
  let liberar;
  const bloqueada = new Promise(resolve => { liberar = resolve; });
  const detener = async ruta => {
    await bloqueada;
    await ruta.abort().catch(() => {});
  };
  await context.route(solicitudObservable, detener);
  try {
    await (await boton(page, 'resultado', 'pdf')).press('Enter');
    await page.locator('#loading-overlay').waitFor();
    await abrir(page, 'historial');
    await page.goBack();
    assert.equal(await page.locator('#loading-overlay').count(), 0);
    assert.equal(await page.locator('a[data-descarga][aria-busy]').count(), 0);
    assert.equal(await page.locator('#cutless-download-status').textContent(), '');
  } finally {
    liberar();
    await context.unroute(solicitudObservable, detener);
  }
  console.log('Atrás restaura la página sin espera pendiente tras interrumpir la preparación.');
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CUTLESS_TEST_CHROMIUM });
  try {
    const movil = await contexto(browser, origen, {
      viewport: { width: 390, height: 844 }, colorScheme: 'light', reducedMotion: 'reduce',
    });
    const page = await movil.newPage();
    await page.clock.install();
    await movil.route('**/estadisticas/grafico-*/?*', route => route.abort());
    for (const [i, caso] of casos.entries()) {
      await verificarDescarga(page, movil, caso, {
        doble: i === 0, captura: i === 0 ? 'movil' : null, reutilizar: casos[i - 1]?.[0] === caso[0],
      });
    }
    await verificarHistorico(page, movil);
    const url = await abrir(page, 'estadisticas');
    const navegar = page.getByRole('link', { name: 'Ver resultado' }).first();
    await navegar.click();
    await page.waitForURL(destino => destino.href !== url);
    assert.equal(await page.locator('#loading-overlay').count(), 0);
    await verificarRegreso(page, movil);
    await verificarErrores(page, movil);
    await movil.close();

    const escritorio = await contexto(browser, origen, { viewport: { width: 1280, height: 900 }, colorScheme: 'dark' });
    await verificarDescarga(await escritorio.newPage(), escritorio, ['historial', 'excel'], { captura: 'escritorio' });
    await escritorio.close();

    const sinJs = await contexto(browser, origen, { javaScriptEnabled: false });
    const sinScript = await sinJs.newPage();
    for (const caso of [['historial', 'png'], ['presupuesto', 'pdf'], ['estadisticas', 'excel', '.export-actions']]) {
      await verificarDescarga(sinScript, sinJs, caso, { js: false });
    }
    await sinJs.close();
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
