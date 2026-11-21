/* Ejecutar contra servidor.py. Solo se permiten loopback y los recursos fijados de la interfaz. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium, webkit, devices } = require('playwright');

const host = new URL(process.env.TUTORIAL_BASE_URL || 'http://127.0.0.1:8775');
assert.equal(host.hostname, '127.0.0.1');
const output = process.env.TUTORIAL_ARTIFACTS;
const widths = [320, 360, 390, 430];
const versions = {
  '/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css': 'bootstrap.min.css',
  '/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js': 'bootstrap.bundle.min.js',
  '/npm/intro.js@7.2.0/minified/introjs.min.css': 'introjs.min.css',
  '/npm/intro.js@7.2.0/minified/intro.min.js': 'intro.min.js'
};
const abreNav = '#btn-tutorial';
const ayuda = '.btn-ayuda-seccion';
const ancho = 'button[aria-label="Cómo medir el tablero"]';
const piezas = 'button[aria-label="Cómo añadir piezas"]';
const siguiente = '.introjs-nextbutton';
const cerrar = '.introjs-skipbutton';
const cuadro = '.introjs-tooltip.customTooltip';
const capas = '.introjs-overlay,.introjs-tooltipReferenceLayer,.introjs-helperLayer,.introjs-disableInteraction,.introjsFloatingElement,.introjs-showElement,.introjs-fixParent';
const inicio = '/cutless/';
const editar = '/cutless/editar/1/';
const casos = [
  ['inicio', inicio, abreNav, 'input[name="ancho"], textarea[name$="-nombre"], #optimizacion-form button[type="submit"]', 4],
  ['tablero', inicio, ancho, '#tableros-dropdown', 2],
  ['piezas', inicio, piezas, '#add-pieza', 2],
  ['historial', '/cutless/historial/', ayuda, '.search-filters,.favorito-btn,.action-buttons', 4],
  ['resultado', '/cutless/resultado/1/', ayuda, '.total-utilization,.cut-drawing-card,.cut-pieces', 4],
  ['estadisticas', '/cutless/estadisticas/', ayuda, '.stats-card,select[name="periodo"],.chart-container,.table-responsive', 5],
  ['costos', '/cutless/historial-costos/', ayuda, '.stats-card,.filter-card input[type="date"],.chart-container,.table-responsive', 5],
  ['presupuestos', '/cutless/presupuestos/', ayuda, '.page-header__actions a[href$="/presupuestos/crear/"]', 4],
  ['crear_presupuesto', '/cutless/presupuestos/crear/', ayuda, '.budget-plan-selector', 4],
  ['editar_presupuesto', '/cutless/presupuestos/editar/1/', ayuda, '.budget-plan-selector', 4],
  ['detalle_presupuesto', '/cutless/presupuestos/1/', ayuda, '.costo-total', 4],
  ['presupuesto_emitido', '/cutless/presupuestos/editar/2/', abreNav],
  ['agregar_presupuesto', '/cutless/presupuestos/1/agregar-optimizaciones/', ayuda],
  ['proyectos', '/cutless/proyectos/', ayuda, '.page-header__actions a[href$="/proyectos/crear/"]', 4],
  ['crear_proyecto', '/cutless/proyectos/crear/', ayuda, '.budget-plan-selector', 4],
  ['editar_proyecto', '/cutless/proyectos/editar/1/', ayuda, '.budget-plan-selector', 4],
  ['detalle_proyecto', '/cutless/proyectos/1/', ayuda, '.costo-total', 4],
  ['agregar_proyecto', '/cutless/proyectos/1/agregar-optimizaciones/', ayuda],
  ['clientes', '/cutless/clientes/', ayuda, '.page-header__actions a[href$="/clientes/crear/"]', 4],
  ['crear_cliente', '/cutless/clientes/crear/', ayuda],
  ['editar_cliente', '/cutless/clientes/editar/1/', ayuda],
  ['historial_cliente', '/cutless/clientes/historial/1/', ayuda],
  ['materiales', '/cutless/materiales/', ayuda, '.page-header__actions a[href$="/materiales/crear/"]', 4],
  ['crear_material', '/cutless/materiales/crear/', ayuda],
  ['editar_material', '/cutless/materiales/editar/1/', ayuda],
  ['plantillas', '/cutless/plantillas/', ayuda, '.page-header__actions a[href$="/plantillas/crear/"],.card-footer a[href*="/plantillas/usar/"]', 4],
  ['crear_plantilla', '/cutless/plantillas/crear/', ayuda],
  ['editar_plantilla', '/cutless/plantillas/editar/1/', ayuda],
  ['perfil', '/usuarios/perfil/', ayuda, '#perfil-tab,#seguridad-tab', 6],
  ['configuracion_sistema', '/usuarios/configuracion-sistema/', abreNav, '#tabOpti select', 6],
  ['comparar', '/cutless/comparar/?opt1=1&opt2=2', ayuda, '[aria-labelledby="comparison-decision-title"]'],
  ['calcular_tiempo', '/cutless/calcular-tiempo/1/', ayuda, '#parametros-tiempo,#resumen-piezas-tiempo', 4],
  ['editar_optimizacion', editar, abreNav, '#optimizacion-form button[type="submit"]', 4],
  ['tablero_edicion', editar, 'button[onclick*="\'tablero\'"]', 'input[name="ancho"],select[name="unidad_medida"]', 2],
  ['piezas_edicion', editar, 'button[onclick*="\'piezas\'"]', '#add-pieza', 2],
  ['costos_optimizacion', editar, 'button[onclick*="costos_optimizacion"]', '#precio_tablero,#mano_obra', 2]
];

async function context(browser, width, theme, state, device = {}) {
  const ctx = await browser.newContext({
    viewport: { width, height: width > 600 ? 900 : 800 },
    isMobile: width <= 600, hasTouch: width <= 600,
    ...device, colorScheme: theme,
    reducedMotion: process.env.TUTORIAL_MOTION || 'reduce', storageState: state
  });
  await ctx.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin === host.origin) return route.continue();
    const asset = versions[url.pathname];
    if (url.origin === 'https://cdn.jsdelivr.net' && asset) {
      if (process.env.TUTORIAL_ASSETS) {
        return route.fulfill({ path: path.join(process.env.TUTORIAL_ASSETS, asset),
          contentType: asset.endsWith('.js') ? 'text/javascript' : 'text/css' });
      }
      return route.continue();
    }
    return route.abort();
  });
  return ctx;
}

async function navegar(page, uri) {
  const response = await page.goto(new URL(uri, host).href, { waitUntil: 'load' });
  assert.equal(response.status(), 200, uri);
  await page.evaluate(() => document.fonts.ready);
  await page.waitForFunction(() => window.introJs?.version === '7.2.0');
}

async function login(ctx, user = 'auditoria') {
  const password = process.env.TUTORIAL_TEST_PASSWORD;
  assert(password, 'Define la misma TUTORIAL_TEST_PASSWORD que usa el servidor temporal.');
  const page = await ctx.newPage();
  await navegar(page, '/usuarios/login/');
  await page.locator('[name="username"]').fill(user);
  await page.locator('[name="password"]').fill(password);
  await page.locator('form.login-form').evaluate(form => form.requestSubmit());
  await page.waitForURL(url => url.pathname === inicio);
  return page;
}

async function abrir(page, selector) {
  const botonMenu = page.locator('.navbar-toggler');
  if (selector === abreNav && await botonMenu.isVisible()) {
    await botonMenu.click();
    await page.locator('#navbarNav.show').waitFor();
  }
  await page.locator(selector).first().click();
  await page.waitForFunction(({ cuadro, siguiente }) => {
    const panel = document.querySelector(cuadro);
    return panel?.getClientRects().length && panel.querySelector(siguiente)?.textContent;
  }, { cuadro, siguiente });
}

async function estable(page, indice, anterior = null) {
  await page.waitForFunction(({ cuadro, indice, anterior }) => {
    const [id, guia] = Object.entries(introJs.instances)[0] || [];
    const panel = document.querySelector(cuadro);
    return id !== anterior && guia?.currentStep() === indice && panel?.getClientRects().length &&
      getComputedStyle(panel).opacity === '1' &&
      panel.querySelector('.introjs-tooltip-title').textContent === guia._introItems[indice].title;
  }, { cuadro, indice, anterior });
}

async function geometria(page, indice) {
  return page.evaluate(({ cuadro, indice }) => {
    const guia = Object.values(introJs.instances)[0];
    const paso = guia._introItems[indice];
    const panel = document.querySelector(cuadro);
    const titulo = panel.querySelector('.introjs-tooltip-title');
    const texto = panel.querySelector('.introjs-tooltiptext');
    const controles = [...panel.querySelectorAll('.introjs-skipbutton, .introjs-tooltipbuttons [role="button"]:not([aria-disabled="true"])')]
      .filter(e => e.getClientRects().length);
    const vista = window.visualViewport;
    const caja = panel.getBoundingClientRect();
    return {
      titulo: titulo.textContent,
      texto: texto.textContent.trim(),
      foco: panel.contains(document.activeElement),
      cantidad: guia._introItems.length,
      ancla: paso.element?.id || paso.element?.className || paso.element?.tagName,
      anclaVisible: Boolean(paso.element?.classList.contains('introjsFloatingElement') ||
        (paso.element?.isConnected && paso.element.getClientRects().length &&
        getComputedStyle(paso.element).visibility === 'visible' &&
        paso.element.closest('.app-main') && paso.element.classList.contains('introjs-showElement'))),
      ancho: document.documentElement.clientWidth,
      alto: vista.height, desplX: scrollX, desplY: scrollY,
      vista: { x: vista.offsetLeft, y: vista.offsetTop, ancho: vista.width, alto: vista.height, escala: vista.scale },
      margenes: { izquierdo: caja.left - vista.offsetLeft, derecho: vista.offsetLeft + vista.width - caja.right },
      desborde: panel.scrollWidth - panel.clientWidth,
      panel: caja.toJSON(),
      controles: controles.map(e => {
        const rect = e.getBoundingClientRect();
        return { ...rect.toJSON(), accion: e.getAttribute('aria-label') || e.textContent.trim(),
          accesible: e.contains(document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2)) };
      }),
      desbordeTexto: texto.scrollWidth - texto.clientWidth
    };
  }, { cuadro, indice });
}

function comprobarGeometriaMovil(datos, nombre) {
  const { panel, vista, margenes } = datos;
  const detalle = `${nombre} ${JSON.stringify(datos)}`;
  assert(datos.texto.length && datos.anclaVisible && datos.foco, detalle);
  assert(margenes.izquierdo >= 11 && margenes.derecho >= 11 &&
    Math.abs(margenes.izquierdo - margenes.derecho) <= 1, detalle);
  assert(panel.top >= vista.y + 11 && panel.bottom <= vista.y + vista.alto - 11 &&
    datos.desplX === 0 && datos.desborde <= 1 && datos.desbordeTexto <= 1, detalle);
  assert(datos.controles.length >= 2 && datos.controles.every(c => c.top >= vista.y &&
    c.bottom <= vista.y + vista.alto + 1 && c.left >= vista.x && c.right <= vista.x + vista.ancho + 1 &&
    c.width >= 24 && c.height >= 24 && c.accesible), detalle);
}

async function comprobarCierre(page, trigger, foco) {
  await page.waitForFunction(capas => !document.querySelector(capas) &&
    !document.body.classList.contains('tutorial-running') &&
    !document.body.classList.contains('modal-open') &&
    !document.documentElement.classList.contains('mobile-nav-open') &&
    !document.querySelector('.app-main').inert &&
    Object.keys(introJs.instances).length === 0, capas);
  const selector = trigger === abreNav && await page.locator('.navbar-toggler').isVisible() ?
    '.navbar-toggler' : trigger;
  if (foco) assert.equal(await page.locator(selector).first().evaluate(el => document.activeElement === el), true, selector);
  // Una comprobación de acción real de puntero. No dispara el botón.
  await page.locator(selector).first().click({ trial: true, timeout: 4000 });
}

async function recorrer(page, caso, width, theme, samples) {
  const [nombre, , trigger, anchors, exacto] = caso;
  const opciones = await page.evaluate(selector => {
    const guia = Object.values(introJs.instances)[0];
    return { pasos: guia._introItems.length,
      coincide: selector ? selector.split(',').every(patron =>
        guia._introItems.some(step => step.element.matches(patron))) : true };
  }, anchors);
  if (exacto) assert.equal(opciones.pasos, exacto, nombre);
  assert(opciones.coincide, nombre + ' no resalta los elementos del caso');
  for (let i = 0; i < opciones.pasos; i++) {
    await estable(page, i);
    const datos = await geometria(page, i);
    assert(datos.texto.length && datos.anclaVisible && datos.foco, nombre + ' ' + JSON.stringify(datos));
    if (width <= 600) comprobarGeometriaMovil(datos, nombre);
    if (samples) {
      samples.push({ nombre, width, theme, paso: i+1, ...datos });
      if (output && ['perfil','inicio','costos'].includes(nombre) && i === 1 && (width === 320 || width === 430)) {
        await page.screenshot({ path: path.join(output, `${nombre}-${width}-${theme}.png`), animations: 'disabled' });
      }
    }
    const control = page.locator(siguiente);
    if (i+1 === opciones.pasos) assert.equal((await control.innerText()).trim(),'Finalizar',nombre);
    await control.click();
  }
  await comprobarCierre(page, trigger, true);
}

async function lote(browser, state, width, theme, repeat, lista = casos) {
  const ctx = await context(browser,width,theme,state);
  const page = await ctx.newPage();
  const samples = [];
  const errors = [];
  const fallos = [];
  page.on('pageerror', e => errors.push(e.message));
  try {
    for (const caso of lista) {
      const [name,url,trigger] = caso;
      try {
        await navegar(page,url);
        assert.equal(await page.locator('html').getAttribute('data-theme'),theme);
        for (let i=0;i<repeat;i++) {
          await abrir(page,trigger);
          await recorrer(page,caso,width,theme,i===0 ? samples : null);
        }
        for (let i=0;i<repeat;i++) {
          await abrir(page,trigger);
          await page.locator(cerrar).click();
          await comprobarCierre(page,trigger,true);
        }
        await abrir(page,trigger);
        await page.keyboard.press('Escape');
        await comprobarCierre(page,trigger,true);
        assert.deepEqual(errors,[]);
        console.log('OK',name,theme,width);
      } catch (err) {
        if (output) await page.screenshot({ path: path.join(output,`error-${name}-${width}-${theme}.png`) });
        const fallo = new Error(`${name} · ${theme} · ${width}: ${err.message}`, {cause:err});
        if (process.argv[2] !== 'diagnostico') throw fallo;
        console.error(fallo.message);
        fallos.push(fallo);
        errors.length = 0;
      }
    }
  } finally { await ctx.close(); }
  if (fallos.length) throw new AggregateError(fallos,'Fallaron '+fallos.length+' recorridos');
  return samples;
}

async function baseOriginal(browser,state) {
  const ctx = await context(browser,1366,'light',state);
  const page = await ctx.newPage();
  try {
    for (const [name,url,selector] of casos) {
      await navegar(page,url);
      const trigger = name === 'costos_optimizacion' ? 'button[onclick*="\'costos\'"]' : selector;
      await abrir(page,trigger);
      const index = await page.evaluate(async () => {
        const guia = guiaActiva;
        const ultimo = guia._introItems.length;
        await guia.goToStep(ultimo);
        return ultimo-1;
      });
      await estable(page,index);
      await page.evaluate(({trigger,siguiente}) => {
        document.querySelector(siguiente).click();
        document.querySelector(trigger).click();
      },{trigger,siguiente});
      await page.waitForTimeout(650);
      const resultado = await page.evaluate(cuadro => ({
        capas: document.querySelectorAll('.introjs-overlay,.introjs-helperLayer').length,
        capasVisibles: [...document.querySelectorAll('.introjs-overlay,.introjs-helperLayer')]
          .filter(el => el.getClientRects().length && getComputedStyle(el).opacity !== '0').length,
        cuadroVisible: Boolean(document.querySelector(cuadro)?.getClientRects().length),
        instancias: Object.keys(introJs.instances).length
      }),cuadro);
      const estado = resultado.cuadroVisible ? 'VISIBLE' :
        resultado.capasVisibles ? 'BLOQUEO' : 'SIN CUADRO';
      console.log('BASE',name,estado,JSON.stringify(resultado));
    }
  } finally { await ctx.close(); }
}

async function carreras(browser,state,lista) {
  const ctx = await context(browser,1366,'light',state);
  const page = await ctx.newPage();
  try {
    for (const caso of lista) {
      const [name,url,trigger] = caso;
      await navegar(page,url);
      await abrir(page,trigger);
      await page.evaluate(({ trigger, siguiente }) => {
        const paso = Object.values(introJs.instances)[0]._introItems.length;
        const guia = Object.values(introJs.instances)[0];
        // Se abre otra guía en la misma tarea que la finalización. El contrato visual sigue siendo el de la UI.
        return guia.goToStep(paso).then(() => new Promise(resolve => requestAnimationFrame(resolve)));
      },{trigger,siguiente});
      const indice = await page.evaluate(()=>Object.values(introJs.instances)[0]._introItems.length-1);
      await estable(page,indice);
      const primera = await page.evaluate(()=>Object.keys(introJs.instances)[0]);
      await page.evaluate(({trigger,siguiente}) => {
        document.querySelector(siguiente).click();
        document.querySelector(trigger).click();
        document.querySelector(trigger).click();
      },{trigger,siguiente});
      await estable(page,0,primera);
      await page.waitForFunction(()=>document.querySelectorAll('.introjs-overlay').length===1 &&
        document.querySelectorAll('.introjs-helperLayer').length===1 &&
        document.querySelectorAll('.introjs-tooltip').length===1);
      if (name==='historial' && output) {
        await page.screenshot({path:path.join(output,'historial-reabierto.png'),animations:'disabled'});
      }
      const segunda = await page.evaluate(()=>Object.keys(introJs.instances)[0]);
      await page.evaluate(({ trigger, cerrar }) => {
        document.querySelector(cerrar).click();
        document.querySelector(trigger).click();
      }, { trigger, cerrar });
      await estable(page,0,segunda);
      await page.locator(siguiente).evaluate(el=>el.click());
      await page.keyboard.press('Escape');
      await comprobarCierre(page,trigger,true);
      await abrir(page,trigger);
      await estable(page,0);
      await page.locator(cerrar).click();
      await comprobarCierre(page,trigger,true);
      console.log('Carrera controlada',name);
    }
    await navegar(page,inicio);
    await page.evaluate(async () => {
      const invis=document.createElement('div');
      invis.hidden=true;
      document.body.append(invis);
      await mostrarGuia([{ title:'Oculto',intro:'Oculto',element:invis },
        { title:'Ausente',intro:'Ausente',element:null },
        { title:'Body',intro:'Body',element:document.body }]);
      invis.remove();
    });
    await estable(page,0);
    assert.equal((await page.locator('.introjs-tooltip-title').innerText()).trim(),'Ayuda');
    await page.keyboard.press('Escape');
    await comprobarCierre(page,abreNav,false);
    await abrir(page,abreNav);
    await page.keyboard.press('Tab');
    assert(await page.locator(cuadro).evaluate(el=>el.contains(document.activeElement)));
    await page.keyboard.press('Shift+Tab');
    assert(await page.locator(cuadro).evaluate(el=>el.contains(document.activeElement)));
    await page.goto(new URL('/cutless/historial/',host).href);
    await page.goBack();
    await comprobarCierre(page,abreNav,false);
  } finally {await ctx.close();}
}

async function viewportCorto(browser,state) {
  const ctx = await context(browser,320,'dark',state);
  const page = await ctx.newPage();
  try {
    await navegar(page,inicio);
    await page.setViewportSize({width:320,height:320});
    await page.evaluate(()=>mostrarGuia([{title:'Ayuda de dimensiones',intro:'Identificador'+ 'CarpinteríaInternacional'.repeat(40)}]));
    await estable(page,0);
    const r=await geometria(page,0);
    assert(r.panel.bottom<=321 && r.panel.left>=0 && r.panel.right<=321 && r.desbordeTexto<=1);
    const scroll=page.locator('.introjs-tooltiptext');
    assert(await scroll.evaluate(el=>el.scrollHeight>el.clientHeight));
    await scroll.evaluate(el=>el.scrollTop=el.scrollHeight);
    assert(await scroll.evaluate(el=>el.scrollTop>0));
    // Activar el control enfocable y visible sin depender de la posición previa del scroll.
    await page.locator(cerrar).press('Enter');
    await comprobarCierre(page,abreNav,false);
    console.log('Área visible reducida y texto largo');
  } finally {await ctx.close();}
}

async function configuracionMovil(browser, state, motor, tema) {
  const nombre = 'configuracion_sistema';
  const [, uri, lanzar] = casos.find(caso => caso[0] === nombre);
  const { defaultBrowserType, ...iphone } = devices['iPhone 13'];
  const ctx = await context(browser, iphone.viewport.width, tema, state, iphone);
  try {
    const page = await ctx.newPage();
    const muestras = [];
    const errores = [];
    page.on('pageerror', error => errores.push(error.message));

    async function medir(paso, escenario) {
      await estable(page, paso);
      await page.waitForFunction(selector => {
        const { style } = document.querySelector(selector);
        const vista = window.visualViewport;
        return parseFloat(style.getPropertyValue('--ayuda-ancho-visible')) === vista.width &&
          parseFloat(style.getPropertyValue('--ayuda-alto-visible')) === vista.height &&
          parseFloat(style.getPropertyValue('--ayuda-borde-inferior-visible')) === vista.offsetTop + vista.height;
      }, cuadro);
      const datos = await geometria(page, paso);
      comprobarGeometriaMovil(datos, `${nombre} · ${motor} · ${tema} · ${escenario}`);
      const acciones = ['Cerrar ayuda', paso === 5 ? 'Finalizar' : 'Siguiente'];
      if (paso > 0) acciones.push('Anterior');
      assert.deepEqual(datos.controles.map(c => c.accion).sort(), acciones.sort());
      muestras.push({ motor, tema, escenario, paso: paso + 1, ...datos });
      return datos;
    }

    await navegar(page, uri);
    assert.equal(await page.locator('html').getAttribute('data-theme'), tema);
    await abrir(page, lanzar);
    for (let paso = 0; paso < 6; paso++) {
      const datos = await medir(paso, 'recorrido');
      assert.equal(datos.cantidad, 6);
      if (paso < 5) await page.locator(siguiente).tap();
    }
    const guardar = await medir(5, 'guardar');
    assert.equal(guardar.titulo, 'Guardar Configuración');

    await page.locator('.introjs-prevbutton').tap();
    await medir(4, 'anterior');
    await page.locator(siguiente).tap();
    const previo = await medir(5, 'regreso');
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
    await page.waitForFunction(y => window.scrollY !== y, previo.desplY);
    const desplazado = await medir(5, 'página desplazada');
    assert(Math.abs(desplazado.panel.top - previo.panel.top) <= 1);
    if (output) await page.screenshot({ path: path.join(output, `configuracion-${motor}-${tema}.png`), scale: 'css' });

    await page.setViewportSize({ width: iphone.viewport.width, height: 300 });
    await page.waitForFunction(() => visualViewport.height === 300);
    await medir(5, 'área visible reducida');
    const texto = page.locator('.introjs-tooltiptext');
    await texto.evaluate(el => { el.scrollTop = el.scrollHeight; });
    assert(await texto.evaluate(el => el.scrollTop > 0));
    await medir(5, 'texto desplazado');
    await page.setViewportSize(iphone.viewport);

    if (motor === 'chromium') {
      const cdp = await ctx.newCDPSession(page);
      await cdp.send('Emulation.setPageScaleFactor', { pageScaleFactor: 1.5 });
      await page.waitForFunction(() => visualViewport.scale === 1.5);
      const zoom = await medir(5, 'zoom 150 %');
      assert(zoom.vista.ancho < zoom.ancho);
      if (output) await page.screenshot({ path: path.join(output, `configuracion-${tema}-zoom.png`), scale: 'css' });
      await cdp.send('Emulation.setPageScaleFactor', { pageScaleFactor: 1 });
      await page.waitForFunction(() => visualViewport.scale === 1);
    }

    for (const accion of [siguiente, cerrar, 'Escape']) {
      const id = await page.evaluate(() => Object.keys(introJs.instances)[0]);
      await page.evaluate(({ accion, lanzar }) => {
        if (accion === 'Escape') document.dispatchEvent(new KeyboardEvent('keydown', { key: accion }));
        else document.querySelector(accion).click();
        document.querySelector(lanzar).click();
      }, { accion, lanzar });
      await estable(page, 0, id);
      await medir(0, `reapertura tras ${accion === siguiente ? 'Finalizar' : accion === cerrar ? 'X' : accion}`);
      for (const selector of ['.introjs-overlay', '.introjs-helperLayer', cuadro]) {
        assert.equal(await page.locator(selector).count(), 1);
      }
    }
    await page.locator(cerrar).tap();
    await comprobarCierre(page, lanzar, true);
    assert.deepEqual(errores, []);
    console.log('OK configuración móvil', motor, tema, muestras.length);
    return muestras;
  } finally { await ctx.close(); }
}

async function testBienvenida(browser) {
  const ctx = await context(browser,360,'light');
  try {
    const page = await login(ctx,'bienvenida');
    await page.locator('#modalBienvenida.show').waitFor();
    await page.locator('#modalBienvenida button').last().click();
    await estable(page,0);
    assert.equal(await page.locator('.modal-backdrop').count(),0);
    const peticiones = [];
    page.on('request', r => {
      if (r.url().endsWith('/completar-tutorial/') && r.method() === 'POST') peticiones.push(r);
    });
    const nivel = await page.evaluate(()=>Object.values(introJs.instances)[0]._introItems.length);
    for (let i=0; i<nivel-1; i++) {
      await estable(page,i);
      await page.locator(siguiente).press('Enter');
    }
    await estable(page,nivel-1);
    await page.locator(cerrar).press('Space');
    await comprobarCierre(page,abreNav,true);
    assert.equal(peticiones.length,0,'Cerrar el último paso no completa el tutorial');
    await abrir(page,abreNav);
    for(let i=0;i<nivel;i++){
      await estable(page,i);
      if(i===nivel-1){
        const post=page.waitForResponse(r=>r.url().endsWith('/completar-tutorial/') && r.request().method()==='POST');
        await page.locator(siguiente).press('Space');
        assert.equal((await post).status(),200);
      } else await page.locator(siguiente).press('Enter');
    }
    await comprobarCierre(page,abreNav,true);
    assert.equal(peticiones.length,1);
    console.log('Bienvenida, foco y finalización persistida');
  } finally {await ctx.close();}
}

async function main() {
  if (output) fs.mkdirSync(output,{recursive:true});
  const mode=process.argv[2] || 'todas';
  const motor = process.env.TUTORIAL_BROWSER || 'chromium';
  assert(motor === 'chromium' || (motor === 'webkit' && mode === 'configuracion'), 'Navegador no admitido para este modo');
  const browser = motor === 'webkit' ? await webkit.launch() : await chromium.launch({
    executablePath:process.env.CHROMIUM_BIN || '/usr/bin/chromium', args:['--no-sandbox']
  });
  try {
    const seed = await context(browser,1366,'light');
    await login(seed);
    const state=await seed.storageState();
    await seed.close();
    const nombres = process.argv.slice(3);
    const lista = nombres.length ? casos.filter(caso => nombres.includes(caso[0])) : casos;
    assert.equal(lista.length, nombres.length || casos.length, 'Nombre de recorrido desconocido o repetido');
    const samples=[];
    if (mode === 'configuracion') {
      for (const tema of ['light', 'dark']) {
        samples.push(...await configuracionMovil(browser, state, motor, tema));
      }
    } else if (mode==='base') {
      await baseOriginal(browser,state);
    } else if (mode==='diagnostico') {
      samples.push(...await lote(browser,state,320,'light',1,lista));
    } else {
      if (mode==='desktop' || mode==='todas') {
        const grupos=[...Array(4)].map((_,i)=>lista.filter((_,j)=>j%4===i));
        samples.push(...(await Promise.all(grupos.map((lista,i)=>lote(browser,state,1366,i%2?'dark':'light',5,lista)))).flat());
      }
      if (mode==='movil' || mode==='todas') {
        for(const theme of ['light','dark']) {
          samples.push(...(await Promise.all(widths.map(w=>lote(browser,state,w,theme,1,lista)))).flat());
        }
      }
      if (mode==='especial' || mode==='todas') {
        await carreras(browser,state,lista);
        await viewportCorto(browser,state);
        await testBienvenida(browser);
      }
    }
    if (output) fs.writeFileSync(path.join(output,`geometria-${mode}.json`),JSON.stringify(samples,null,2));
    console.log('Geometrías registradas',mode,samples.length);
  } finally { await browser.close(); }
}

main().catch(error => { console.error(error); process.exitCode=1; });
