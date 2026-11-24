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
const bootstrap = process.env.CUTLESS_TEST_BOOTSTRAP;
const scripts = process.env.CUTLESS_TEST_BOOTSTRAP_JS;
const evidencia = process.env.CUTLESS_TEST_EVIDENCE;
const cdn = 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist';
assert.ok(fs.existsSync(bootstrap), 'Se requiere Bootstrap 5.3.0 local.');

const celda = 'tbody tr > td:last-child';
const modulos = {
  proyectos: celda, presupuestos: celda, clientes: celda, materiales: celda,
  plantillas: '.card-footer.action-group, .card-footer.management-action-set',
  proyecto: '.management-actions, .management-action-set--wide',
  presupuesto: '.form-action-bar',
  admin: '.admin-user-actions:has(.admin-action-btn)',
};
const anchos = [320, 390, 768, 1280];

async function contexto(browser, servidor, ancho, tema) {
  const context = await browser.newContext({
    viewport: { width: ancho, height: 920 }, colorScheme: tema, locale: 'es-CL',
    reducedMotion: 'reduce', serviceWorkers: 'block', acceptDownloads: true,
  });
  await context.addCookies([{ name: 'sessionid', value: fixture.session, url: servidor }]);
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.origin === servidor) {
      if (url.pathname.endsWith('/presupuestos/indicadores/')) {
        return route.fulfill({ json: { indicadores: {}, desde_cache: false } });
      }
      if (url.pathname.endsWith('/cutless/css/fonts.css')) {
        const response = await route.fetch({ maxRedirects: 0 });
        assert.ok(response.ok());
        const body = (await response.text()).replaceAll('font-display: optional', 'font-display: swap');
        return route.fulfill({ response, body });
      }
      return route.continue();
    }
    if (url.href === cdn + '/css/bootstrap.min.css') return route.fulfill({ path: bootstrap, contentType: 'text/css' });
    if (scripts && url.href === cdn + '/js/bootstrap.bundle.min.js') {
      return route.fulfill({ path: scripts, contentType: 'application/javascript' });
    }
    return route.abort();
  });
  return context;
}

async function abrir(page, servidor, modulo, tema) {
  const url = servidor + fixture.rutas[modulo];
  assert.equal((await page.goto(url)).status(), 200, modulo);
  assert.equal(page.url(), url);
  assert.equal(await page.locator('html').getAttribute('data-theme'), tema);
  await page.evaluate(() => document.fonts.ready);
}

async function medir(page, modulo) {
  return page.locator(modulos[modulo]).evaluateAll(grupos => {
    const contexto2d = document.createElement('canvas').getContext('2d', { willReadFrequently: true });
    const luminancia = color => {
      contexto2d.clearRect(0, 0, 1, 1);
      contexto2d.fillStyle = color;
      contexto2d.fillRect(0, 0, 1, 1);
      return Array.from(contexto2d.getImageData(0, 0, 1, 1).data).slice(0, 3)
        .map(canal => canal / 255)
        .map(canal => canal <= .04045 ? canal / 12.92 : ((canal + .055) / 1.055) ** 2.4)
        .reduce((suma, canal, i) => suma + canal * [.2126, .7152, .0722][i], 0);
    };
    return grupos.map(grupo => {
      const caja = grupo.getBoundingClientRect();
      return Array.from(grupo.querySelectorAll('.btn[data-action]')).map(boton => {
        const css = getComputedStyle(boton);
        const rect = boton.getBoundingClientRect();
        const rango = document.createRange();
        rango.selectNodeContents(boton);
        const texto = rango.getBoundingClientRect();
        let fondo = css.backgroundColor;
        for (let padre = boton.parentElement; fondo === 'rgba(0, 0, 0, 0)' && padre; padre = padre.parentElement) {
          fondo = getComputedStyle(padre).backgroundColor;
        }
        const tonos = [luminancia(css.color), luminancia(fondo)].sort((a, b) => a - b);
        return {
          nombre: boton.textContent.trim(), ancho: rect.width, alto: rect.height,
          x: rect.left - caja.left, y: rect.top - caja.top,
          gap: css.gap, padding: css.padding, alineacion: [css.alignItems, css.justifyContent],
          icono: boton.querySelector('.button-icon')?.getAttribute('aria-hidden'),
          cabe: rect.width > 0 && rect.height > 0 && rect.left >= caja.left - 1 && rect.right <= caja.right + 1
            && texto.left >= rect.left - 1 && texto.right <= rect.right + 1
            && texto.top >= rect.top - 1 && texto.bottom <= rect.bottom + 1,
          contraste: (tonos[1] + .05) / (tonos[0] + .05),
          estilo: [css.color, css.backgroundColor, css.borderColor, css.borderRadius,
            css.boxShadow, css.fontFamily, css.fontSize, css.fontWeight, css.lineHeight],
          destino: boton.getAttribute('href'), accion: boton.dataset.action, target: boton.getAttribute('target'),
        };
      });
    }).filter(grupo => grupo.length);
  });
}

async function sinDesbordamiento(page, modulo) {
  const extra = await page.evaluate(() => ({
    documento: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    tablas: Array.from(document.querySelectorAll('.management-action-table')).map(tabla =>
      tabla.parentElement.scrollWidth - tabla.parentElement.clientWidth),
  }));
  assert.ok(extra.documento <= 1 && extra.tablas.every(valor => valor <= 1), modulo + ' ' + JSON.stringify(extra));
}

async function captura(page, modulo, ancho, momento) {
  const selector = modulos[modulo];
  const destino = selector === celda ? (ancho === 1280 ? '.table-responsive' : 'tbody tr')
    : modulo === 'plantillas' ? '.card:has(.card-footer)' : selector;
  await page.locator(destino).first().screenshot({
    path: path.join(evidencia, `${modulo}-${momento}-${ancho}.png`),
    style: '.navbar-custom, #magnifier-toggle { visibility: hidden; }',
  });
}

function validar(grupos, modulo, grande = false) {
  assert.ok(grupos.length, modulo);
  const referencia = grupos[0][0];
  const alto = modulo === 'admin' ? 40 : 44;
  for (const grupo of grupos) {
    for (const boton of grupo) {
      assert.ok(boton.cabe, modulo + ' ' + JSON.stringify(boton));
      assert.ok(boton.alto >= alto, JSON.stringify(boton));
      assert.equal(boton.icono, 'true', JSON.stringify(boton));
      assert.ok(boton.contraste >= 4.5, JSON.stringify(boton));
      assert.equal(boton.gap, '8px');
      assert.equal(boton.padding, referencia.padding);
      assert.deepEqual(boton.alineacion, ['center', 'center']);
      if (!grande) {
        assert.equal(boton.alto, alto, modulo + ' ' + JSON.stringify(boton));
        assert.deepEqual(boton.estilo.slice(5), referencia.estilo.slice(5));
      }
      assert.ok(boton.ancho <= referencia.ancho + 1, modulo + ' ' + JSON.stringify(boton));
    }
    assert.ok(grupo.every(boton => Math.abs(boton.ancho - grupo[0].ancho) <= 1), modulo);
    for (const [indice, boton] of grupo.entries()) {
      for (const otro of grupo.slice(indice + 1)) {
        assert.ok(boton.y + boton.alto <= otro.y + 1 || boton.x + boton.ancho <= otro.x + 1,
          modulo + ' ' + boton.nombre + ' / ' + otro.nombre);
      }
    }
    if (modulos[modulo] !== celda && grupo.length === grupos[0].length) {
      assert.deepEqual(grupo.map(boton => [boton.x, boton.y]), grupos[0].map(boton => [boton.x, boton.y]), modulo);
    }
  }
  if (modulos[modulo] === celda) assert.ok(grupos.every(grupo => grupo[0].x === grupos[0][0].x), modulo);
}

async function probarMatriz(browser, ancho, tema) {
  const actual = await contexto(browser, origen, ancho, tema);
  const comparar = (ancho === 390 && tema === 'light') || (ancho === 1280 && tema === 'dark');
  const anterior = comparar && base && await contexto(browser, base, ancho, tema);
  try {
    const page = await actual.newPage();
    const previa = anterior && await anterior.newPage();
    for (const modulo of Object.keys(modulos)) {
      await abrir(page, origen, modulo, tema);
      const despues = await medir(page, modulo);
      validar(despues, modulo);
      await sinDesbordamiento(page, modulo);
      if (modulo === 'presupuestos' || modulo === 'proyectos') {
        const estados = await page.locator('tbody td > .badge').evaluateAll(etiquetas => etiquetas
          .filter(etiqueta => etiqueta.hasAttribute('data-presupuesto-estado') ||
            ['Enviado', 'Aceptado', 'Rechazado', 'Vencido', 'Borrador', 'Planificación',
              'En Proceso', 'Completado', 'Cancelado'].includes(etiqueta.textContent.trim()))
          .map(etiqueta => {
            const caja = etiqueta.getBoundingClientRect();
            return [caja.width, caja.height];
          }));
        assert.equal(estados.length, 5, modulo);
        assert.ok(estados.every(([ancho, alto]) => alto === 42 && (modulo !== 'proyectos' || ancho === 120)),
          modulo + ' ' + JSON.stringify(estados));
      }
      if (previa) {
        await abrir(previa, base, modulo, tema);
        const antes = await medir(previa, modulo);
        const apariencia = grupos => grupos.map(grupo => grupo.map(({ nombre, estilo, destino, accion, target }) =>
          [nombre, estilo, destino, accion, target]));
        assert.deepEqual(apariencia(despues), apariencia(antes), modulo);
        if (evidencia && (ancho === 390 || ['proyectos', 'presupuestos'].includes(modulo))) {
          await captura(previa, modulo, ancho, 'antes');
          await captura(page, modulo, ancho, 'despues');
        }
        console.log(modulo, ancho, tema, 'antes', antes[0].map(b => [b.nombre, b.ancho, b.alto]),
          'después', despues[0].map(b => [b.nombre, b.ancho, b.alto]));
      }
      if (ancho === 390 && tema === 'light') {
        const zoom = await page.addStyleTag({ content: 'html { zoom: 1.25; }' });
        validar(await medir(page, modulo), modulo, true);
        await sinDesbordamiento(page, modulo + ' zoom');
        await zoom.evaluate(e => e.remove());
        await page.addStyleTag({ content: 'html body .management-action-set .btn, html body.admin-users-page .admin-user-actions .btn { font-size: 18px !important; }' });
        validar(await medir(page, modulo), modulo, true);
        await sinDesbordamiento(page, modulo + ' texto ampliado');
      }
    }
    console.log(`Aprobado ${ancho} px, tema ${tema}`);
  } finally {
    if (anterior) await anterior.close();
    await actual.close();
  }
}

async function probarInteraccion(browser) {
  const context = await contexto(browser, origen, 390, 'light');
  try {
    const page = await context.newPage();
    await abrir(page, origen, 'proyectos', 'light');
    const grupo = page.locator('.management-action-set').first();
    const detalle = grupo.getByRole('link', { name: 'Ver detalle' });
    await detalle.focus();
    await page.keyboard.press('Tab');
    const editar = grupo.getByRole('link', { name: 'Editar' });
    assert.ok(await editar.evaluate(e => e === document.activeElement && e.matches(':focus-visible')
      && getComputedStyle(e).outlineStyle !== 'none'));
    await page.keyboard.press('Shift+Tab');
    const rutaDetalle = await detalle.getAttribute('href');
    await page.keyboard.press('Enter');
    await page.waitForURL(origen + rutaDetalle);
    const eliminar = page.locator('.management-action-set').getByRole('link', { name: 'Eliminar' });
    const rutaEliminar = await eliminar.getAttribute('href');
    await eliminar.click();
    await page.waitForURL(origen + rutaEliminar);
    await page.getByRole('button', { name: /eliminar/i }).first().waitFor();

    await abrir(page, origen, 'presupuestos', 'light');
    const pdf = page.locator('.management-action-set').first().getByRole('link', { name: 'PDF' });
    const respuesta = await context.request.get(origen + await pdf.getAttribute('href'));
    assert.equal(respuesta.status(), 200);
    assert.equal(respuesta.headers()['content-type'], 'application/pdf');

    await abrir(page, origen, 'historial', 'light');
    const menu = page.getByRole('button', { name: 'Más opciones' }).first();
    await menu.press('Enter');
    assert.equal(await menu.getAttribute('aria-expanded'), 'true');
    await page.getByRole('link', { name: 'Cambiar nombre' }).first().waitFor();
    await menu.press('Escape');
    assert.equal(await menu.getAttribute('aria-expanded'), 'false');
  } finally {
    await context.close();
  }
}

async function auditarOtrosGrupos(browser) {
  const context = await contexto(browser, origen, 390, 'light');
  try {
    const page = await context.newPage();
    for (const [modulo, selector] of Object.entries({
      historialCliente: 'tbody td:last-child .btn',
      costos: 'tbody td:last-child .btn',
      asociar: '.selection-actions .btn',
    })) {
      await abrir(page, origen, modulo, 'light');
      const dimensiones = await page.locator(selector).evaluateAll(botones => botones
        .filter(boton => boton.getClientRects().length)
        .map(boton => [boton.innerText.trim(), boton.offsetWidth, boton.offsetHeight]));
      assert.ok(dimensiones.length, modulo);
      console.log('Auditado', modulo, dimensiones.slice(0, 4));
    }
  } finally {
    await context.close();
  }
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CUTLESS_TEST_CHROMIUM || undefined });
  try {
    console.log(`Chromium ${browser.version()}`);
    for (const ancho of anchos) {
      for (const tema of ['light', 'dark']) await probarMatriz(browser, ancho, tema);
    }
    await probarInteraccion(browser);
    await auditarOtrosGrupos(browser);
    console.log('Aprobados teclado, foco, enlaces, PDF y menú de Historial.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
