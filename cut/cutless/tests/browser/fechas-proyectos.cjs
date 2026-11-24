const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium, webkit, devices } = require('playwright');

const origen = new URL(process.env.CUTLESS_TEST_ORIGIN);
assert.equal(origen.protocol, 'http:');
assert.equal(origen.hostname, '127.0.0.1');
const fixture = JSON.parse(fs.readFileSync(process.env.CUTLESS_TEST_FIXTURE, 'utf8'));
const estilos = process.env.CUTLESS_TEST_BOOTSTRAP;
const scripts = process.env.CUTLESS_TEST_BOOTSTRAP_JS;
assert.ok(fs.existsSync(estilos) && fs.existsSync(scripts), 'Se requiere Bootstrap 5.3.0 local.');
const cdn = 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist';

async function enviar(page, campo, usarValidacion = true) {
  const destino = page.url();
  const [post] = await Promise.all([
    page.waitForResponse(r => r.url() === destino && r.request().method() === 'POST'),
    page.waitForNavigation({ waitUntil: 'domcontentloaded' }),
    campo.evaluate((input, validar) => {
      input.form.noValidate = !validar;
      input.form.requestSubmit();
    }, usarValidacion),
  ]);
  return post.status();
}

async function comprobar(page, caso) {
  await page.goto(fixture.alta);
  const inicio = page.locator('#id_fecha_inicio');
  const fin = page.locator('#id_fecha_fin');
  for (const campo of [inicio, fin]) {
    assert.equal(await campo.getAttribute('type'), 'date');
    assert.equal(await campo.getAttribute('min'), fixture.hoy);
    assert.equal(await campo.inputValue(), '');
    assert.ok(await campo.evaluate(e => {
      const caja = e.getBoundingClientRect();
      return caja.left >= 0 && caja.right <= document.documentElement.clientWidth + 1;
    }));
  }
  await page.locator('#id_nombre').fill('Proyecto de navegador');
  await inicio.fill(fixture.manana);
  await fin.fill(fixture.ayer);
  assert.ok(await fin.evaluate(e => e.validity.rangeUnderflow));
  assert.equal(await enviar(page, fin, false), 200);
  assert.match(await page.locator('#id_fecha_fin_error').textContent(), /fecha de finalización no puede ser anterior a hoy/i);
  assert.equal(await fin.getAttribute('aria-invalid'), 'true');
  assert.match(await fin.getAttribute('aria-describedby'), /\bid_fecha_fin_error\b/);
  assert.equal(await inicio.inputValue(), fixture.manana);
  assert.equal(await fin.inputValue(), fixture.ayer);

  await fin.fill(fixture.hoy);
  assert.equal(await enviar(page, fin), 200);
  assert.match(await page.locator('#id_fecha_fin_error').textContent(), /finalización no puede ser anterior al inicio/i);
  await inicio.fill(fixture.hoy);
  assert.equal(await enviar(page, inicio), 302);
  assert.match(page.url(), /\/cutless\/proyectos\/\d+\/$/);

  await page.goto(fixture.edicion);
  assert.equal(await inicio.getAttribute('min'), null);
  assert.equal(await fin.getAttribute('min'), null);
  assert.equal(await inicio.inputValue(), fixture.inicio);
  assert.equal(await fin.inputValue(), fixture.ayer);
  await page.locator('#id_descripcion').fill(caso);
  assert.equal(await enviar(page, inicio), 302);
  assert.equal(page.url(), new URL(fixture.detalle, origen).href);
  await page.goto(fixture.edicion);
  assert.equal(await page.locator('#id_descripcion').inputValue(), caso);
  assert.equal(await inicio.inputValue(), fixture.inicio);
  assert.equal(await fin.inputValue(), fixture.ayer);

  await inicio.fill('');
  await fin.fill(fixture.inicio);
  assert.equal(await enviar(page, inicio), 200);
  assert.equal(await inicio.inputValue(), '');
  assert.equal(await fin.inputValue(), fixture.inicio);
  assert.match(await page.locator('#id_fecha_fin_error').textContent(), /anterior a hoy/i);
  console.log(caso);
}

(async () => {
  const motor = process.env.CUTLESS_TEST_ENGINE || 'chromium';
  assert.ok(['chromium', 'webkit'].includes(motor));
  const browser = motor === 'webkit' ? await webkit.launch()
    : await chromium.launch({ executablePath: process.env.CUTLESS_TEST_CHROMIUM });
  try {
    const perfiles = motor === 'webkit' ? [devices['iPhone 13']] : [320, 390, 1280].map(
      width => ({ viewport: { width, height: 900 }, isMobile: width <= 390, hasTouch: width <= 390 }),
    );
    for (const perfil of perfiles) {
      for (const javaScriptEnabled of [true, false]) {
        const context = await browser.newContext({
          ...perfil, baseURL: origen.origin, javaScriptEnabled, locale: 'es-CL',
          timezoneId: 'Pacific/Kiritimati', reducedMotion: 'reduce', serviceWorkers: 'block',
        });
        try {
          await context.addCookies([{ name: 'sessionid', value: fixture.sesion, url: origen.origin }]);
          await context.route('**/*', route => {
            const url = route.request().url();
            if (url.startsWith(origen.origin + '/')) return route.continue();
            if (url === cdn + '/css/bootstrap.min.css') return route.fulfill({ path: estilos, contentType: 'text/css' });
            if (url === cdn + '/js/bootstrap.bundle.min.js') return route.fulfill({ path: scripts, contentType: 'application/javascript' });
            return route.abort();
          });
          await comprobar(await context.newPage(),
            `VAL-02 · ${motor} · ${perfil.viewport.width} px · ${javaScriptEnabled ? 'con' : 'sin'} JavaScript`);
        } finally {
          await context.close();
        }
      }
    }
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
