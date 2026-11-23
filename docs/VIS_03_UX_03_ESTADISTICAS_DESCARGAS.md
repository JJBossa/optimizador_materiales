# VIS-03 y UX-03 en CutLess

La rama `fix/vis03-ux03-estadisticas-descargas` parte de `upstream/main` en `fd90c92aa46d90d422dcb1212c25b903f1faa3ab`, la fusión del PR #27. Esa revisión incorpora CLI-02, UX-01, PRE-01 y su consistencia horaria, VIS-01, VIS-02 y UX-02.

## VIS-03 · Acciones de Estadísticas

El top del período mezclaba botones normales y compactos. En Chromium, «Ver resultado», «Duplicar» y «PDF» medían respectivamente **146 × 44**, **111 × 34** y **85 × 34 px**, con redondeo al píxel. El listado y el grupo de exportaciones del período reutilizan `management-action-set` de VIS-02. Las cinco acciones miden **160 × 44 px** en la configuración probada. Se conservaron sus colores, iconos, destinos y orden de tabulación.

La columna Acciones reserva el ancho de un botón en la tabla. Las tarjetas móviles adaptan el grupo al ancho disponible. Al abrir los tipos de pieza se permite que el texto se ajuste a su celda. El selector de período, la ayuda y los controles del visor mantienen sus propias medidas. Las consultas y la presentación de gráficos, el cálculo y el orden del top quedan fuera del cambio. [Prueba de Chromium](../cut/cutless/tests/browser/estadisticas-acciones.cjs)

| Vista | Antes | Después |
| --- | --- | --- |
| Móvil, 390 px, tema claro | [Tarjeta](evidencia/vis03-ux03/estadisticas-antes-390.png) | [Tarjeta](evidencia/vis03-ux03/estadisticas-despues-390.png) |
| Escritorio, 1280 px, tema oscuro | [Tabla](evidencia/vis03-ux03/estadisticas-antes-1280.png) | [Tabla](evidencia/vis03-ux03/estadisticas-despues-1280.png) |

## UX-03 · Inventario de descargas

El controlador anterior seleccionaba enlaces por texto o fragmentos de URL. Las exportaciones del período, Costos y los enlaces de Presupuestos con destino `_blank` quedaban fuera. Los enlaces interceptados pasaban por `fetch` y un Blob, y la espera visual tenía un cierre fijo a los 15 segundos.

| Pantalla o control | Rutas de CutLess | Comportamiento |
| --- | --- | --- |
| Historial de optimizaciones, menú Más opciones | `descargar-pdf/<pk>/`, `descargar-excel/<pk>/`, `descargar-png/<pk>/` | Indicador y entrega nativa PDF, XLSX y primer PNG. El mismo menú deja visibles sus enlaces sin JavaScript. |
| Resultados de una optimización | `descargar-pdf/<pk>/`, `descargar-excel/<pk>/` | Indicador y entrega nativa de los dos formatos. |
| Plano individual, en Resultados y paneles del visor que reutilizan `board-layout.html` | `descargar-png/<pk>/<tablero>/` | Indicador y entrega nativa del tablero elegido. Los paneles insertados después de cargar la página usan el mismo enlace. |
| Estadísticas, exportaciones del período y PDF por fila | `estadisticas/exportar-excel-desperdicio/?periodo=…`, `estadisticas/exportar-pdf-desperdicio/?periodo=…`, `descargar-pdf/<pk>/` | Indicador en los tres controles y conservación del período en las exportaciones. |
| Presupuestos, listado y detalle | `presupuestos/<pk>/pdf/` | Indicador en la página de origen y conservación de `_blank`. Los PDF generados mantienen `attachment` y los archivados mantienen `inline` y su nombre original. |
| Historial de costos | `historial-costos/?export=excel&fecha_desde=…&fecha_hasta=…` | Indicador para XLSX con el filtro elegido. La consulta normal de Costos queda fuera de la señal. |
| Estimación de tiempo de corte | `descargar-pdf/<pk>/` | Indicador y entrega nativa del PDF del plan. |
| Proyectos, Plantillas, Materiales y Clientes | Sin exportación directa en las pantallas auditadas | Los accesos al resultado de una optimización son navegación normal. |
| Imprimir en Historial, miniaturas y gráficos HD, `/media/`, Findic | Páginas imprimibles, medios visuales, archivos privados y destino externo | Conservan sus flujos. La vista de presupuesto puede servir un PDF archivado mediante `media_privada` y señaliza esa descarga desde la ruta de presupuesto. |

### Inicio, preparación y recuperación

Los enlaces reales se declaran con `data-descarga`. Un único controlador reutiliza el símbolo animado, el fondo y la preferencia de movimiento reducido de `includes/loading.html` y `loading.css`. El texto se anuncia una vez en una región persistente `role="status"`. Los avisos tienen `role="alert"` y se pueden cerrar sin atrapar el foco en un diálogo. Mientras se prepara un archivo se suprimen clics duplicados. Las interacciones modificadas del navegador, como Ctrl o Cmd más clic, mantienen su ruta nativa.

El navegador emite un único GET a la ruta original con un token aleatorio. Las descargas que ya apuntaban a otra pestaña conservan su destino. Las demás usan un marco oculto del mismo origen para conservar la URL y el estado de la página original. El middleware actúa solo en las rutas inventariadas y señala el resultado mediante una cookie efímera al enviar las cabeceras. Comprueba el estado HTTP, el tipo MIME y `Content-Disposition`. La señal no autoriza acceso. Las vistas originales siguen aplicando sus controles de sesión, permiso y propiedad. Se conservan el contenido, el nombre, el modo de disposición y el streaming. El controlador tampoco vuelve a solicitar el archivo ni lo copia a un Blob en JavaScript.

Al recibir la señal, la superposición se retira. En los flujos con marco, el marco se conserva durante la vida de la página tras recibir cabeceras para permitir que el navegador termine de recibir el cuerpo. Los errores de sesión, propiedad, permiso, preparación y contenido inesperado muestran mensajes específicos. La salida de la página limpia la espera. Un plazo de 120 segundos cubre solicitudes sin señal. En ese caso se pide comprobar las descargas del navegador antes de repetir la solicitud.

La señal acredita **preparación y recepción de cabeceras**, no que el archivo se haya guardado en disco. La cancelación del diálogo de guardado o una interrupción del cuerpo después de las cabeceras quedan a cargo del navegador. El plazo de recuperación se trata como resultado sin confirmar. Sin JavaScript se usan los enlaces originales.

| Evidencia con datos sintéticos | Captura |
| --- | --- |
| PDF de Historial en móvil, con movimiento reducido | [Indicador PDF](evidencia/vis03-ux03/descarga-movil.png) |
| Excel de Historial en escritorio, tema oscuro | [Indicador Excel](evidencia/vis03-ux03/descarga-escritorio.png) |

## Pruebas y alcance

| Prueba | Resultado |
| --- | --- |
| Django completa · SQLite | 472 aprobadas, 8 omitidas por requerir bloqueo de filas |
| Django completa · PostgreSQL local | 480 aprobadas |
| Regresiones dirigidas · descargas, Estadísticas, permisos, exportaciones, Clientes y Presupuestos | 96 aprobadas en PostgreSQL local |
| Chromium VIS-03 | 320, 390, 768 y 1280 px en ambos temas. Igualdad de rectángulos, colores, foco y ausencia de desbordamiento. |
| Chromium UX-03 | 13 controles de descarga en móvil y un recorrido adicional de escritorio. Se comprobaron los tipos MIME, la disposición, las firmas de los archivos recibidos, el PDF archivado y tres descargas sin JavaScript. |
| Recuperación en Chromium | 401, 403, 404, 500, sesión eliminada, interrupción sin señal, doble activación, descargas consecutivas y regreso a la página. |
| Node y Worker simulado | 67 y 8 aprobadas |
| `makemigrations --check --dry-run` y `git diff --check` | Sin cambios de esquema ni incidencias |

VIS-03 cambia `estadisticas.html` y `estadisticas.css`. UX-03 actualiza las plantillas del inventario, los recursos del indicador y `confirmaciones.js`. Añade `descargas.js` y el middleware `cutless/descargas.py`, registrado en los ajustes de Django. Se incorporan pruebas de middleware en `test_descargas.py` y recorridos permanentes de navegador con una SQLite desechable. [Pruebas de descargas en Chromium](../cut/cutless/tests/browser/descargas.cjs)

Para repetir los recorridos, cargar `fixtures-estadisticas-descargas.py` mediante `manage.py shell` con `CUTLESS_TEST_FIXTURE` apuntando a un JSON nuevo. Ejecutar `estadisticas-acciones.cjs` y `descargas.cjs` con Playwright, el servidor local en `CUTLESS_TEST_ORIGIN`, el JSON de sesión sintética y copias locales de Bootstrap en `CUTLESS_TEST_BOOTSTRAP` y `CUTLESS_TEST_BOOTSTRAP_JS`. `CUTLESS_TEST_BASE` permite comparar con el servidor de la revisión anterior. `CUTLESS_TEST_EVIDENCE` guarda las capturas. La verificación de navegador y entrega nativa se limita a Chromium Linux.
