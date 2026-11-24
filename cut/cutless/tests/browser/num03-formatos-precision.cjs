/* Requires a Django loopback server with synthetic NUM-03 fixtures. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const fixture = JSON.parse(fs.readFileSync(path.join(process.env.NUM03_TEMPORAL, 'servidor.json')));
assert.match(fixture.origen, /^http:\/\/127\.0\.0\.1:\d+$/);

async function submit(page, form, destino, expected) {
  const match = req => req.method() === 'POST' && req.url() === destino;
  const click = () => form.locator('button[type="submit"]').last().press('Enter');
  if (expected === null) {
    const request = page.waitForRequest(match, { timeout: 650 });
    await click();
    await assert.rejects(request, {name: 'TimeoutError'});
    return null;
  }
  const [response] = await Promise.all([
    page.waitForResponse(res => match(res.request()), {timeout: 10000}), click(),
  ]);
  assert.equal(response.status(), expected);
  const values = new URLSearchParams(response.request().postData());
  values.delete('csrfmiddlewaretoken');
  return Object.fromEntries(values);
}

async function run(page, js, id) {
  const modo = js ? 'JS' : 'HTML';
  const nombre = `Browser ${id} ${modo}`;
  const plantilla = ['P1','P2','P3','P4','P5'].includes(id);
  const ruta = id === 'P4' ? 'editar_plantilla' : id === 'O4' ? 'duplicar'
    : plantilla ? 'plantilla' : 'opt';
  const url = fixture.origen + fixture.rutas[ruta];
  const response = await page.goto(url, {waitUntil:'domcontentloaded'});
  assert.equal(response.status(), 200);
  const form = page.locator(plantilla ? 'form:has([name="ancho_tablero"])' : '#optimizacion-form');
  const get = field => form.locator(`[name="${field}"]`);
  const fill = async values => {
    for (const [field, value] of Object.entries(values)) await get(field).fill(value);
  };
  const teclear = async (field, valor) => {
    await get(field).fill('');
    await get(field).pressSequentially(valor);
    assert.equal(await get(field).inputValue(), valor);
  };

  if (id === 'P4') {
    assert.equal(await get('ancho_tablero').inputValue(), '122.1234567');
    await fill({descripcion:nombre});
    return {post:await submit(page,form,url,302)};
  }
  if (id === 'O4') {
    assert.equal(await get('margen_corte').inputValue(), '2.15');
    await fill({nombre_optimizacion:nombre});
    const post = await submit(page,form,fixture.origen + fixture.rutas.opt,302);
    assert.equal(post.margen_corte, '2.15');
    assert.ok(post.origen_medidas);
    delete post.origen_medidas;
    return {post};
  }

  if (plantilla) {
    const unidad = id === 'P2' ? 'mm' : id === 'P3' ? 'm' : 'cm';
    await get('unidad_medida').selectOption(unidad);
    await fill({nombre, ancho_tablero:unidad==='mm'?'1220':unidad==='m'?'1.22125':'122',
      alto_tablero:unidad==='mm'?'2440':unidad==='m'?'2.44':'244', margen_corte:'3'});
    if (id === 'P1') {
      await teclear('ancho_tablero','12,5');
      await teclear('margen_corte','2,15');
    }
    const pieza = id === 'P2' ? ['Puerta, "Norte" Ω\nNivel 2','400','500']
      : id === 'P3' ? ['Pieza','.2','.3'] : ['Pieza',js?'2,5':'2.5','5'];
    if (js) {
      const editor = form.locator('.template-piece-editor fieldset');
      await editor.locator('textarea').fill(pieza[0]);
      const ancho = editor.locator('input').nth(0);
      await ancho.fill('');
      await ancho.pressSequentially(pieza[1]);
      assert.equal(await ancho.inputValue(), pieza[1]);
      await editor.locator('input').nth(1).fill(pieza[2]);
    } else {
      const [nom, ancho, alto] = pieza;
      await get('piezas').fill('"' + nom.replaceAll('"','""') + `",${ancho},${alto},1`);
    }
    if (id==='P5') {
      await teclear('ancho_tablero','1.000');
      assert.equal(await get('ancho_tablero').evaluate(e => e.validity.patternMismatch),true);
      return {post:await submit(page,form,url,null)};
    }
    const post = await submit(page,form,url,302);
    if (id==='P1') {
      assert.equal(post.ancho_tablero,'12,5');
      assert.equal(post.margen_corte,'2,15');
      assert.match(post.piezas, /,2\.5,5,1$/);
    }
    return {post};
  }

  await fill({nombre_optimizacion:nombre, ancho:'122', alto:'244', margen_corte:'3',
    precio_tablero:'12.50', mano_obra:'15.75', 'form-0-nombre':'Pieza de prueba',
    'form-0-ancho':'4', 'form-0-alto':'8', 'form-0-cantidad':'1'});
  if (id === 'O1') {
    await teclear('ancho','12,5');
    await teclear('form-0-ancho','2,5');
    await teclear('precio_tablero','12,5');
    await teclear('margen_corte','0,5');
    const post = await submit(page,form,url,302);
    assert.equal(post.ancho,'12,5');
    assert.equal(post['form-0-ancho'],'2,5');
    assert.equal(post.precio_tablero,'12,5');
    assert.equal(post.margen_corte,'0,5');
    return {post};
  }
  if (id === 'O3') {
    await teclear('form-0-cantidad','1.000');
    assert.equal(await get('form-0-cantidad').evaluate(e => e.validity.patternMismatch),true);
    return {post:await submit(page,form,url,null)};
  }
  if (id === 'O5') await fill({precio_tablero:'37,25'});
  for (const [field,value] of Object.entries(fixture.ids)) await get(field).selectOption(String(value));
  if (id === 'O5') {
    assert.equal(await get('precio_tablero').inputValue(), '37,25');
    assert.equal(await get('ancho').inputValue(), '122');
    assert.equal(await get('alto').inputValue(), '244');
    return {precio:'37,25', ancho:'122', alto:'244'};
  }
  await get('permitir_rotacion').check();
  await fill({ancho:'132.1250',alto:'242.25',precio_tablero:'37,25',margen_corte:'2.15',
    'form-0-ancho':'200','form-0-alto':'240'});
  const rechazado = await submit(page,form,url,200);
  await page.waitForLoadState('domcontentloaded');
  // Los temporizadores del fallo auditado se ejecutaban 500 ms después de la carga.
  if (js) await page.waitForTimeout(650);
  const claves = ['ancho','alto','precio_tablero','margen_corte','mano_obra','material','cliente','proyecto'];
  const repuesto = {};
  for (const campo of claves) {
    repuesto[campo] = await get(campo).inputValue();
    assert.equal(repuesto[campo], rechazado[campo]);
  }
  assert.equal(await get('permitir_rotacion').isChecked(),true);
  await fill({'form-0-ancho':'20','form-0-alto':'30'});
  const post = await submit(page,form,url,302);
  for (const campo of claves) assert.equal(post[campo], rechazado[campo]);
  return {rechazado, repuesto, post};
}

(async () => {
  const browser = await chromium.launch({
    executablePath: process.env.CHROMIUM_BIN || '/usr/bin/chromium',args:['--lang=es-CL'],
  });
  let aprobadas = 0;
  let fallidas = 0;
  try {
    console.error('Chromium', browser.version());
    for (const js of [true,false]) {
      const context = await browser.newContext({locale:'es-CL',javaScriptEnabled:js,serviceWorkers:'block'});
      await context.addCookies([{name:'sessionid',value:fixture.cookie,url:fixture.origen}]);
      await context.route('**/*',route => new URL(route.request().url()).origin === fixture.origen
        ? route.continue() : route.abort());
      const page = await context.newPage();
      page.setDefaultTimeout(6500);
      for (const id of ['P1','P2','P3','P4','P5','O1','O2','O3','O4','O5']) {
        try {
          const datos = await run(page,js,id);
          console.log(JSON.stringify({id,js,...datos}));
          aprobadas++;
        } catch (error) {
          console.error(JSON.stringify({id,js,error:error.message}));
          fallidas++;
        }
      }
      await context.close();
    }
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify({aprobadas,fallidas,omitidas:0}));
  process.exitCode = Number(fallidas > 0);
})().catch(error => {console.error(error.message); process.exitCode = 1;});
