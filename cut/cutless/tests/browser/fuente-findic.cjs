const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright');

const local = new URL(process.env.CUTLESS_TEST_ORIGIN);
assert.equal(local.protocol, 'http:');
assert.equal(local.hostname, '127.0.0.1');
const fixture = JSON.parse(fs.readFileSync(process.env.CUTLESS_TEST_FIXTURE, 'utf8'));
const findic = 'https://findic.cl/';

(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CUTLESS_TEST_CHROMIUM || undefined });
  try {
    const context = await browser.newContext({ serviceWorkers: 'block' });
    await context.addCookies([{ name: 'sessionid', value: fixture.session, url: local.origin }]);
    await context.route('**/*', route => {
      const url = new URL(route.request().url());
      if (url.href === findic) return route.fulfill({ contentType: 'text/html', body: '<title>Findic simulado</title>' });
      if (url.origin === local.origin) {
        if (url.pathname.endsWith('/presupuestos/indicadores/')) {
          return route.fulfill({ json: { indicadores: {}, desde_cache: false } });
        }
        return route.continue();
      }
      if (url.href === 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css') {
        return route.fulfill({ path: process.env.CUTLESS_TEST_BOOTSTRAP, contentType: 'text/css' });
      }
      return route.abort();
    });
    const page = await context.newPage();
    for (const vista of ['presupuestos', 'presupuesto']) {
      const origen = local.origin + fixture.rutas[vista];
      assert.equal((await page.goto(origen)).status(), 200);
      const fuente = page.getByRole('link', { name: 'Fuente: Findic.cl (se abre en una pestaña nueva)' });
      const [popup] = await Promise.all([page.waitForEvent('popup'), fuente.press('Enter')]);
      await popup.waitForLoadState();
      assert.equal(popup.url(), findic);
      assert.equal(await popup.title(), 'Findic simulado');
      assert.ok(await popup.evaluate(() => window.opener === null && document.referrer === ''));
      assert.equal(page.url(), origen);
      assert.equal(page.isClosed(), false);
      console.log(`Aprobado ${vista}: Findic se abre en otra pestaña y CutLess permanece abierto.`);
      await popup.close();
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
