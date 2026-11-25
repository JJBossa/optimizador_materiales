const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium, firefox, webkit } = require('playwright');
const { contexto, fixture, origen } = require('./estadisticas-descargas-helpers.cjs');

const motor = process.env.CUTLESS_TEST_BROWSER || 'chromium';
const evidencia = process.env.CUTLESS_TEST_EVIDENCE;
const intro = process.env.CUTLESS_TEST_INTRO_DIR;
const campana = page => page.locator('[data-alertas-boton]');
const panel = page => page.locator('#panel-alertas');
const aviso = (page, texto) => panel(page).getByRole('link').filter({ hasText: texto });

async function abrir(page, ruta = fixture.inicio) {
  assert.equal((await page.goto(origen + ruta)).status(), 200);
}

async function cuenta(page, cantidad) {
  await page.waitForFunction(total =>
    document.querySelector('[data-alertas-boton]')?.getAttribute('aria-label')?.startsWith(`Notificaciones, ${total} alerta`),
  cantidad);
  const marca = page.locator('[data-alertas-contador]');
  assert.equal(await marca.isVisible(), cantidad > 0);
  if (cantidad) assert.equal(await marca.textContent(), cantidad > 99 ? '99+' : String(cantidad));
}

async function captura(page, nombre, locator = null) {
  if (!evidencia) return;
  const opciones = { path: path.join(evidencia, nombre) };
  if (locator) await locator.screenshot(opciones);
  else await page.screenshot(opciones);
}

async function pulsarFiltro(page, nombre) {
  const filtro = panel(page).getByRole('button', { name: nombre, exact: true });
  await filtro.press('Enter');
  assert.equal(await filtro.getAttribute('aria-pressed'), 'true');
}

async function seguirAviso(page, texto) {
  const enlace = aviso(page, texto);
  const destino = new URL(await enlace.getAttribute('href'), origen).href;
  await enlace.press('Enter');
  await page.waitForURL(destino);
}

async function guardar(page, nombre) {
  const boton = page.getByRole('button', { name: nombre, exact: true });
  const destino = await boton.evaluate(e => e.form.action);
  const [respuesta] = await Promise.all([
    page.waitForResponse(r => r.request().method() === 'POST' && r.url() === destino),
    boton.press('Enter'),
  ]);
  assert.equal(respuesta.status(), 302);
  await page.waitForURL(new URL(respuesta.headers().location, destino).href);
}

async function resolver(page) {
  await pulsarFiltro(page, 'Todas');
  await seguirAviso(page, fixture.nombres.inicio);
  await page.locator('summary').filter({ hasText: 'Iniciar proyecto' }).press('Enter');
  await guardar(page, 'Confirmar inicio');
  await cuenta(page, 6);

  await campana(page).press('Enter');
  await seguirAviso(page, fixture.nombres.atrasado);
  await page.getByRole('link', { name: 'Editar Proyecto', exact: true }).press('Enter');
  await page.locator('#id_fecha_fin').fill(fixture.futura);
  await guardar(page, 'Guardar cambios');
  await cuenta(page, 5);

  await campana(page).press('Enter');
  await seguirAviso(page, fixture.nombres.finaliza);
  await page.locator('summary').filter({ hasText: 'Completar proyecto' }).press('Enter');
  await guardar(page, 'Confirmar finalización');
  await cuenta(page, 4);

  await campana(page).press('Enter');
  await seguirAviso(page, 'PRE-ENVIO');
  await page.getByRole('link', { name: 'Registrar estado' }).press('Enter');
  await guardar(page, 'Registrar envío');
  await cuenta(page, 3);

  await campana(page).press('Enter');
  await seguirAviso(page, 'PRE-VENCIDO');
  await cuenta(page, 3);
  assert.ok(await page.locator('[data-presupuesto-estado="vencido"]').isVisible());
}

async function errorConcurrenciaYSesion(page) {
  let modo = 'error';
  let esperando;
  let liberar;
  await page.route(/\/api\/alertas\//, async ruta => {
    const query = new URL(ruta.request().url()).searchParams;
    if (query.has('resumen')) return ruta.continue();
    if (modo === 'error') return ruta.fulfill({ status: 500 });
    if (modo === 'invalido') return ruta.fulfill({ json: { total: 5, alertas: ['inválida'] } });
    if (modo === 'sesion') return ruta.fulfill({ status: 401, json: {} });
    if (modo === 'concurrente' && query.get('categoria') === 'presupuestos') {
      const demora = new Promise(resolve => { liberar = resolve; });
      esperando();
      await demora;
      try { await ruta.continue(); } catch (_) { /* El navegador pudo cancelar el GET. */ }
      return;
    }
    return ruta.continue();
  });
  await abrir(page);
  await cuenta(page, 7);
  await campana(page).press('Enter');
  const fallo = panel(page).getByText('No se pudieron cargar las alertas. Intenta nuevamente.');
  await fallo.waitFor();
  const reintentar = panel(page).getByRole('button', { name: 'Reintentar' });
  modo = 'invalido';
  await reintentar.press('Enter');
  await fallo.waitFor();
  modo = 'normal';
  await reintentar.press('Enter');
  await aviso(page, fixture.nombres.atrasado).waitFor();

  modo = 'concurrente';
  const enVuelo = new Promise(resolve => { esperando = resolve; });
  await pulsarFiltro(page, 'Presupuestos');
  await enVuelo;
  await panel(page).getByText('Cargando alertas…').waitFor();
  await pulsarFiltro(page, 'Proyectos');
  await aviso(page, fixture.nombres.atrasado).waitFor();
  liberar();
  assert.equal(await aviso(page, 'PRE-VENCIDO').count(), 0);
  assert.equal(await panel(page).locator('.alertas-item').count(), 4);

  modo = 'sesion';
  await campana(page).press('Escape');
  await campana(page).press('Enter');
  await panel(page).getByText('Tu sesión expiró. Vuelve a iniciar sesión.').waitFor();
  assert.equal(await panel(page).locator('.alertas-item').count(), 0);
  assert.equal(await campana(page).getAttribute('aria-label'), 'Notificaciones');
  assert.ok(await panel(page).getByRole('link', { name: 'Iniciar sesión' }).isVisible());
}

async function comprobarCaja(page, ancho) {
  const medidas = await panel(page).evaluate(caja => {
    const panel = caja.getBoundingClientRect();
    const marca = document.querySelector('.navbar-brand').getBoundingClientRect();
    const boton = document.querySelector('[data-alertas-boton]').getBoundingClientRect();
    return { izquierda: panel.left, derecha: panel.right, abajo: panel.bottom, alto: innerHeight,
      finMarca: marca.right, inicioBoton: boton.left, extra: document.documentElement.scrollWidth - innerWidth };
  });
  assert.ok(medidas.izquierda >= 0 && medidas.derecha <= ancho + 1 && medidas.abajo <= medidas.alto &&
    medidas.finMarca <= medidas.inicioBoton && medidas.extra <= 1, JSON.stringify(medidas));
}

async function comprobarNavegacionEscritorio(page) {
  const gestion = page.locator('#nav-gestion');
  const proyectos = page.getByRole('link', { name: 'Proyectos', exact: true });
  await gestion.click();
  assert.equal(await campana(page).getAttribute('aria-expanded'), 'false');
  await proyectos.waitFor();
  assert.ok(await campana(page).isVisible());
  await gestion.click();
  await proyectos.waitFor({ state: 'hidden' });
  await page.locator('#nav-cuenta').click();
  await page.getByRole('link', { name: 'Mi perfil' }).waitFor();
  await page.locator('#nav-cuenta').click();

  await campana(page).press('Enter');
  await aviso(page, 'PRE-VENCIDO').waitFor();
  const ayuda = page.getByRole('button', { name: 'Ayuda', exact: true });
  await ayuda.press('Enter');
  const tutorial = page.getByRole('dialog', { name: '¡Bienvenido a CutLess!' });
  await tutorial.waitFor();
  assert.equal(await campana(page).getAttribute('aria-expanded'), 'false');
  await page.keyboard.press('Escape');
  await tutorial.waitFor({ state: 'hidden' });
  await page.waitForFunction(() => document.activeElement?.id === 'btn-tutorial');
  await campana(page).press('Enter');
  await aviso(page, 'PRE-VENCIDO').waitFor();
}

async function verAncho(browser, ancho, esquema, tema) {
  const context = await contexto(browser, origen, {
    viewport: { width: ancho, height: 900 }, colorScheme: esquema, timezoneId: 'Pacific/Kiritimati',
    reducedMotion: 'reduce',
  });
  try {
    if (ancho === 1440) {
      await context.route('https://cdn.jsdelivr.net/npm/intro.js@7.2.0/minified/*', ruta =>
        ruta.fulfill({ path: path.join(intro, path.basename(new URL(ruta.request().url()).pathname)) }));
    }
    await context.addCookies([{ name: 'sessionid', value: fixture.sesiones[ancho], url: origen }]);
    const page = await context.newPage();
    if (ancho === 768) {
      await errorConcurrenciaYSesion(page);
      // Otra carga vuelve a autenticar el panel ante el error simulado.
      const visual = await context.newPage();
      await abrir(visual);
      await cuenta(visual, 7);
      await campana(visual).press('Enter');
      await aviso(visual, 'PRE-PROXIMO').waitFor();
      await comprobarCaja(visual, ancho);
      assert.equal(await visual.locator('html').getAttribute('data-theme'), tema);
      console.log(`${motor} · ${ancho} px · error, reintento, respuestas concurrentes y sesión aprobados`);
      return;
    }

    await abrir(page);
    const cantidad = ancho === 320 ? 112 : 7;
    await cuenta(page, cantidad);
    assert.equal(await page.locator('html').getAttribute('data-theme'), tema);
    if (ancho === 1440) await captura(page, 'noti01-campana-cerrada.png', page.locator('.app-header-row'));
    await campana(page).press(ancho === 320 ? 'Space' : 'Enter');
    assert.equal(await campana(page).getAttribute('aria-expanded'), 'true');
    await aviso(page, 'PRE-VENCIDO').waitFor();
    await comprobarCaja(page, ancho);
    assert.equal(await panel(page).locator('img').count(), 0);
    assert.equal(await aviso(page, 'Proyecto ajeno sintético').count(), 0);
    assert.equal(await aviso(page, 'PRE-ACEPTADO').count(), 0);
    if (ancho === 390) await captura(page, 'noti01-panel-movil-claro.png');
    if (ancho === 1440) await captura(page, 'noti01-panel-escritorio-oscuro.png');

    await campana(page).press('Tab');
    assert.equal(await panel(page).getByRole('button', { name: 'Cerrar notificaciones' }).evaluate(e => e === document.activeElement), true);
    await page.keyboard.press('Escape');
    assert.equal(await campana(page).evaluate(e => e === document.activeElement), true);
    assert.equal(await campana(page).getAttribute('aria-expanded'), 'false');
    await campana(page).press('Enter');
    await aviso(page, 'PRE-VENCIDO').waitFor();
    if (ancho === 320) {
      assert.equal(await panel(page).locator('.alertas-item').count(), 10);
      assert.ok(await panel(page).evaluate(e => e.scrollHeight > e.clientHeight));
      await panel(page).getByRole('button', { name: 'Ver más' }).press('Enter');
      await page.waitForFunction(() => document.querySelectorAll('#panel-alertas .alertas-item').length === 20);
      await cuenta(page, cantidad);
      await page.getByRole('button', { name: 'Abrir navegación' }).click();
      assert.equal(await campana(page).getAttribute('aria-expanded'), 'false');
      assert.ok(await campana(page).isVisible());
      await page.waitForFunction(() => document.querySelector('#navbarNav').classList.contains('show'));
      await page.keyboard.press('Escape');
    }
    if (ancho === 1440) await comprobarNavegacionEscritorio(page);
    if (ancho === 390 || ancho === 1440) {
      await pulsarFiltro(page, 'Presupuestos');
      await aviso(page, 'PRE-ENVIO').waitFor();
      assert.equal(await aviso(page, fixture.nombres.inicio).count(), 0);
      if (ancho === 1440) await captura(page, 'noti01-filtro-presupuestos.png');
      await pulsarFiltro(page, 'Proyectos');
      await aviso(page, '<img src=x> «Taller Ñ»').waitFor();
      assert.equal(await aviso(page, 'PRE-VENCIDO').count(), 0);
      if (ancho === 390) {
        await captura(page, 'noti01-filtro-proyectos.png');
        await resolver(page);
      }
    }
    console.log(`${motor} · ${ancho} px · tema ${tema} · navegación y alertas aprobadas`);
  } finally {
    await context.close();
  }
}

async function estadosEspeciales(browser) {
  for (const [clave, js] of [['vacio', true], ['silencio', true], ['390', false]]) {
    const context = await contexto(browser, origen, {
      viewport: { width: 390, height: 900 }, javaScriptEnabled: js, reducedMotion: 'reduce',
    });
    try {
      await context.addCookies([{ name: 'sessionid', value: fixture.sesiones[clave], url: origen }]);
      const page = await context.newPage();
      let peticiones = 0;
      page.on('request', r => { if (new URL(r.url()).pathname === fixture.api) peticiones++; });
      await abrir(page);
      if (clave === 'vacio') {
        await cuenta(page, 0);
        await campana(page).press('Enter');
        await panel(page).getByText('No tienes alertas pendientes.').waitFor();
        await captura(page, 'noti01-estado-vacio.png');
      } else if (clave === 'silencio') {
        assert.equal(await campana(page).count(), 0);
        assert.equal(peticiones, 0);
      } else {
        await page.getByRole('link', { name: 'Notificaciones', exact: true }).press('Enter');
        await page.waitForURL(origen + fixture.centro);
        assert.ok(await page.getByRole('heading', { name: 'Notificaciones' }).isVisible());
        await page.getByRole('navigation', { name: 'Filtrar alertas' }).getByRole('link', { name: 'Presupuestos' }).press('Enter');
        await page.waitForURL(url => url.searchParams.get('categoria') === 'presupuestos');
        assert.ok(await page.getByRole('link').filter({ hasText: 'PRE-PROXIMO' }).isVisible());
        assert.equal(peticiones, 0);
      }
    } finally {
      await context.close();
    }
  }
}

async function main() {
  assert.ok(intro, 'Indica CUTLESS_TEST_INTRO_DIR con los archivos minificados locales de Intro.js 7.2.0.');
  const browser = await { chromium, firefox, webkit }[motor].launch(motor === 'chromium' ? {
    executablePath: process.env.CUTLESS_TEST_CHROMIUM || undefined,
  } : {});
  try {
    for (const [ancho, esquema, tema] of [[320, 'dark', 'dark'], [390, 'light', 'light'],
      [768, 'light', 'light'], [1440, 'light', 'dark']]) await verAncho(browser, ancho, esquema, tema);
    await estadosEspeciales(browser);
    console.log('Estado vacío, avisos deshabilitados y centro sin JavaScript aprobados');
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
