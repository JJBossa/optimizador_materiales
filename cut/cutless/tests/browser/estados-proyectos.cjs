const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

function origenLocal(variable) {
  const url = new URL(process.env[variable]);
  assert.equal(url.protocol, 'http:');
  assert.equal(url.hostname, '127.0.0.1');
  return url.origin;
}

const origen = origenLocal('CUTLESS_TEST_ORIGIN');
const base = process.env.CUTLESS_TEST_BASE && origenLocal('CUTLESS_TEST_BASE');
const fixture = JSON.parse(fs.readFileSync(process.env.CUTLESS_TEST_FIXTURE, 'utf8'));
const estilos = process.env.CUTLESS_TEST_BOOTSTRAP;
const scripts = process.env.CUTLESS_TEST_BOOTSTRAP_JS;
const evidencia = process.env.CUTLESS_TEST_EVIDENCE;
const cdn = 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist';
assert.ok(fs.existsSync(estilos), 'Se requiere la copia local de Bootstrap 5.3.0.');

async function medir(page, ruta, selector, tema) {
  const respuesta = await page.goto(ruta);
  assert.equal(respuesta.status(), 200);
  assert.equal(page.url(), ruta);
  assert.equal(await page.locator('html').getAttribute('data-theme'), tema);
  await page.evaluate(() => document.fonts.ready);
  return page.locator(selector).evaluateAll(etiquetas => etiquetas.map(etiqueta => {
    const caja = etiqueta.getBoundingClientRect();
    const contenedor = etiqueta.parentElement.getBoundingClientRect();
    const rango = document.createRange();
    rango.selectNodeContents(etiqueta);
    const texto = rango.getBoundingClientRect();
    const css = getComputedStyle(etiqueta);
    return {
      estado: etiqueta.textContent.trim(), ancho: caja.width, alto: caja.height, x: caja.left,
      margenIzquierdo: caja.left - contenedor.left, margenDerecho: contenedor.right - caja.right,
      centroVertical: (caja.top + caja.bottom - contenedor.top - contenedor.bottom) / 2,
      centroTexto: (texto.left + texto.right - caja.left - caja.right) / 2,
      centroTextoVertical: (texto.top + texto.bottom - caja.top - caja.bottom) / 2,
      lineas: rango.getClientRects().length,
      estilo: [css.backgroundColor, css.color, css.borderColor, css.borderRadius,
        css.fontFamily, css.fontSize, css.fontWeight, css.lineHeight],
    };
  }));
}

async function inspeccionar(browser, servidor, ancho, tema, momento) {
  const context = await browser.newContext({
    viewport: { width: ancho, height: ancho > 768 ? 920 : 844 },
    colorScheme: tema, locale: 'es-CL', reducedMotion: 'reduce', serviceWorkers: 'block',
  });
  try {
    await context.addCookies([{ name: 'sessionid', value: fixture.session, url: servidor }]);
    await context.route('**/*', async ruta => {
      const url = ruta.request().url();
      if (url.startsWith(servidor + '/')) {
        if (new URL(url).pathname.endsWith('/cutless/css/fonts.css')) {
          const respuesta = await ruta.fetch({ maxRedirects: 0 });
          assert.ok(respuesta.ok());
          // Mide las mismas fuentes en ambos servidores con caché fría.
          const body = (await respuesta.text()).replaceAll('font-display: optional', 'font-display: swap');
          return ruta.fulfill({ response: respuesta, body });
        }
        return ruta.continue();
      }
      if (url === cdn + '/css/bootstrap.min.css') return ruta.fulfill({ path: estilos, contentType: 'text/css' });
      if (scripts && url === cdn + '/js/bootstrap.bundle.min.js') {
        return ruta.fulfill({ path: scripts, contentType: 'application/javascript' });
      }
      return ruta.abort();
    });
    const page = await context.newPage();
    const lista = await medir(page, servidor + fixture.lista, 'tbody td:nth-child(3) > .badge', tema);
    assert.equal(lista.length, 4);
    assert.deepEqual(lista.map(item => item.estado).sort(), Object.keys(fixture.detalles).sort());
    const tabla = page.locator('.table-responsive:has(> table)');
    const { pagina, tablaExtra, modo } = await tabla.evaluate(e => ({
      pagina: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      tablaExtra: e.scrollWidth - e.clientWidth,
      modo: getComputedStyle(e.querySelector('table')).display,
    }));
    const captura = (ancho === 390 && tema === 'light') || (ancho === 1280 && tema === 'dark');
    if (evidencia && captura) {
      await tabla.screenshot({
        path: path.join(evidencia, `vis01-${momento}-${ancho}.png`),
        style: '.navbar-custom { visibility: hidden; }',
      });
    }
    const detalles = {};
    for (const [estado, ruta] of Object.entries(fixture.detalles)) {
      const etiquetas = await medir(page, servidor + ruta, '.card-header > .badge', tema);
      assert.equal(etiquetas.length, 1, estado);
      assert.equal(etiquetas[0].estado, estado);
      detalles[estado] = etiquetas[0];
      const extra = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      assert.equal(extra, 0, `Detalle ${estado}, ${ancho} px, ${tema}`);
    }
    return { lista, detalles, pagina, tablaExtra, modo };
  } finally {
    await context.close();
  }
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CUTLESS_TEST_CHROMIUM || undefined });
  try {
    console.log(`Chromium ${browser.version()}`);
    for (const ancho of [320, 390, 768, 1280]) {
      for (const tema of ['light', 'dark']) {
        const antes = base && await inspeccionar(browser, base, ancho, tema, 'antes');
        const despues = await inspeccionar(browser, origen, ancho, tema, 'despues');
        const { lista, detalles } = despues;
        const dimensiones = items => items.map(({ estado, ancho, alto }) => [estado, ancho, alto]);
        console.log(JSON.stringify({ ancho, tema, antes: antes && dimensiones(antes.lista),
          despues: dimensiones(lista), pagina: despues.pagina,
          tablaAntes: antes && antes.tablaExtra, tablaDespues: despues.tablaExtra }));
        assert.equal(despues.pagina, 0);
        assert.equal(despues.tablaExtra, 0);
        assert.equal(despues.modo, ancho <= 575 ? 'block' : 'table');
        const referencia = lista[0];
        for (const etiqueta of [...lista, ...Object.values(detalles)]) {
          assert.equal(etiqueta.ancho, referencia.ancho, etiqueta.estado);
          assert.equal(etiqueta.alto, referencia.alto, etiqueta.estado);
          assert.equal(etiqueta.lineas, 1, etiqueta.estado);
          assert.ok(Math.abs(etiqueta.centroTexto) <= 1, JSON.stringify(etiqueta));
          assert.ok(Math.abs(etiqueta.centroTextoVertical) <= 3, JSON.stringify(etiqueta));
          assert.ok(etiqueta.margenIzquierdo >= 0 && etiqueta.margenDerecho >= 0, JSON.stringify(etiqueta));
        }
        for (const etiqueta of lista) {
          assert.equal(etiqueta.x, referencia.x, etiqueta.estado);
          if (ancho > 575) assert.ok(Math.abs(etiqueta.centroVertical) <= 1, JSON.stringify(etiqueta));
          if (antes) {
            assert.deepEqual(etiqueta.estilo, antes.lista.find(item => item.estado === etiqueta.estado).estilo);
            assert.deepEqual(detalles[etiqueta.estado].estilo, antes.detalles[etiqueta.estado].estilo);
          }
        }
      }
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
