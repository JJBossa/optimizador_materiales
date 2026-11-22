// Playwright contra dos copias locales de CutLess con los mismos datos sintéticos.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const base = process.env.CUTLESS_TEST_BASE || 'http://127.0.0.1:8790';
const current = process.env.CUTLESS_TEST_ORIGIN || 'http://127.0.0.1:8791';
const bootstrap = process.env.CUTLESS_TEST_BOOTSTRAP;
const evidence = process.env.CUTLESS_TEST_EVIDENCE;
const fixture = JSON.parse(fs.readFileSync(process.env.CUTLESS_TEST_FIXTURE, 'utf8'));
const widths = [320, 360, 390, 430, 575, 576, 768, 1280];
const sections = ['clientes', 'materiales', 'proyectos', 'presupuestos', 'detalleProyecto', 'detallePresupuesto',
    'clienteHistorial', 'costos', 'estadisticas', 'resultado', 'historial', 'comparar', 'tiempo', 'asociar',
    'crearProyecto', 'crearPresupuesto', 'admin'];
const totals = {
    detallePresupuesto: { name: 'TOTAL:', colspan: 3 },
    costos: { name: 'Totales y promedio:', colspan: 4 },
};

async function localContext(browser, width, theme, origin) {
    const context = await browser.newContext({
        viewport: { width, height: 900 }, colorScheme: theme, reducedMotion: 'reduce', serviceWorkers: 'block',
    });
    await context.addCookies([{ name: 'sessionid', value: fixture.session, url: origin }]);
    await context.route('**/*', async route => {
        const url = new URL(route.request().url());
        if (url.origin === origin) {
            if (url.pathname.includes('/estadisticas/grafico-miniatura/')) return route.abort();
            if (url.pathname.endsWith('/cutless/css/fonts.css')) {
                // Las dos versiones deben usar las mismas fuentes tras cargarlas, incluso con caché fría.
                const response = await route.fetch({ maxRedirects: 0 });
                assert.ok(response.ok(), `Hoja de fuentes local: HTTP ${response.status()}`);
                const body = (await response.text()).replaceAll('font-display: optional', 'font-display: swap');
                return route.fulfill({ response, body });
            }
            return route.continue();
        }
        if (bootstrap && url.pathname.endsWith('/bootstrap.min.css')) {
            return route.fulfill({ path: bootstrap + '.css', contentType: 'text/css' });
        }
        if (bootstrap && url.pathname.endsWith('/bootstrap.bundle.min.js')) {
            return route.fulfill({ path: bootstrap + '.js', contentType: 'application/javascript' });
        }
        return route.abort();
    });
    return context;
}

async function navigate(page, origin, section, theme) {
    const response = await page.goto(origin + fixture.routes[section]);
    assert.equal(response.status(), 200, section);
    assert.equal(page.url(), origin + fixture.routes[section], section);
    assert.equal(await page.locator('html').getAttribute('data-theme'), theme, section);
    if (section === 'resultado') {
        await page.locator('details.result-details').evaluate(el => { el.open = true; });
        await page.locator('.board-card:not([hidden]) .cut-pieces > .table-responsive > table').first().waitFor();
    }
    if (section === 'historial') {
        await page.locator(`[data-history-board-id="${fixture.plan}"]`).click();
        await page.locator('#history-board-pieces .cut-pieces > .table-responsive > table').waitFor();
    }
    if (section === 'comparar') await page.locator('details.comparison-pieces').evaluate(el => { el.open = true; });
    await page.locator('table:visible').first().waitFor();
    await page.evaluate(async () => {
        await Promise.all([400, 500, 600, 700].map(weight => document.fonts.load(`${weight} 16px Barlow`)));
        await document.fonts.ready;
    });
}

function inspect(page) {
    return page.evaluate(() => ({
        viewport: document.documentElement.clientWidth,
        documentWidth: document.documentElement.scrollWidth,
        tables: Array.from(document.querySelectorAll('table')).filter(table => table.getClientRects().length).map(table => {
            const box = table.getBoundingClientRect();
            const wrapper = table.closest('.table-responsive');
            return {
                display: getComputedStyle(table).display,
                dimensions: [box.width, box.height].map(value => Math.round(value * 10)),
                width: table.clientWidth,
                scroll: table.scrollWidth,
                wrapperWidth: wrapper?.clientWidth,
                wrapperScroll: wrapper?.scrollWidth,
                rows: Array.from(table.rows).filter(row => row.getClientRects().length).map(row =>
                    Array.from(row.cells).map(cell => [cell.innerText.trim(), cell.colSpan, cell.offsetWidth])),
            };
        }),
    }));
}

function visibleAmounts(page) {
    return page.locator('table td:visible').evaluateAll(cells => cells.flatMap(cell =>
        cell.innerText.match(/-?\$[\d.]+/g) || []));
}

async function matrix(browser, width, theme) {
    const context = await localContext(browser, width, theme, current);
    let before;
    try {
        if (width > 575 || width === 320 || (evidence && width === 390 && theme === 'light')) {
            before = await localContext(browser, width, theme, base);
        }
        const page = await context.newPage();
        const previous = await before?.newPage();
        for (const section of sections) {
            await navigate(page, current, section, theme);
            const after = await inspect(page);
            assert.ok(after.tables.length, section);
            if (width <= 575) {
                assert.ok(after.documentWidth <= width + 1, `${section} ${width}: página ${after.documentWidth}`);
                for (const table of after.tables) {
                    assert.ok(table.scroll <= table.width + 1, `${section} ${width}: tabla ${table.scroll}/${table.width}`);
                    assert.ok(!table.wrapperWidth || table.wrapperScroll <= table.wrapperWidth + 1,
                        `${section} ${width}: contenedor ${table.wrapperScroll}/${table.wrapperWidth}`);
                }
                if (section === 'comparar') assert.ok(after.tables.every(table => table.display === 'table'));
                if (width === 320 && totals[section]) {
                    const { name, colspan } = totals[section];
                    const heading = page.getByRole('rowheader', { name, exact: true });
                    assert.equal(await heading.count(), 1, section);
                    assert.equal(await heading.getAttribute('colspan'), String(colspan), section);
                    const amounts = await visibleAmounts(page);
                    assert.ok(amounts.length > 0, section);
                    await navigate(previous, base, section, theme);
                    assert.deepEqual(amounts, await visibleAmounts(previous), `${section} ${theme}: importes CLP`);
                }
            }
            if (width > 575) {
                await navigate(previous, base, section, theme);
                assert.deepEqual(after, await inspect(previous), `${section} ${width} ${theme}: escritorio`);
            }
            if (evidence && section === 'clientes' && (width === 390 || width === 1280) && theme === 'light') {
                if (width === 390) await navigate(previous, base, section, theme);
                await previous.locator('.table-responsive').first().screenshot({ path: path.join(evidence, `clientes-antes-${width}.png`) });
                await page.locator('.table-responsive').first().screenshot({ path: path.join(evidence, `clientes-despues-${width}.png`) });
            }
            if (evidence && width === 390 && theme === 'dark' && ['comparar', 'detallePresupuesto'].includes(section)) {
                await page.screenshot({ path: path.join(evidence, `${section}-390-oscuro.png`), fullPage: true });
            }
        }
        console.log(`OK ${width}px ${theme}: ${sections.length} secciones`);
    } finally {
        await Promise.all([context.close(), before?.close()]);
    }
}

async function interactions(browser) {
    const context = await localContext(browser, 320, 'light', current);
    try {
        const page = await context.newPage();
        await navigate(page, current, 'crearPresupuesto', 'light');
        const first = page.locator('tr[data-budget-plan]:visible input[type=checkbox]').first();
        const checkedId = await first.getAttribute('id');
        await page.locator(`label[for="${checkedId}"]`).click();
        assert.equal(await first.isChecked(), true);
        await page.locator('[data-budget-page="next"]').click();
        const checked = page.locator(`#${checkedId}`);
        assert.equal(await checked.isVisible(), false);
        assert.equal(await checked.isChecked(), true);
        await page.locator('#budget-plan-search').fill('SinResultadosCutLess');
        await page.locator('#budget-no-matches').waitFor();
        assert.equal(await page.locator('tr[data-budget-plan]:visible').count(), 0);
        assert.equal(await page.locator('tr[data-budget-plan] input:checked').count(), 1);
        await page.locator('#budget-plan-search').fill('');
        await page.locator('tr[data-budget-plan]:visible').first().waitFor();
        assert.equal(await page.locator('#budget-no-matches').isVisible(), false);

        await navigate(page, current, 'asociar', 'light');
        const selectAll = page.locator('#select-all');
        await page.locator('button[value="agregar"]').focus();
        await page.keyboard.press('Tab');
        assert.equal(await selectAll.evaluate(el => el === document.activeElement), true);
        assert.notEqual(await selectAll.evaluate(el => getComputedStyle(el).outlineStyle), 'none');
        await page.keyboard.press('Space');
        const selected = await page.locator('input.optimizacion-checkbox:checked').count();
        assert.ok(selected > 1);
        await page.keyboard.press('Tab');
        assert.equal(await page.locator('input.optimizacion-checkbox').first().evaluate(el => el === document.activeElement), true);
        await page.locator('button[value="siguiente"]').click();
        assert.equal(await page.locator('input.selection-preserved').count(), selected);
        await page.locator('#project-plan-search').fill('SinResultadosCutLess');
        await page.locator('button[value="buscar"]').click();
        await page.getByText(/No hay coincidencias/).waitFor();
        assert.equal(await page.locator('input.selection-preserved').count(), selected);
        if (process.env.CUTLESS_TEST_MUTATIONS === '1') {
            await page.locator('button[value="agregar"]').click();
            await page.waitForURL(current + fixture.routes.detalleProyecto);
            assert.equal(await page.locator('table tbody tr').count(), selected + 1);
        }

        await navigate(page, current, 'clientes', 'light');
        const table = page.getByRole('table').first();
        assert.ok(await table.getByRole('columnheader', { name: 'Email', exact: true }).count());
        assert.ok(await table.getByRole('cell').count());
        const edit = table.getByRole('link', { name: 'Editar', exact: true }).first();
        const editUrl = await edit.getAttribute('href');
        await edit.click();
        await page.locator('form input[name="nombre"]').waitFor();
        if (process.env.CUTLESS_TEST_MUTATIONS === '1') {
            const note = 'Verificación de edición con datos sintéticos';
            await page.locator('form textarea[name="notas"]').fill(note);
            await page.getByRole('button', { name: 'Guardar cambios' }).click();
            await page.waitForURL(current + fixture.routes.clientes);
            await table.locator(`a[href="${editUrl}"]`).click();
            assert.equal(await page.locator('form textarea[name="notas"]').inputValue(), note);
        }
        await navigate(page, current, 'clientes', 'light');
        await table.getByRole('link', { name: 'Historial', exact: true }).first().click();
        await page.getByRole('heading', { name: /Historial/ }).first().waitFor();
        await navigate(page, current, 'clientes', 'light');
        await table.locator(`a[href="${fixture.routes.eliminarCliente}"]`).click();
        const remove = page.getByRole('button', { name: 'Sí, eliminar cliente' });
        await remove.waitFor();
        if (process.env.CUTLESS_TEST_MUTATIONS === '1') {
            await remove.click();
            await page.getByRole('button', { name: 'Sí, eliminar', exact: true }).click();
            await page.waitForURL(current + fixture.routes.clientes);
            assert.equal(await table.locator(`a[href="${fixture.routes.eliminarCliente}"]`).count(), 0);
        }

        await navigate(page, current, 'admin', 'light');
        await page.getByRole('link', { name: 'Página siguiente' }).click();
        assert.match(page.url(), /page=2/);
        await page.locator('#adminUserSearch').fill('SinResultadosCutLess');
        await page.getByRole('button', { name: 'Buscar', exact: true }).click();
        await page.getByText('No se encontraron usuarios').waitFor();

        await page.emulateMedia({ media: 'print' });
        await page.goto(current + fixture.routes.imprimir);
        assert.ok(await page.locator('table').count());
        assert.equal(await page.locator('table').first().evaluate(el => getComputedStyle(el).display), 'table');
        assert.equal(await page.locator('.mobile-table-cards').count(), 0);
        const forms = process.env.CUTLESS_TEST_MUTATIONS === '1' ? 'envío de edición y eliminación' : 'apertura de edición y eliminación';
        console.log('OK flujos: selección, paginación, búsqueda, teclado, accesibilidad, ' + forms + ' e impresión');
    } finally {
        await context.close();
    }
}

(async () => {
    for (const origin of [base, current]) assert.match(origin, /^http:\/\/(127\.0\.0\.1|localhost):\d+$/);
    assert.ok(fixture.session && bootstrap, 'Se requieren una sesión sintética y Bootstrap local.');
    if (evidence) fs.mkdirSync(evidence, { recursive: true });
    const browser = await chromium.launch({ executablePath: process.env.CUTLESS_TEST_CHROMIUM || undefined });
    try {
        const selectedWidths = process.env.CUTLESS_TEST_WIDTHS ? process.env.CUTLESS_TEST_WIDTHS.split(',').map(Number) : widths;
        if (process.env.CUTLESS_TEST_ONLY !== 'flows') {
            for (const width of selectedWidths) {
                await Promise.all(['light', 'dark'].map(theme => matrix(browser, width, theme)));
            }
        }
        if (process.env.CUTLESS_TEST_ONLY !== 'matrix') await interactions(browser);
    } finally {
        await browser.close();
    }
})().catch(error => { console.error(error); process.exitCode = 1; });
