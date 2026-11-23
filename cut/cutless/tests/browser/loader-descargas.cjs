const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { chromium } = require('playwright');
const { contexto, fixture, origen } = require('./estadisticas-descargas-helpers.cjs');

const evidencia = process.env.CUTLESS_TEST_EVIDENCE;
const logoSelector = '#loading-overlay .cutless-loading__logo';
const esDescarga = url => url.origin === origen && url.searchParams.has('_cutless_download');

async function preparar(context, vista) {
  const page = await context.newPage();
  const errores = [];
  page.on('pageerror', error => errores.push(error.message));
  const url = origen + fixture.rutas[vista];
  assert.equal((await page.goto(url)).status(), 200, vista);
  await page.evaluate(() => {
    const traza = window.trazaDescarga = { fotogramas: 0 };
    const ahora = () => Math.round(performance.now() - traza.clic);
    document.addEventListener('click', event => {
      if (event.target.closest('a[data-descarga]')) traza.clic ??= performance.now();
    }, true);
    const clicNativo = HTMLAnchorElement.prototype.click;
    HTMLAnchorElement.prototype.click = function () {
      if (this.href.includes('_cutless_download')) {
        traza.pestana = [ahora(), traza.fotogramas, this.target];
      }
      return clicNativo.call(this);
    };
    new MutationObserver(() => {
      if (traza.clic === undefined) return;
      const overlay = document.getElementById('loading-overlay');
      if (overlay) traza.insercion ??= ahora();
      else if (traza.insercion !== undefined) traza.retirada ??= ahora();
      if (overlay?.matches('.cutless-loading--prepared')) {
        traza.preparado ??= [ahora(), getComputedStyle(overlay).pointerEvents,
          overlay.querySelector('[data-loading-message]').textContent,
          Boolean(document.querySelector('a[data-descarga][aria-busy]'))];
      }
    }).observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['class'] });
    function contarFotogramas() {
      if (document.getElementById('loading-overlay')) {
        traza.fotogramas++;
        traza.primerFotograma ??= ahora();
      }
      requestAnimationFrame(contarFotogramas);
    }
    requestAnimationFrame(contarFotogramas);
  });
  return { page, errores, url };
}

async function observarPiezas(page) {
  return page.locator(logoSelector + ' path').evaluateAll(piezas => piezas.map(pieza => {
    const estilo = getComputedStyle(pieza);
    return [estilo.animationName, estilo.animationDuration, estilo.animationPlayState,
      estilo.animationDelay, estilo.fill, Number(pieza.style.getPropertyValue('--piece-order'))];
  }).sort((a, b) => a[5] - b[5]));
}

async function esperarPaso(page, orden) {
  await page.waitForFunction(({ selector, orden }) => {
    const piezas = document.querySelectorAll(selector + ' path');
    const pieza = [...piezas].find(p => Number(p.style.getPropertyValue('--piece-order')) === orden);
    const reloj = pieza?.getAnimations()[0]?.currentTime;
    const desplazamiento = orden * 320;
    const fase = (reloj - desplazamiento) % 1600;
    return reloj >= desplazamiento && fase >= 50 && fase < 170;
  }, { selector: logoSelector, orden });
}

async function verificarAnimacion(browser, movimiento, ancho, tema) {
  const context = await contexto(browser, origen, {
    viewport: { width: ancho, height: 900 }, colorScheme: tema, reducedMotion: movimiento,
  });
  try {
    const { page, errores, url } = await preparar(context, 'historial');
    let liberar;
    const espera = new Promise(resolve => { liberar = resolve; });
    await context.route(esDescarga, async ruta => {
      await espera;
      await ruta.continue();
    });
    const recepcion = page.waitForEvent('download');
    recepcion.catch(() => {});
    try {
      await page.getByRole('button', { name: 'Más opciones' }).first().click();
      await page.locator('a[data-descarga="pdf"]:visible').press('Enter');
      const logo = page.locator(logoSelector);
      await logo.waitFor();
      const clip = await logo.evaluate(elemento => {
        const { x, y, width, height } = elemento.getBoundingClientRect();
        return { x: x + scrollX, y: y + scrollY, width, height, scale: 1 };
      });
      const protocolo = await context.newCDPSession(page);
      const captura = async sufijo => {
        // Captura del compositor, sin las esperas de estabilidad de locator.screenshot().
        const { data } = await protocolo.send('Page.captureScreenshot', { format: 'png', clip });
        const imagen = Buffer.from(data, 'base64');
        if (evidencia) await fs.writeFile(path.join(evidencia, `ux04-${movimiento}-${sufijo}.png`), imagen);
        return imagen;
      };
      if (movimiento === 'reduce') {
        const inicial = await observarPiezas(page);
        assert.ok(inicial.every(([nombre, duracion]) => nombre === 'none' && duracion === '0s'));
        const a = await captura('a');
        await page.waitForTimeout(400);
        assert.deepEqual(await observarPiezas(page), inicial);
        assert.deepEqual(await captura('b'), a, 'El logotipo pintado se mantiene estático.');
      } else {
        await esperarPaso(page, 0);
        const inicial = await observarPiezas(page);
        for (const [indice, pieza] of inicial.entries()) {
          assert.deepEqual(pieza.slice(0, 4), [
            'cutless-loading-piece', '1.6s', 'running', `${indice * 320 / 1000}s`,
          ]);
        }
        const a = await captura('a');
        await esperarPaso(page, 1);
        const siguiente = await observarPiezas(page);
        assert.notEqual(inicial[0][4], siguiente[0][4]);
        assert.notEqual(inicial[1][4], siguiente[1][4]);
        assert.equal(inicial[0][4], siguiente[1][4], 'El acento avanza a la segunda pieza.');
        const b = await captura('b');
        assert.notDeepEqual(a, b, 'Los fotogramas pintados del SVG deben diferir.');
      }
      assert.equal(await page.locator('#cutless-download-status').textContent(), 'Generando documento PDF...');
      await page.waitForFunction(() => performance.now() - window.trazaDescarga.clic >= 600);
    } finally {
      liberar();
    }
    const descarga = await recepcion;
    assert.equal(await descarga.failure(), null);
    await page.locator('#loading-overlay').waitFor({ state: 'detached', timeout: 5000 });
    const traza = await page.evaluate(() => window.trazaDescarga);
    assert.ok(traza.retirada - traza.insercion >= 420, JSON.stringify(traza));
    assert.equal(traza.preparado, undefined, 'Una preparación larga se retira al recibir la señal.');
    assert.equal(page.url(), url);
    assert.deepEqual(errores, []);
    console.log(movimiento, ancho, tema, JSON.stringify(traza));
  } finally {
    await context.close();
  }
}

async function verificarPresupuesto(browser, vista, ancho, tema, historico = vista === 'historico') {
  const context = await contexto(browser, origen, { viewport: { width: ancho, height: 900 }, colorScheme: tema });
  try {
    const { page, errores, url } = await preparar(context, vista);
    const pdf = vista === 'presupuestos'
      ? page.getByRole('row').filter({ hasText: historico ? /PRE-UX03-ARCHIVADO/ : /PRE-UX03(?!-ARCHIVADO)/ })
        .locator('a[data-descarga="pdf"]')
      : page.locator('a[data-descarga="pdf"]');
    const rutaPdf = await pdf.getAttribute('href');
    const original = await context.request.get(origen + rutaPdf);
    assert.equal(original.status(), 200);
    assert.equal(original.headers()['content-type'], 'application/pdf');
    assert.match(original.headers()['content-disposition'], historico
      ? /^inline; filename="ux03-archivado.pdf"/ : /^attachment; filename="presupuesto_PRE-UX03.pdf"/);
    if (historico) {
      const [pestana] = await Promise.all([context.waitForEvent('page'), pdf.press('Enter')]);
      await pestana.waitForURL(destino => destino.pathname === rutaPdf);
      assert.ok(await pestana.evaluate(() => window.opener === null));
      await pestana.close();
      const lectura = await context.request.get(origen + rutaPdf);
      assert.deepEqual(await lectura.body(), await original.body());
      await lectura.dispose();
    } else {
      const [descarga] = await Promise.all([page.waitForEvent('download'), pdf.press('Enter')]);
      assert.equal(await descarga.failure(), null);
      assert.equal(descarga.suggestedFilename(), 'presupuesto_PRE-UX03.pdf');
    }
    await original.dispose();
    await page.locator('#loading-overlay').waitFor({ state: 'detached', timeout: 5000 });
    assert.equal(await page.locator('#cutless-download-status').textContent(), '');
    const traza = await page.evaluate(() => window.trazaDescarga);
    assert.ok(traza.pestana[1] >= 1, JSON.stringify(traza));
    assert.equal(traza.pestana[2], '_blank');
    assert.ok(traza.retirada - traza.insercion >= 390 && traza.retirada < 1200, JSON.stringify(traza));
    if (traza.preparado) assert.deepEqual(traza.preparado.slice(1), ['none', 'Archivo preparado.', false]);
    assert.equal(page.url(), url);
    assert.deepEqual(errores, []);
    console.log(vista, historico ? 'archivado' : 'nuevo', ancho, tema, JSON.stringify(traza));
    return Boolean(traza.preparado);
  } finally {
    await context.close();
  }
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CUTLESS_TEST_CHROMIUM });
  try {
    await verificarAnimacion(browser, 'no-preference', 1280, 'dark');
    await verificarAnimacion(browser, 'reduce', 390, 'light');
    const resultados = [
      await verificarPresupuesto(browser, 'presupuestos', 390, 'light'),
      await verificarPresupuesto(browser, 'presupuesto', 1280, 'dark'),
      await verificarPresupuesto(browser, 'presupuestos', 390, 'light', true),
      await verificarPresupuesto(browser, 'historico', 1280, 'dark'),
    ];
    assert.ok(resultados.some(Boolean), 'Una respuesta rápida debe mostrar una preparación confirmada.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
