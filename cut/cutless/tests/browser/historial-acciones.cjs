const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require('playwright');
const { contexto, fixture, origen, origenLocal } = require('./estadisticas-descargas-helpers.cjs');

const base = process.env.CUTLESS_TEST_BASE && origenLocal('CUTLESS_TEST_BASE');
const evidencia = process.env.CUTLESS_TEST_EVIDENCE;
const tarjeta = '.optimizacion-card';
const menu = '.management-action-menu';
const acciones = '.btn[data-icon]:is([data-icon="eye"], [data-icon="edit"], [data-icon="copy"], [data-icon="more"])';
const etiquetas = ['Ver resultado', 'Editar', 'Duplicar', 'Más opciones'];
const opciones = ['Cambiar nombre', 'Estimar tiempo de corte', 'Descargar PNG', 'Descargar PDF',
  'Descargar Excel', 'Imprimir (otra pestaña)', 'Eliminar'];

async function abrir(page, servidor, tema) {
  const url = servidor + fixture.rutas.historial;
  assert.equal((await page.goto(url)).status(), 200);
  assert.equal(page.url(), url);
  assert.equal(await page.locator('html').getAttribute('data-theme'), tema);
  await page.evaluate(() => document.fonts.ready);
}

async function medir(page) {
  return page.locator(tarjeta).evaluateAll((tarjetas, selector) => tarjetas.map(tarjeta => {
    const caja = tarjeta.querySelector('.card-body');
    const interior = caja.getBoundingClientRect();
    const ancho = interior.width - parseFloat(getComputedStyle(caja).paddingInlineStart)
      - parseFloat(getComputedStyle(caja).paddingInlineEnd);
    return { ancho, botones: Array.from(tarjeta.querySelectorAll(selector)).map(boton => {
      const { left: x, top: y, width, height, right, bottom } = boton.getBoundingClientRect();
      const css = getComputedStyle(boton);
      const rango = document.createRange();
      rango.selectNodeContents(boton);
      const contenido = rango.getBoundingClientRect();
      const icono = boton.querySelector('.button-icon');
      return {
        nombre: boton.textContent.trim(), x, y, width, height, right, bottom,
        cabe: contenido.left >= x - 1 && contenido.right <= right + 1
          && contenido.top >= y - 1 && contenido.bottom <= bottom + 1,
        alineacion: [css.alignItems, css.justifyContent], padding: css.padding,
        identidad: [boton.getAttribute('href'), boton.dataset.action, boton.dataset.icon,
          icono.innerHTML, icono.getAttribute('aria-hidden'),
          css.color, css.backgroundColor, css.borderColor, css.borderRadius,
          css.fontFamily, css.fontSize, css.fontWeight, css.lineHeight],
      };
    }) };
  }), acciones);
}

function cerca(actual, esperado) {
  assert.ok(Math.abs(actual - esperado) <= 1, `${actual} ≉ ${esperado}`);
}

function validar(tarjetas, ancho, js) {
  assert.ok(tarjetas.length > 1);
  for (const tarjeta of tarjetas) {
    const [resultado, editar, duplicar, mas] = tarjeta.botones;
    const visibles = js ? tarjeta.botones : tarjeta.botones.slice(0, 3);
    assert.deepEqual(tarjeta.botones.map(boton => boton.nombre), etiquetas);
    for (const boton of visibles) {
      assert.ok(boton.cabe && boton.height >= 44, JSON.stringify(boton));
      assert.deepEqual(boton.alineacion, ['center', 'center']);
    }
    assert.equal(editar.padding, duplicar.padding);
    cerca(resultado.width, tarjeta.ancho);
    cerca(editar.x, resultado.x);
    cerca(editar.y - resultado.bottom, 12);
    cerca(editar.width, duplicar.width);
    if (ancho < 300) {
      cerca(editar.width, resultado.width);
      cerca(duplicar.x, editar.x);
      cerca(duplicar.y - editar.bottom, 12);
    } else {
      cerca(editar.y, duplicar.y);
      cerca(editar.height, duplicar.height);
      cerca(duplicar.x - editar.right, 12);
    }
    if (!js) {
      assert.equal(mas.height, 0);
    } else if (ancho >= 768) {
      assert.equal(editar.padding, mas.padding);
      cerca(mas.height, editar.height);
      cerca(mas.width, editar.width);
      cerca(mas.y, editar.y);
      cerca(mas.x - duplicar.right, 12);
      cerca(mas.right, resultado.right);
    } else {
      cerca(mas.y - duplicar.bottom, 12);
      cerca(mas.x, resultado.x);
      cerca(mas.width, resultado.width);
    }
  }
}

async function enlaces(page) {
  return page.locator(`${tarjeta} ${menu} a`).evaluateAll(links => links.map(a => [
    a.textContent.trim().replace(/\s+/g, ' '), a.getAttribute('href'), a.dataset.descarga, a.target,
  ]));
}

async function sinDesbordamiento(page) {
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1));
}

async function enfocado(locator, visible = false) {
  assert.ok(await locator.evaluate((elemento, visible) => elemento === document.activeElement
    && (!visible || (elemento.matches(':focus-visible') && getComputedStyle(elemento).outlineStyle !== 'none')), visible));
}

async function probarMenu(page, js, captura) {
  const primera = page.locator(tarjeta).first();
  const [resultado, editar, duplicar] = await primera.locator(acciones).all();
  const toggle = primera.locator(`${menu} button`);
  const lista = primera.locator(`${menu} .dropdown-menu`);
  assert.deepEqual((await lista.locator('a').allTextContents()).map(texto => texto.trim().replace(/\s+/g, ' ')), opciones);
  await resultado.focus();
  for (const boton of [editar, duplicar]) {
    await page.keyboard.press('Tab');
    await enfocado(boton, true);
  }
  await page.keyboard.press('Tab');
  if (js) {
    await enfocado(toggle, true);
    await page.keyboard.press('Enter');
    assert.equal(await toggle.getAttribute('aria-expanded'), 'true');
    await page.keyboard.press('ArrowDown');
  } else {
    assert.ok(await toggle.isHidden());
  }
  await enfocado(lista.locator('a').first());
  await lista.scrollIntoViewIfNeeded();
  const alcanzables = await lista.locator('a').evaluateAll(links => links.every(a => {
    const { x, y, width, height } = a.getBoundingClientRect();
    return document.elementFromPoint(x + width / 2, y + height / 2)?.closest('a') === a;
  }));
  assert.ok(alcanzables, 'Se puede pulsar cada enlace del menú sin recortes.');
  await sinDesbordamiento(page);
  if (captura && evidencia) await page.screenshot({ path: path.join(evidencia, captura) });
  if (js) {
    await page.keyboard.press('Escape');
    assert.equal(await toggle.getAttribute('aria-expanded'), 'false');
    await enfocado(toggle);
    await lista.waitFor({ state: 'hidden' });
  }
}

async function capturaTarjeta(page, nombre) {
  if (!evidencia) return;
  await page.locator(tarjeta).first().screenshot({ path: path.join(evidencia, nombre),
    style: '.navbar-custom, #magnifier-toggle { visibility: hidden; }' });
}

async function probarEstados(page) {
  const toggle = page.locator(tarjeta).first().locator(`${menu} button`);
  const colorInicial = await toggle.evaluate(b => getComputedStyle(b).backgroundColor);
  await toggle.hover();
  assert.notEqual(await toggle.evaluate(b => getComputedStyle(b).backgroundColor), colorInicial);
  await toggle.click();
  assert.equal(await toggle.getAttribute('aria-expanded'), 'true');
  await toggle.click();
  assert.equal(await toggle.getAttribute('aria-expanded'), 'false');
  await toggle.evaluate(b => { b.disabled = true; });
  try {
    assert.ok(await toggle.isDisabled());
    assert.equal(await toggle.evaluate(b => getComputedStyle(b).boxShadow), 'none');
  } finally {
    await toggle.evaluate(b => { b.disabled = false; });
  }
}

function medidas(tarjetas) {
  return tarjetas[0].botones.map(boton => [boton.width, boton.height].map(valor => +valor.toFixed(2)));
}

async function probar(browser, width, tema, js = true) {
  const config = { viewport: { width, height: 920 }, colorScheme: tema, javaScriptEnabled: js, reducedMotion: 'reduce' };
  const context = await contexto(browser, origen, config);
  const comparar = js && ((width === 390 && tema === 'light') || (width === 1280 && tema === 'dark'));
  const anterior = comparar && base && await contexto(browser, base, config);
  try {
    const page = await context.newPage();
    await abrir(page, origen, tema);
    const despues = await medir(page);
    validar(despues, width, js);
    await sinDesbordamiento(page);
    if (anterior) {
      const previa = await anterior.newPage();
      await abrir(previa, base, tema);
      const antes = await medir(previa);
      const identidad = tarjetas => tarjetas.map(t => t.botones.map(b => [b.nombre, b.identidad]));
      assert.deepEqual(identidad(despues), identidad(antes));
      assert.deepEqual(await enlaces(page), await enlaces(previa));
      await capturaTarjeta(previa, `historial-antes-${width}.png`);
      await capturaTarjeta(page, `historial-despues-${width}.png`);
      console.log(width, tema, 'antes', JSON.stringify(medidas(antes)));
    }
    await probarMenu(page, js, width === 390 && tema === 'light' && (js ? 'historial-menu-390.png' : 'historial-sin-js-390.png'));
    console.log(width, tema, js ? 'JavaScript' : 'sin JavaScript', JSON.stringify(medidas(despues)));
    if (js && [320, 390, 1200, 1280].includes(width)) {
      await page.addStyleTag({ content: `:root body.history-page .history-card-actions .btn {
        font-size: 18px !important; line-height: 1.5 !important;
      }` });
      validar(await medir(page), width, js);
      await sinDesbordamiento(page);
      console.log(width, tema, 'texto ampliado a 18 px');
    }
    if (js && width === 1280) await probarEstados(page);
  } finally {
    await context.close();
    if (anterior) await anterior.close();
  }
}

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CUTLESS_TEST_CHROMIUM });
  try {
    for (const width of [320, 390, 768, 1280]) {
      for (const tema of ['light', 'dark']) await probar(browser, width, tema);
    }
    for (const width of [280, 1200]) await probar(browser, width, 'light');
    for (const width of [320, 390, 1280]) await probar(browser, width, 'light', false);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
