const assert = require('node:assert/strict');
const { chromium, devices, webkit } = require('playwright');
const { contexto, origen } = require('./estadisticas-descargas-helpers.cjs');
const { abrir, boton, casos, comprobarArchivo, nombres } = require('./descargas.cjs');

const motores = { chromium, webkit };
const motor = process.env.CUTLESS_TEST_ENGINE || 'chromium';
const leyenda = 'Abre el archivo en otra pestaña. Si ves una vista previa, usa Compartir y Guardar en Archivos.';

async function comprobarNavegacion(page, enlace, formato, { ios, js, inline = false }) {
  const context = page.context();
  const url = page.url();
  const href = new URL(await enlace.getAttribute('href'), origen).href;
  const target = await enlace.getAttribute('target');
  if (ios && js && formato !== 'excel') {
    assert.equal(target, '_blank');
    assert.match(await enlace.getAttribute('rel'), /\bnoopener\b/);
    assert.equal(await enlace.getAttribute('aria-describedby'), 'cutless-download-ios-help');
    assert.equal(await page.locator('#cutless-download-ios-help').textContent(), leyenda);
  } else if (formato === 'excel') {
    assert.equal(target, null);
  }

  const inicio = await context.request.get(href);
  const [,, firma, mime] = nombres[formato];
  assert.equal(inicio.status(), 200, href);
  assert.equal(inicio.headers()['content-type'], mime);
  const disposicion = inicio.headers()['content-disposition'];
  assert.match(disposicion, inline ? /^inline; filename="ux03-archivado\.pdf"$/ : /^attachment; filename/i);
  assert.equal((await inicio.body()).subarray(0, firma.length / 2).toString('hex'), firma);
  await inicio.dispose();

  // Registrar la navegación real y cualquier intento de sustituir la activación del enlace.
  if (js) await page.evaluate(() => {
    window.pruebaDescarga = {};
    document.addEventListener('click', evento => {
      if (evento.target.closest('a[data-descarga]')) {
        window.pruebaDescarga.clic = [evento.isTrusted, evento.defaultPrevented];
      }
    });
    new MutationObserver(cambios => {
      for (const cambio of cambios) {
        for (const nodo of cambio.addedNodes) {
          if (nodo.matches?.('#loading-overlay, iframe')) window.pruebaDescarga.intercepcion = true;
        }
      }
    }).observe(document.body, { childList: true });
  });

  const espera = { timeout: 15000 };
  const [peticion, recepcion] = await Promise.all([
    context.waitForEvent('request', { ...espera, predicate: r => r.url() === href }),
    inline ? context.waitForEvent('page', espera) : page.waitForEvent('download', espera),
    ios ? enlace.tap() : enlace.click(),
  ]);
  assert.ok(peticion.isNavigationRequest(), href);
  if (inline) {
    await recepcion.waitForURL(href);
    assert.equal(await recepcion.evaluate(() => window.opener), null);
    await recepcion.close();
  } else {
    assert.equal(recepcion.url(), href);
    await comprobarArchivo(recepcion, formato);
    const nombre = disposicion.match(/filename="([^"]+)"/)?.[1];
    if (nombre?.startsWith('historial_costos_')) {
      // El servidor genera la fecha y hora del nombre en cada solicitud.
      assert.match(recepcion.suggestedFilename(), /^historial_costos_\d{8}_\d{6}\.xlsx$/);
    } else if (nombre) {
      assert.equal(recepcion.suggestedFilename(), nombre);
    }
  }
  assert.equal(page.url(), url);
  assert.equal(await enlace.getAttribute('aria-busy'), null);
  if (js) assert.deepEqual(await page.evaluate(() => window.pruebaDescarga), { clic: [true, false] });
}

async function probar(browser, config, opciones, etiqueta, seleccion = casos) {
  const context = await contexto(browser, origen, { ...config, javaScriptEnabled: opciones.js });
  try {
    await context.route('**/estadisticas/grafico-*/?*', route => route.abort());
    if (etiqueta === 'iPadOS en modo escritorio') {
      await context.addInitScript(() => Object.defineProperty(navigator, 'maxTouchPoints', { value: 5 }));
    }
    const page = await context.newPage();
    for (const [lugar, tipo, selector] of seleccion) {
      await abrir(page, lugar);
      const enlace = await boton(page, lugar, tipo, selector, opciones.js);
      await comprobarNavegacion(page, enlace, tipo, opciones);
      console.log(etiqueta, lugar, tipo, selector ?? '');
    }
    if (seleccion === casos) {
      await abrir(page, 'presupuestos');
      const fila = page.getByRole('row').filter({ hasText: 'PRE-UX03-ARCHIVADO' });
      await comprobarNavegacion(page, fila.locator('a[data-descarga="pdf"]'), 'pdf', { ...opciones, inline: true });
      await abrir(page, 'historico');
      const enlace = await boton(page, 'historico', 'pdf');
      await comprobarNavegacion(page, enlace, 'pdf', { ...opciones, inline: true });
      console.log(etiqueta, 'PDF archivado en listado y detalle');
    }
  } finally {
    await context.close();
  }
}

(async () => {
  assert.ok(motores[motor], motor);
  const browser = await motores[motor].launch({ executablePath: motor === 'chromium' ? process.env.CUTLESS_TEST_CHROMIUM : undefined });
  try {
    console.log(motor, browser.version());
    const { defaultBrowserType, ...iphone } = devices['iPhone 13'];
    await probar(browser, iphone, { ios: true, js: true }, 'iPhone emulado');
    const { defaultBrowserType: navegador, ...desktop } = devices['Desktop Safari'];
    await probar(browser, { ...desktop, hasTouch: true }, { ios: true, js: true }, 'iPadOS en modo escritorio', [
      ['resultado', 'pdf'], ['resultado', 'png'], ['estadisticas', 'excel', '.export-actions'],
    ]);
    await probar(browser, {}, { ios: false, js: false }, 'Sin JavaScript');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
