// Prueba opcional con Playwright y una sesión local de un usuario de prueba.
const assert = require('node:assert/strict');
const { chromium } = require('playwright');

const origen = process.env.CUTLESS_TEST_ORIGIN || 'http://127.0.0.1:8777';
const sesion = process.env.CUTLESS_TEST_SESSION;
const ruta = '/cutless/estadisticas/';
const estados = ['http', 'red', 'tipo', 'png'];
const cargando = 'Cargando gráfico…';
const error = 'No se pudo cargar el gráfico.';

async function verificar(browser, width, colorScheme) {
    const context = await browser.newContext({
        viewport: { width, height: width === 390 ? 844 : 1200 },
        isMobile: width === 390, hasTouch: width === 390, colorScheme,
        ignoreHTTPSErrors: true,
    });
    try {
        await context.addCookies([{ name: 'sessionid', value: sesion, url: origen }]);
        const page = await context.newPage();
        const intentos = new Map();
        await page.route('**/estadisticas/grafico-*/?*', async route => {
            const url = new URL(route.request().url());
            const tipo = url.searchParams.get('tipo');
            const periodo = url.searchParams.get('periodo');
            assert.ok(['semanal', 'mensual'].includes(periodo));
            const clave = url.pathname + tipo + periodo;
            const total = (intentos.get(clave) || 0) + 1;
            intentos.set(clave, total);
            if (tipo === 'desperdicio' || periodo !== 'semanal' || total > estados.length) {
                return route.continue();
            }
            switch (estados[total - 1]) {
                case 'http': return route.fulfill({ status: 503 });
                case 'red': return route.abort('failed');
                case 'tipo': return route.fulfill({ status: 200, contentType: 'text/html', body: 'HTML inesperado' });
                case 'png': return route.fulfill({ status: 200, contentType: 'image/png', body: 'PNG inválido' });
            }
        });
        await page.goto(origen + ruta + '?periodo=semanal');
        assert.equal(await page.locator('html').getAttribute('data-theme'), colorScheme);
        await page.locator('.metric-card').first().waitFor();
        await page.getByText('Hasta 10 mejores resultados del período').waitFor();
        const miniatura = page.locator('[data-tipo="aprovechamiento"]');
        const esperarOtro = page.getByRole('button', { name: 'Ampliar gráfico de desperdicio' });
        await esperarOtro.waitFor();
        assert.equal([...intentos].filter(([clave]) => clave.includes('/grafico-hd/')).length, 0);
        const tamano = (await miniatura.boundingBox()).height;

        async function reintentar(contenedor) {
            for (const _ of estados) {
                await contenedor.getByText(error, { exact: true }).waitFor();
                const boton = contenedor.getByRole('button', { name: 'Reintentar', exact: true });
                // Dos clics sobre el mismo control, incluso después de ocultarlo o retirarlo.
                const estado = await boton.evaluate(el => {
                    const panel = el.parentElement;
                    el.click();
                    el.click();
                    return panel.querySelector('[role="status"]').textContent;
                });
                assert.equal(estado, cargando);
            }
            await contenedor.locator('img').waitFor();
        }

        await reintentar(miniatura);
        assert.ok(Math.abs((await miniatura.boundingBox()).height - tamano) <= 1);
        assert.equal(intentos.get(ruta + 'grafico-miniatura/aprovechamientosemanal'), 5);
        assert.equal(intentos.get(ruta + 'grafico-miniatura/desperdiciosemanal'), 1);
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        await page.getByRole('button', { name: 'Ampliar gráfico de aprovechamiento' }).click();
        const modal = page.locator('#modalGrafico');
        await reintentar(modal.locator('#modalGraficoContenido'));
        assert.equal(intentos.get(ruta + 'grafico-hd/aprovechamientosemanal'), 5);
        assert.ok(await modal.locator('img').evaluate(img => img.naturalWidth > 2000));
        await modal.locator('#zoomSlider').evaluate(slider => {
            slider.value = 250;
            slider.dispatchEvent(new Event('input', { bubbles: true }));
        });
        assert.equal(await modal.locator('#zoomValue').textContent(), '250%');
        assert.ok(await modal.locator('#modalGraficoContenido').evaluate(el => {
            el.scrollLeft = 100;
            return el.scrollLeft > 0;
        }));
        await modal.getByRole('button', { name: 'Restablecer ampliación' }).click();
        assert.equal(await modal.locator('#zoomValue').textContent(), '100%');
        await modal.getByRole('button', { name: 'Cerrar', exact: true }).last().click();
        await modal.waitFor({ state: 'hidden' });
        await page.getByRole('button', { name: 'Ampliar gráfico de aprovechamiento' }).click();
        await modal.locator('img').waitFor();
        assert.equal(intentos.get(ruta + 'grafico-hd/aprovechamientosemanal'), 5);
        await modal.getByRole('button', { name: 'Cerrar', exact: true }).last().click();
        await modal.waitFor({ state: 'hidden' });

        let liberarHd;
        const esperaHd = new Promise(resolve => { liberarHd = resolve; });
        const rutaHd = '**/estadisticas/grafico-hd/?tipo=desperdicio&periodo=semanal';
        let peticionesHd = 0;
        await page.route(rutaHd, async route => {
            peticionesHd++;
            await esperaHd;
            await route.continue();
        });
        await esperarOtro.click();
        const cerrar = modal.getByRole('button', { name: 'Cerrar', exact: true }).last();
        await cerrar.click();
        await modal.waitFor({ state: 'hidden' });
        await esperarOtro.click();
        liberarHd();
        await modal.locator('img').waitFor();
        assert.equal(peticionesHd, 1);
        await cerrar.click();
        await modal.waitFor({ state: 'hidden' });

        // Atrasar una respuesta del período anterior mientras se envía el filtro.
        let liberar;
        const espera = new Promise(resolve => { liberar = resolve; });
        const atrasada = '**/estadisticas/grafico-miniatura/?tipo=aprovechamiento&periodo=semanal';
        await page.route(atrasada, async route => {
            await espera;
            await route.continue().catch(() => {});
        });
        const solicitada = page.waitForRequest(atrasada);
        await page.reload({ waitUntil: 'domcontentloaded' });
        await solicitada;
        await page.locator('#estadisticasPeriodo').selectOption('mensual');
        await page.getByRole('button', { name: 'Aplicar período' }).click();
        await page.waitForURL('**/estadisticas/?periodo=mensual');
        liberar();
        await esperarOtro.waitFor();
        assert.equal(intentos.get(ruta + 'grafico-miniatura/aprovechamientomensual'), 1);
        assert.equal(intentos.get(ruta + 'grafico-miniatura/desperdiciomensual'), 1);
        console.log(`OK ${width} px, tema ${colorScheme}`);
    } finally {
        await context.close();
    }
}

(async () => {
    assert.ok(sesion, 'Indica CUTLESS_TEST_SESSION con una sesión local de prueba.');
    const browser = await chromium.launch({
        executablePath: process.env.CUTLESS_TEST_CHROMIUM || undefined,
        args: ['--no-sandbox', ...(process.env.HTTPS_PROXY ? ['--proxy-server=' + process.env.HTTPS_PROXY] : [])],
    });
    try {
        for (const width of [390, 1440]) {
            for (const tema of ['light', 'dark']) await verificar(browser, width, tema);
        }
    } finally {
        await browser.close();
    }
})().catch(error => {
    console.error(error);
    process.exitCode = 1;
});
