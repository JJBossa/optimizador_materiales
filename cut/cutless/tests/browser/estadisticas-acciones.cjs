const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require('playwright');
const { contexto, fixture, origen, origenLocal } = require('./estadisticas-descargas-helpers.cjs');

const base = process.env.CUTLESS_TEST_BASE && origenLocal('CUTLESS_TEST_BASE');
const evidencia = process.env.CUTLESS_TEST_EVIDENCE;

async function visitar(context, servidor, tema) {
  await context.route('**/estadisticas/grafico-*/?*', ruta => ruta.abort());
  const page = await context.newPage();
  assert.equal((await page.goto(servidor + fixture.rutas.estadisticas)).status(), 200);
  assert.equal(await page.locator('html').getAttribute('data-theme'), tema);
  await page.evaluate(() => document.fonts.ready);
  return page;
}

function medir(enlaces) {
  return enlaces.evaluateAll(botones => botones.map(boton => {
    const caja = boton.getBoundingClientRect();
    const css = getComputedStyle(boton);
    return {
      ancho: caja.width, alto: caja.height, x: caja.left, y: caja.top,
      estilo: [css.backgroundColor, css.color, css.borderRadius, css.fontFamily, css.fontSize],
      destino: boton.getAttribute('href'), nombre: boton.textContent.trim(),
      centrado: css.alignItems === 'center' && css.justifyContent === 'center',
      iconoDecorativo: boton.querySelector('svg')?.getAttribute('aria-hidden'),
    };
  }));
}

async function verificar(browser, ancho, tema) {
  const opciones = { viewport: { width: ancho, height: 900 }, colorScheme: tema, reducedMotion: 'reduce' };
  const actual = await contexto(browser, origen, opciones);
  const captura = (ancho === 390 && tema === 'light') || (ancho === 1280 && tema === 'dark');
  const anterior = base && captura && await contexto(browser, base, opciones);
  try {
    const page = await visitar(actual, origen, tema);
    const tabla = page.locator('.table-responsive:has(.management-action-table)');
    const filas = tabla.locator('tbody tr');
    assert.equal(await filas.count(), 3);
    let x;
    for (const fila of await filas.all()) {
      const botones = await medir(fila.locator('.management-action-set .btn'));
      assert.deepEqual(botones.map(boton => boton.nombre), ['Ver resultado', 'Duplicar', 'PDF']);
      for (const [i, boton] of botones.entries()) {
        assert.ok(boton.ancho === 160 && boton.alto === 44 && boton.centrado, JSON.stringify(boton));
        assert.equal(boton.iconoDecorativo, 'true');
        if (i) {
          const previo = botones[i - 1];
          assert.ok(boton.y >= previo.y + previo.alto || boton.x >= previo.x + previo.ancho);
        }
      }
      x ??= botones.map(boton => boton.x);
      assert.deepEqual(botones.map(boton => boton.x), x);
    }
    const exportaciones = page.getByRole('group', { name: 'Descargar estadísticas' }).getByRole('link');
    assert.deepEqual((await medir(exportaciones)).map(b => [b.ancho, b.alto]), [[160, 44], [160, 44]]);
    await filas.first().locator('summary').press('Enter');
    const desborde = await tabla.evaluate(e => [
      e.scrollWidth - e.clientWidth, document.documentElement.scrollWidth - document.documentElement.clientWidth,
    ]);
    assert.deepEqual(desborde, [0, 0], JSON.stringify({ ancho, tema }));
    await filas.first().locator('summary').press('Enter');
    const primero = filas.first().getByRole('link', { name: 'Ver resultado' });
    await primero.focus();
    await page.keyboard.press('Tab');
    assert.ok(await filas.first().getByRole('link', { name: 'Duplicar' }).evaluate(elemento =>
      elemento === document.activeElement && elemento.matches(':focus-visible')
      && getComputedStyle(elemento).outlineStyle !== 'none'));

    if (anterior) {
      await page.locator(':focus').evaluate(elemento => elemento.blur());
      const previa = await visitar(anterior, base, tema);
      const tablaPrevia = previa.locator('.table-responsive:has(tbody a[data-icon="copy"])');
      const forma = botones => botones.map(({ estilo, destino }) => [estilo, destino]);
      const antes = await medir(tablaPrevia.locator('tbody tr').first().locator('a.btn'));
      const despues = await medir(filas.first().locator('a.btn'));
      assert.deepEqual(forma(antes), forma(despues));
      console.log(ancho, tema, 'antes', antes.map(b => [b.ancho, b.alto]),
        'después', despues.map(b => [b.ancho, b.alto]));
      if (evidencia) {
        const opcionesCaptura = { style: '.navbar-custom, #magnifier-toggle { visibility: hidden; }' };
        for (const [momento, tablaCaptura] of [['antes', tablaPrevia], ['despues', tabla]]) {
          const sujeto = ancho === 390 ? tablaCaptura.locator('tbody tr').first() : tablaCaptura;
          await sujeto.screenshot({ ...opcionesCaptura, path: path.join(evidencia, `estadisticas-${momento}-${ancho}.png`) });
        }
      }
    }
    console.log(`Aprobado ${ancho} px, ${tema}: tabla, exportación y teclado.`);
  } finally {
    if (anterior) await anterior.close();
    await actual.close();
  }
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CUTLESS_TEST_CHROMIUM });
  try {
    for (const ancho of [320, 390, 768, 1280]) {
      for (const tema of ['light', 'dark']) await verificar(browser, ancho, tema);
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
