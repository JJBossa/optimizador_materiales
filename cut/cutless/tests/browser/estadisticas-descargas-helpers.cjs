const assert = require('node:assert/strict');
const fs = require('node:fs');

function origenLocal(variable) {
  const url = new URL(process.env[variable]);
  assert.equal(url.protocol, 'http:');
  assert.equal(url.hostname, '127.0.0.1');
  return url.origin;
}

const origen = origenLocal('CUTLESS_TEST_ORIGIN');
const fixture = JSON.parse(fs.readFileSync(process.env.CUTLESS_TEST_FIXTURE, 'utf8'));
const cdn = 'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist';

async function contexto(browser, servidor, opciones) {
  const context = await browser.newContext({
    locale: 'es-CL', acceptDownloads: true, serviceWorkers: 'block', ...opciones,
  });
  await context.addCookies([{ name: 'sessionid', value: fixture.session, url: servidor }]);
  await context.route('**/*', async ruta => {
    const url = new URL(ruta.request().url());
    if (url.origin === servidor) {
      if (url.pathname.endsWith('/presupuestos/indicadores/')) {
        return ruta.fulfill({ json: { indicadores: {}, desde_cache: false } });
      }
      if (url.pathname.endsWith('/cutless/css/fonts.css')) {
        const response = await ruta.fetch({ maxRedirects: 0 });
        assert.ok(response.ok());
        const body = (await response.text()).replaceAll('font-display: optional', 'font-display: swap');
        return ruta.fulfill({ response, body });
      }
      return ruta.continue();
    }
    if (url.href === cdn + '/css/bootstrap.min.css') {
      return ruta.fulfill({ path: process.env.CUTLESS_TEST_BOOTSTRAP, contentType: 'text/css' });
    }
    if (url.href === cdn + '/js/bootstrap.bundle.min.js') {
      return ruta.fulfill({ path: process.env.CUTLESS_TEST_BOOTSTRAP_JS, contentType: 'application/javascript' });
    }
    return ruta.abort();
  });
  return context;
}

module.exports = { contexto, fixture, origen, origenLocal };
