const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

function origenLocal(valor) {
  const url = new URL(valor);
  assert.equal(url.protocol, 'http:');
  assert.equal(url.hostname, '127.0.0.1');
  return url.origin;
}

const origen = origenLocal(process.env.CUTLESS_TEST_ORIGIN);
const base = process.env.CUTLESS_TEST_BASE && origenLocal(process.env.CUTLESS_TEST_BASE);
const fixture = JSON.parse(fs.readFileSync(process.env.CUTLESS_TEST_FIXTURE, 'utf8'));
const bootstrap = process.env.CUTLESS_TEST_BOOTSTRAP;
const evidencia = process.env.CUTLESS_TEST_EVIDENCE;
const colores = { '10,6%': 'bg-danger', '53,6%': 'bg-danger', '70,0%': 'bg-warning', '100,0%': 'bg-success' };
assert.ok(bootstrap && fs.existsSync(bootstrap), 'Se requiere Bootstrap 5.3.0 local.');

async function abrir(page, servidor, vista, tema) {
  const respuesta = await page.goto(servidor + fixture.vistas[vista]);
  assert.equal(respuesta.status(), 200);
  assert.equal(page.url(), servidor + fixture.vistas[vista]);
  assert.equal(await page.locator('html').getAttribute('data-theme'), tema);
  await page.evaluate(() => document.fonts.ready);
  return page.getByRole('table').filter({
    has: page.getByRole('columnheader', { name: 'Aprovechamiento', exact: true }),
  });
}

async function medir(tabla) {
  const badges = await tabla.locator('tbody .badge').evaluateAll(etiquetas => etiquetas.map(etiqueta => {
    const caja = etiqueta.getBoundingClientRect();
    const celda = etiqueta.closest('td').getBoundingClientRect();
    const rango = document.createRange();
    rango.selectNodeContents(etiqueta);
    const texto = rango.getBoundingClientRect();
    const css = getComputedStyle(etiqueta);
    return {
      porcentaje: etiqueta.textContent.trim(), clases: Array.from(etiqueta.classList),
      dimensiones: [caja.width, caja.height],
      diferenciaX: (texto.left + texto.right - caja.left - caja.right) / 2,
      diferenciaY: (texto.top + texto.bottom - caja.top - caja.bottom) / 2,
      cabe: caja.left >= celda.left && caja.right <= celda.right
        && texto.left >= caja.left && texto.right <= caja.right
        && texto.top >= caja.top && texto.bottom <= caja.bottom,
      lineas: rango.getClientRects().length,
      estilo: [css.backgroundColor, css.color, css.borderColor, css.borderRadius,
        css.fontFamily, css.fontSize, css.fontWeight, css.lineHeight],
    };
  }));
  return Object.fromEntries(badges.map(badge => [badge.porcentaje, badge]));
}

async function verificarResultado(page) {
  const fila = page.getByRole('row').filter({ has: page.getByText(fixture.etiqueta, { exact: true }) });
  const enlace = fila.getByRole('link', { name: 'Ver resultado', exact: true });
  assert.equal(await enlace.getAttribute('href'), fixture.resultado);
  const destino = origen + fixture.resultado;
  const [respuesta] = await Promise.all([
    page.waitForResponse(item => item.url() === destino && item.request().isNavigationRequest()),
    enlace.click(),
  ]);
  assert.equal(respuesta.status(), 200);
  await page.waitForURL(destino);
  await page.getByRole('heading', { name: 'Resultado del plan de corte', exact: true }).waitFor();
  await page.getByText(fixture.etiqueta, { exact: true }).first().waitFor();
}

async function verificar(browser, ancho, tema, dimensiones) {
  const context = await browser.newContext({
    viewport: { width: ancho, height: 900 }, locale: 'es-CL', colorScheme: tema,
    reducedMotion: 'reduce', serviceWorkers: 'block',
  });
  try {
    for (const servidor of new Set([origen, base].filter(Boolean))) {
      await context.addCookies([{ name: 'sessionid', value: fixture.session, url: servidor }]);
    }
    await context.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.origin === origen || url.origin === base) {
        if (url.pathname.endsWith('/presupuestos/indicadores/')) {
          return route.fulfill({ json: { indicadores: {}, desde_cache: false } });
        }
        if (url.pathname.endsWith('/cutless/css/fonts.css')) {
          const respuesta = await route.fetch({ maxRedirects: 0 });
          const body = (await respuesta.text()).replaceAll('font-display: optional', 'font-display: swap');
          return route.fulfill({ response: respuesta, body });
        }
        return route.continue();
      }
      if (url.href === 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css') {
        return route.fulfill({ path: bootstrap, contentType: 'text/css' });
      }
      return route.abort();
    });

    const page = await context.newPage();
    for (const vista of Object.keys(fixture.vistas)) {
      const tabla = await abrir(page, origen, vista, tema);
      const badges = await medir(tabla);
      assert.deepEqual(Object.keys(badges).sort(), Object.keys(colores).sort(), vista);
      dimensiones ??= Object.values(badges)[0].dimensiones;
      for (const [valor, badge] of Object.entries(badges)) {
        assert.ok(badge.clases.includes('badge-aprovechamiento') && badge.clases.includes(colores[valor]), valor);
        assert.deepEqual(badge.dimensiones, dimensiones, vista);
        assert.ok(badge.cabe && badge.lineas === 1, JSON.stringify(badge));
        assert.ok(Math.abs(badge.diferenciaX) <= 1 && Math.abs(badge.diferenciaY) <= 2, JSON.stringify(badge));
      }
      const desbordes = await tabla.evaluate(elemento => ({
        pagina: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        tabla: elemento.parentElement.scrollWidth - elemento.parentElement.clientWidth,
      }));
      assert.ok(desbordes.pagina <= 1 && desbordes.tabla <= 1, JSON.stringify({ vista, ancho, desbordes }));
      const captura = evidencia && vista === 'proyecto'
        && ((ancho === 390 && tema === 'light') || (ancho === 1280 && tema === 'dark'));
      if (captura) {
        await tabla.screenshot({ path: path.join(evidencia, `despues-${ancho}.png`),
          style: '.navbar-custom, #magnifier-toggle { visibility: hidden; }' });
      }
      if (vista === 'proyecto') await verificarResultado(page);

      let anchoAnterior;
      if (base) {
        const tablaBase = await abrir(page, base, vista, tema);
        const anteriores = await medir(tablaBase);
        for (const [valor, badge] of Object.entries(badges)) {
          assert.deepEqual(badge.estilo, anteriores[valor].estilo, `${vista} ${valor} ${tema}`);
        }
        anchoAnterior = Object.fromEntries(Object.entries(anteriores).map(([valor, badge]) => [valor, badge.dimensiones[0]]));
        if (captura) {
          await tablaBase.screenshot({ path: path.join(evidencia, `antes-${ancho}.png`),
            style: '.navbar-custom, #magnifier-toggle { visibility: hidden; }' });
        }
      }
      console.log(JSON.stringify({ vista, ancho, tema, dimensiones, desbordes, anchoAnterior }));
    }
    return dimensiones;
  } finally {
    await context.close();
  }
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CUTLESS_TEST_CHROMIUM });
  try {
    console.log(`Chromium ${browser.version()}`);
    let dimensiones;
    for (const ancho of [320, 390, 1280]) {
      for (const tema of ['light', 'dark']) dimensiones = await verificar(browser, ancho, tema, dimensiones);
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
