// Chromium con datos sintéticos. Variables de entorno descritas en CAMBIOS_NAVEGACION_VISORES.md.
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

const origin = process.env.CUTLESS_TEST_ORIGIN || 'http://127.0.0.1:8779';
const session = process.env.CUTLESS_TEST_SESSION;
const plan = Number(process.env.CUTLESS_TEST_PLAN);
const bootstrap = process.env.CUTLESS_TEST_BOOTSTRAP;
const base = origin + '/cutless/';

async function newPage(browser) {
    const context = await browser.newContext({ ignoreHTTPSErrors: true });
    await context.addCookies([{ name: 'sessionid', value: session, url: origin }]);
    if (bootstrap) {
        await context.route('**/*', route => {
            const url = new URL(route.request().url());
            if (url.origin === origin) return route.continue();
            if (url.pathname.endsWith('/bootstrap.min.css')) return route.fulfill({ path: bootstrap + '.css', contentType: 'text/css' });
            if (url.pathname.endsWith('/bootstrap.bundle.min.js')) return route.fulfill({ path: bootstrap + '.js', contentType: 'application/javascript' });
            return route.abort();
        });
    }
    return context.newPage();
}

const traversal = { waitUntil: 'commit' };
const length = page => page.evaluate(() => history.length);
const scroll = page => page.evaluate(() => window.scrollY);
const shown = modal => modal.locator('.modal-dialog').waitFor();
const closed = modal => modal.waitFor({ state: 'hidden' });
const waitForFocus = (page, control) => control.and(page.locator(':focus')).waitFor();
const otherState = { filters: ['sin-cambios'], page: 2 };

async function preserveOtherState(page) {
    await page.evaluate(state => history.replaceState({ ...history.state, reviewOtherComponent: state }, ''), otherState);
}

async function checkOtherState(page) {
    assert.deepEqual(await page.evaluate(() => history.state?.reviewOtherComponent), otherState);
}

async function statistics(browser, type) {
    const page = await newPage(browser);
    try {
        const modal = page.locator('#modalGrafico');
        const hd = page.locator('#modalGraficoContenido img');
        const button = page.getByRole('button', { name: 'Ampliar gráfico de ' + type, exact: true });
        const previous = base + 'presupuestos/';
        await page.goto(previous);
        await page.locator('#nav-analisis').click();
        const link = page.getByRole('link', { name: 'Estadísticas', exact: true });
        await link.evaluate(anchor => { anchor.search = '?periodo=semanal'; });
        await link.click();
        await button.scrollIntoViewIfNeeded();
        const url = base + 'estadisticas/?periodo=semanal';
        await closed(modal);
        await preserveOtherState(page);
        const before = await length(page);
        const y = await scroll(page);

        await button.click();
        await hd.waitFor();
        await checkOtherState(page);
        assert.equal(await length(page), before + 1);
        await page.goBack(traversal);
        await closed(modal);
        await checkOtherState(page);
        await waitForFocus(page, button);
        assert.equal(page.url(), url);
        assert.equal(await scroll(page), y);
        assert.equal(await page.locator('#estadisticasPeriodo').inputValue(), 'semanal');
        await page.goForward(traversal);
        await hd.waitFor();
        assert.match(await modal.locator('.modal-title').textContent(), new RegExp(type, 'i'));
        await page.reload();
        await hd.waitFor();
        await button.waitFor();
        await modal.getByRole('button', { name: 'Cerrar', exact: true }).last().click();
        await closed(modal);
        await waitForFocus(page, button);
        await button.click();
        await hd.waitFor();
        await page.keyboard.press('Escape');
        await closed(modal);
        assert.equal(await length(page), before + 1);
        await page.goBack(traversal);
        assert.equal(page.url(), previous);
        console.log('OK Estadísticas', type, 'Atrás, Adelante, recarga, cierre, foco, estado ajeno y desplazamiento');
    } finally {
        await page.context().close();
    }
}

async function historyViewer(browser) {
    const page = await newPage(browser);
    try {
        const modal = page.locator('#modalImagen');
        const board = page.locator('#history-board-canvas svg');
        const position = page.locator('#history-board-position');
        const button = page.locator(`[data-history-board-id="${plan}"]`);
        const search = '?nombre_pieza=Tablero&ordenar_por=fecha_asc&page=2';
        await page.goto(base);
        const link = page.getByRole('link', { name: 'Historial', exact: true }).first();
        await link.evaluate((anchor, query) => { anchor.search = query; }, search);
        await link.click();
        const original = page.url();
        assert.equal(new URL(original).search, search);
        assert.equal(await button.getAttribute('role'), 'button');
        await button.scrollIntoViewIfNeeded();
        const y = await scroll(page);
        await closed(modal);
        await preserveOtherState(page);
        const before = await length(page);
        await button.focus();
        await page.keyboard.press('Enter');
        await board.waitFor();
        await page.getByRole('button', { name: 'Tablero siguiente' }).click();
        await position.filter({ hasText: /^Tablero 2 de / }).waitFor();
        await board.waitFor();
        await checkOtherState(page);
        assert.equal(await length(page), before + 1);
        await page.goBack(traversal);
        await closed(modal);
        await checkOtherState(page);
        await waitForFocus(page, button);
        assert.equal(page.url(), original);
        assert.equal(await scroll(page), y);
        assert.equal(await page.locator('input[name="nombre_pieza"]').inputValue(), 'Tablero');
        await page.goForward(traversal);
        await board.waitFor();
        assert.match(await position.textContent(), /^Tablero 2 de /);
        await page.reload();
        await board.waitFor();
        assert.match(await position.textContent(), /^Tablero 2 de /);
        await modal.and(page.locator(':focus-within')).waitFor();
        await modal.getByRole('button', { name: 'Volver al historial' }).click();
        await closed(modal);
        await waitForFocus(page, button);
        await page.keyboard.press('Space');
        await board.waitFor();
        await page.keyboard.press('Escape');
        await closed(modal);
        assert.equal(await length(page), before + 1);
        await page.goBack(traversal);
        assert.equal(page.url(), base);
        console.log('OK Historial: teclado, Atrás, Adelante, recarga, filtros, tablero 2, foco y estado ajeno');
    } finally {
        await page.context().close();
    }
}

async function pending(browser, section, modalId, endpoint, buttonSelector, loaded, expectedRequests) {
    const page = await newPage(browser);
    try {
        let release, calls = 0;
        const gate = new Promise(resolve => { release = resolve; });
        await page.route(endpoint, async route => {
            if (++calls === 1) await gate;
            await route.continue().catch(() => {});
        });
        const url = base + section;
        await page.goto(url);
        const modal = page.locator(modalId);
        const button = page.locator(buttonSelector);
        const request = page.waitForRequest(endpoint);
        await button.click();
        await request;
        await shown(modal);
        await page.goBack(traversal);
        await closed(modal);
        const response = expectedRequests === 1 ? page.waitForResponse(endpoint) : null;
        release();
        if (response) await (await response).finished();
        assert.equal(await modal.isHidden(), true);
        assert.equal(await page.locator(loaded).count(), 0);
        assert.equal(page.url(), url);
        await page.goForward(traversal);
        await page.locator(loaded).waitFor();
        assert.equal(calls, expectedRequests);
        await page.goBack(traversal);
        await closed(modal);
        console.log('OK solicitud pendiente', section, 'al cerrar y avanzar');
    } finally {
        await page.context().close();
    }
}

async function results(browser) {
    const page = await newPage(browser);
    try {
        await page.goto(base + 'resultado/' + plan + '/');
        const modal = page.locator('#modalTablero');
        const trigger = page.locator('[data-open-board]').first();
        const url = page.url();
        await trigger.click();
        await modal.waitFor();
        await page.goBack(traversal);
        await closed(modal);
        assert.equal(page.url(), url);
        await page.goForward(traversal);
        await modal.waitFor();
        console.log('OK Resultados: Atrás y Adelante conservan el comportamiento previo');
    } finally {
        await page.context().close();
    }
}

async function returnAfterNavigation(browser, path, trigger, modalSelector, loaded) {
    const page = await newPage(browser);
    try {
        await page.addInitScript(() => {
            window.addEventListener('pageshow', event => { window.restoredWithBFCache = event.persisted; });
        });
        const url = base + path;
        const content = page.locator(loaded);
        await page.goto(url);
        await page.locator(trigger).click();
        await content.waitFor();
        await page.goto(base);
        await page.goBack(traversal);
        await content.waitFor();
        await page.waitForFunction(() => typeof window.restoredWithBFCache === 'boolean');
        assert.equal(page.url(), url);
        const restored = await page.evaluate(() => window.restoredWithBFCache);
        await page.goBack(traversal);
        await closed(page.locator(modalSelector));
        assert.equal(page.url(), url);
        console.log('OK volver a', path, 'desde otra página, pageshow.persisted=' + restored);
    } finally {
        await page.context().close();
    }
}

async function staleEntry(browser) {
    const page = await newPage(browser);
    try {
        const url = base + 'estadisticas/?periodo=semanal';
        const modal = page.locator('#modalGrafico');
        await page.goto(url);
        await preserveOtherState(page);
        await page.evaluate(() => history.pushState({ ...history.state,
            cutlessStatisticsViewer: { url: location.href, value: 'gráfico retirado' },
        }, ''));
        await page.reload();
        await closed(modal);
        const before = await length(page);
        await page.getByRole('button', { name: 'Ampliar gráfico de desperdicio' }).click();
        await page.locator('#modalGraficoContenido img').waitFor();
        assert.equal(await length(page), before);
        await checkOtherState(page);
        await modal.getByRole('button', { name: 'Cerrar', exact: true }).last().click();
        await closed(modal);
        assert.equal(page.url(), url);
        console.log('OK entrada obsoleta queda inactiva y se reutiliza al abrir un gráfico válido');
    } finally {
        await page.context().close();
    }
}

(async () => {
    assert.ok(session && Number.isSafeInteger(plan) && plan > 0, 'Se requiere sesión local sintética y un plan con varios tableros.');
    const browser = await chromium.launch({
        executablePath: process.env.CUTLESS_TEST_CHROMIUM || undefined,
        ignoreDefaultArgs: ['--disable-back-forward-cache'],
        args: ['--no-sandbox', ...(process.env.HTTPS_PROXY ? ['--proxy-server=' + process.env.HTTPS_PROXY] : [])],
    });
    try {
        for (const type of ['aprovechamiento', 'desperdicio']) await statistics(browser, type);
        await historyViewer(browser);
        await pending(browser, 'estadisticas/', '#modalGrafico', '**/estadisticas/grafico-hd/?*',
            '[aria-label="Ampliar gráfico de aprovechamiento"]', '#modalGraficoContenido img', 1);
        await pending(browser, 'historial/', '#modalImagen', '**/api/tableros/' + plan + '/?*tablero=1',
            `[data-history-board-id="${plan}"]`, '#history-board-canvas svg', 2);
        await results(browser);
        await returnAfterNavigation(browser, 'estadisticas/?periodo=semanal', '[aria-label="Ampliar gráfico de desperdicio"]',
            '#modalGrafico', '#modalGraficoContenido img');
        await returnAfterNavigation(browser, 'historial/', `[data-history-board-id="${plan}"]`,
            '#modalImagen', '#history-board-canvas svg');
        await staleEntry(browser);
    } finally {
        await browser.close();
    }
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
