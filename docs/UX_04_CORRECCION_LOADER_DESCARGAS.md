# UX-04 · Indicador de descargas

La rama `fix/ux04-loader-descargas` parte de `upstream/main` en `671e6a0aecc9a395cc1a9f005bc9fc4b8e25d6e2`, la fusión del PR #28. El diagnóstico comparó esta revisión con `fd90c92aa46d90d422dcb1212c25b903f1faa3ab`, anterior al PR #28, y repitió las mediciones con la corrección. Se usaron el mismo navegador Chromium, servidores locales y datos sintéticos.

## Diagnóstico reproducido

Con movimiento normal, `getComputedStyle()` mostró `animation-name: cutless-loading-piece`, `animation-duration: 1.6s` y `animation-play-state: running` en las cinco piezas, con retrasos de `0`, `320`, `640`, `960` y `1280` ms según su orden visual. En PDF de Historial con la respuesta retenida 1,8 s, el relleno cambió y el acento pasó por las piezas antes y después del PR #28. Con `prefers-reduced-motion: reduce`, las reglas de accesibilidad desactivaron la animación y se observó un único relleno por pieza durante la espera. El archivo `loading.css` se cargó con la versión de cada revisión y una consulta condicional local devolvió 304. El ciclo SVG se conservaba en la revisión fusionada.

La diferencia apareció en las respuestas rápidas. UX-03 retiraba la superposición al recibir la señal de preparación. El Excel rápido de Historial terminó cerca de los 206 ms y solo apareció el primer resaltado. Al segundo paso se llega a los 320 ms. Esta limitación también podía presentarse antes del PR #28 en respuestas rápidas. La espera larga confirmó que el síntoma se debía al tiempo de exposición en el caso reproducido.

En Presupuestos, antes del PR #28 el flujo `_blank` quedaba fuera del indicador. Tras la fusión, la superposición se insertaba pero el disparo de la pestaña se hacía en el mismo ciclo de JavaScript. La traza registró cero fotogramas de la superposición antes de activar el enlace. En los PDF rápidos, la retirada ocurrió entre 202 y 207 ms desde el clic. Se observó HTTP 200 con `application/pdf`. El listado y el detalle devolvieron el PDF nuevo como `attachment`, mientras el archivado conservó `inline` y su nombre. La revisión fusionada emitió la cookie de preparación y las ejecuciones comparativas terminaron sin excepciones JavaScript.

| Escenario sintético | Antes del PR #28 | PR #28 fusionado | Con UX-04 |
| --- | --- | --- | --- |
| Excel rápido de Historial | Retirada a 193 ms y un estado de relleno observado | 206 ms y un estado | 421 ms y cuatro estados observados |
| PDF rápido nuevo desde listado y detalle | Enlace `_blank` sin indicador | `_blank` con cero fotogramas previos | En el recorrido dedicado, aperturas a 12 y 54 ms con dos fotogramas previos y retiradas a 422 ms |
| PDF rápido archivado | Apertura `inline` desde el detalle sin indicador | Cero fotogramas previos en el detalle | Uno o dos fotogramas previos desde listado y detalle en el recorrido dedicado. Se mantuvieron `inline` y los bytes archivados. |
| PDF de Historial con retención de 1,8 s | La secuencia era visible | La secuencia era visible | La secuencia sigue visible y el indicador se retira al recibir la señal, sin retención visual adicional. |

Los tiempos describen ejecuciones locales concretas. La traza cuenta oportunidades de pintura con `requestAnimationFrame` y las capturas verifican el resultado gráfico del compositor.

## Corrección

- En `_blank`, la página visible ofrece un fotograma al indicador antes de activar el enlace nativo. Se programan dos llamadas consecutivas a `requestAnimationFrame` dentro de la activación del clic y un respaldo de 80 ms si el navegador aplaza los fotogramas. Una página oculta o un navegador sin activación activa usa el lanzamiento inmediato.
- Una confirmación rápida libera el enlace y cambia el texto a «Archivo preparado.». El mismo indicador se conserva hasta completar **420 ms** de presentación y deja pasar los clics. El plazo es solo visual y la señal HTTP inicia el cambio de estado. Una espera larga termina al recibir la señal y los errores se muestran inmediatamente. La navegación limpia ambos estados.
- Continúan los tres mensajes originales por formato y la preferencia de movimiento reducido. Se actualizaron las referencias de `loading.css` y `descargas.js` para que el navegador solicite las versiones nuevas. Las rutas, los archivos, sus cabeceras de descarga y el middleware de señalización se conservan.

## Evidencia de fotogramas

Cada pareja consiste en dos capturas reales del símbolo. Se comparó el color de los píxeles RGB dentro del recorte. El recorrido permanente también verifica en vivo los rellenos de las dos primeras piezas y captura el compositor durante la espera. [Prueba de Chromium](../cut/cutless/tests/browser/loader-descargas.cjs)

| Revisión y modo | Primer fotograma | Segundo fotograma | Resultado de la comparación |
| --- | --- | --- | --- |
| Antes del PR #28, claro | [A](evidencia/ux04/antes28-logo-a.png) | [B](evidencia/ux04/antes28-logo-b.png) | 9.235 píxeles cambiaron |
| PR #28 fusionado, claro | [A](evidencia/ux04/fusion28-logo-a.png) | [B](evidencia/ux04/fusion28-logo-b.png) | 9.235 píxeles cambiaron |
| UX-04, claro, misma medición | [A](evidencia/ux04/ux04-logo-a.png) | [B](evidencia/ux04/ux04-logo-b.png) | 9.235 píxeles cambiaron |
| UX-04, escritorio oscuro con movimiento normal | [A](evidencia/ux04/ux04-no-preference-a.png) | [B](evidencia/ux04/ux04-no-preference-b.png) | 10.861 píxeles cambiaron |
| UX-04, móvil claro con movimiento reducido | [A](evidencia/ux04/ux04-reduce-a.png) | [B](evidencia/ux04/ux04-reduce-b.png) | 0 píxeles cambiaron |

## Verificación y límites

| Prueba | Resultado |
| --- | --- |
| Django completa · SQLite | 472 aprobadas, 8 omitidas por requerir bloqueo de filas |
| Django completa · PostgreSQL local | 480 aprobadas |
| Chromium UX-04 | 6 escenarios. Fotogramas reales durante la espera, modo reducido estático y PDF nuevo y archivado desde listado y detalle, a 390 y 1280 px. |
| Chromium UX-03 | 13 controles con archivos reales, recorrido adicional de escritorio, 3 descargas sin JavaScript, 401/403/404/500, sesión expirada, ausencia de señal, doble activación, descargas consecutivas y regreso con Atrás. |
| Chromium VIS-03 | 8 combinaciones de ancho y tema aprobadas |
| Node y Worker simulado | 67 y 8 aprobadas |
| `makemigrations --check --dry-run` y `git diff --check` | Sin cambios de esquema ni incidencias |

La confirmación corresponde a las cabeceras del archivo preparado. El guardado final y las cancelaciones posteriores dependen del navegador. La comprobación se hizo en Chromium Linux. Otros navegadores pueden gestionar la apertura de pestañas o la activación transitoria de forma distinta. Si el navegador aplaza la pintura, el respaldo prioriza iniciar la descarga.

El cambio funcional está en `descargas.js`, `loading.css` y `base.html`. Para repetir los recorridos, preparar `fixtures-estadisticas-descargas.py` en una SQLite local y usar la configuración de Playwright de VIS-03 y UX-03. Ejecutar `loader-descargas.cjs` y `descargas.cjs`. [Configuración local](VIS_03_UX_03_ESTADISTICAS_DESCARGAS.md) · [Regresión de UX-03](../cut/cutless/tests/browser/descargas.cjs)
