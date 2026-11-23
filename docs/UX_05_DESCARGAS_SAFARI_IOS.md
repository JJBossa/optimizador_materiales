# UX-05 · Descargas de CutLess en Safari iOS

La corrección parte de `upstream/main` `35aa5d5ec69e5fca523fbfc3a648eeb5a039f545`, con UX-03, UX-04 y VIS-04 integrados.

## Evidencia del iPhone

En producción, el usuario observó que la pulsación normal fallaba con PDF y PNG en distintos paneles. Al mantener presionado el enlace y elegir **Open in New Tab**, Safari abrió el PDF y mostró **View** y **Download** para `OPT-0026_tablero-1.png`. En Estadísticas, Excel mostró un diálogo de descarga nativo. El reporte identifica Estadísticas para Excel y deja sin identificar los paneles exactos de PDF y PNG. Es una observación de la incidencia, anterior a esta corrección.

La evidencia muestra que las rutas de PDF y PNG respondieron desde una pestaña iniciada por Safari. `descargas.js` interceptaba el clic normal y enviaba los enlaces en la misma pestaña a un iframe oculto. Para enlaces que ya tenían `target="_blank"`, sintetizaba otra activación para presentar el indicador antes de abrir. Ambos flujos cambian la forma en que Safari recibe la activación. La corrección usa el enlace original como en la prueba física que funcionó.

## Corrección compartida

- En iOS y iPadOS, el módulo compartido deja que el navegador siga el `href` original con la activación del usuario. Se reconoce también iPadOS cuando Safari solicita el sitio de escritorio. PDF y PNG usan una pestaña nueva con `noopener`. Excel usa el destino original y el diálogo que proporcione el navegador.
- Los enlaces de PDF y PNG anuncian la pestaña nueva y cómo guardar una vista previa. Si Safari ofrece **Descargar**, se puede usar directamente. Si abre el documento o la imagen, el menú **Compartir → Guardar en Archivos** permite elegir dónde guardarlo. Para Excel que se descarga directamente, el archivo queda disponible en las descargas de Safari o en Archivos.
- En iOS el navegador controla la descarga o la vista previa. El indicador de UX-04 sigue activo en escritorio. Los enlaces renderizados por Django siguen disponibles sin JavaScript.
- El cambio conserva las rutas, parámetros, nombres, bytes, permisos y cabeceras de las exportaciones. Los PDF nuevos de Presupuestos conservan `attachment`. Los archivados conservan `inline`, su nombre original y la apertura en otra pestaña.

## Inventario y matriz de validación

| Panel | Controles y destino | Safari en iPhone después del despliegue |
| --- | --- | --- |
| Historial | PDF y Excel del plan desde «Más opciones», con el orden aplicado. PNG del primer tablero desde el mismo menú. | Pendientes PDF, Excel y PNG. |
| Resultado | PDF y Excel del plan. PNG individual, con número de tablero en la ruta. | Pendientes PDF, Excel y PNG. |
| Estadísticas | PDF y Excel del período seleccionado. PDF del plan desde cada fila del listado. | Pendientes ambas descargas PDF y volver a comprobar Excel. El diálogo de Excel se observó en producción antes del cambio. |
| Presupuestos · listado | PDF nuevo y PDF archivado desde la fila correspondiente. | Pendientes ambos. |
| Presupuestos · detalle | PDF nuevo y PDF archivado desde el botón del presupuesto. | Pendientes ambos. |
| Estimar tiempo de corte | PDF del plan. | Pendiente PDF. |
| Historial de costos | Excel con las fechas aplicadas. | Pendiente Excel. |

Las 13 ubicaciones de enlace y las dos variantes archivadas abarcan ocho rutas de exportación. En Estadísticas, las imágenes de gráfico sirven a los visores. «Imprimir plan», en Historial y Resultado, abre una vista de impresión del navegador. Se verificó que esas acciones tienen flujos separados de la descarga de archivos. [Mapa de rutas](../cut/cutless/urls.py) · [Respuestas observadas por UX-04](../cut/cutless/descargas.py)

## Revisión previa al PR · Enlaces y contenido dinámico

En `e9fb3c1`, todos los enlaces interactivos de PDF y PNG del inventario llegan en el HTML inicial de sus páginas. El script diferido `descargas.js` los encuentra incluso si están en un menú cerrado o en un tablero oculto. La revisión permite conservar la inicialización actual.

| Flujo revisado | Qué ocurre después de cargar la página |
| --- | --- |
| Resultado | La plantilla renderiza el PDF y el PNG de cada tablero. Cambiar de tablero alterna la visibilidad de los paneles existentes. La animación solo añade marcadores de carga. [Plantilla de Resultado](../cut/cutless/templates/cutless/resultado.html) · [Plantilla del PNG](../cut/cutless/templates/cutless/includes/board-layout.html) · [Paginación](../cut/cutless/static/cutless/js/board-deck.js) · [Animación](../cut/cutless/static/cutless/js/result-reveal.js) |
| Visor de Resultado | Clona únicamente el dibujo, los datos y el detalle de piezas. El enlace PNG permanece en la cabecera del panel original. [Visor de Resultado](../cut/cutless/static/cutless/js/board-viewer.js) |
| Visor de Historial | La API devuelve un fragmento con el enlace PNG en la cabecera. El visor inserta solo el dibujo o la imagen, el resumen y las piezas, también al recorrer tableros antiguos. El PNG y el PDF accesibles en Historial pertenecen al menú «Más opciones» renderizado en la página. [Respuesta de la API](../cut/cutless/views/exports.py) · [Visor de Historial](../cut/cutless/static/cutless/js/history-board-viewer.js) · [Menú de Historial](../cut/cutless/templates/cutless/historial.html) |
| Gráfico de Estadísticas y lupa de escritorio | El visor de gráficos inserta una imagen. La lupa clona una copia visual inerte, fuera de la interacción del usuario. [Gráfico de Estadísticas](../cut/cutless/templates/cutless/estadisticas.html) · [Lupa](../cut/cutless/static/cutless/js/magnifier.js) |

En Chromium 156 con perfil de iPhone 13 y un plan sintético de tres tableros, se observaron las inserciones en el DOM desde el fin del análisis del HTML. El PDF y los tres PNG de Resultado conservaron sus nodos, `href`, `target="_blank"` y `aria-describedby` durante la animación, la paginación y el visor. Se comprobó también que los cuatro `href` llegan con JavaScript desactivado. En Historial, las dos respuestas inspeccionadas de la API contenían el PNG y el visor mantuvo cero enlaces de descarga al recorrer los tableros 1 y 2. Los toques en el PDF de Resultado, el PNG del tercer tablero y el PNG del menú de Historial generaron una sola navegación al `href` original por toque y entregaron los archivos esperados. Pasaron también 19 pruebas de Django de visores, Historial, PNG y descargas.

## Pruebas locales

| Entorno | Resultado |
| --- | --- |
| Chromium 156 en Linux, iPhone emulado | Los 13 enlaces y los dos PDF archivados se activaron con toque normal y navegación nativa. Se verificaron los destinos, formatos, nombres y firmas, la ausencia de iframe y el indicador de pestaña nueva. |
| Chromium 156 en Linux, iPadOS con identificación de escritorio | PDF y PNG de Resultado y Excel de Estadísticas recorrieron la rama nativa. |
| Chromium 156 en Linux, JavaScript desactivado | Pasaron los 13 casos de descarga y los PDF archivados del listado y detalle. |
| WebKitGTK 2.52.6 en Linux, agente de iPhone | La activación por teclado recorrió los 13 controles, entregó archivos con las firmas esperadas y abrió los dos PDF archivados. Se comprobó que la activación siguió el enlace nativo sin iframe. |
| Chrome 158 en Linux, agente de Windows | Pasó el recorrido de escritorio de los 13 controles, el PDF archivado y las regresiones de UX-03. La prueba nativa sobre Windows está pendiente. |
| Chrome 158 en Linux, UX-04 | Pasaron los seis escenarios del indicador, incluidos movimiento normal, movimiento reducido y los PDF nuevos y archivados de Presupuestos. |
| Firefox ESR 153 en Linux | WebDriver activó los 13 controles con el clic de escritorio y comprobó los archivos en disco. Los dos PDF archivados abrieron su propia pestaña. |
| Django y Node | SQLite completa con 472 aprobadas y 8 omitidas por requerir bloqueo de filas. PostgreSQL local con 53 pruebas dirigidas de permisos, exportaciones, medios privados y Presupuestos. Node con 67 pruebas aprobadas. |
| Migraciones y formato | `makemigrations --check --dry-run` y `git diff --check` pasaron. |

La emulación verifica los enlaces y la navegación que llegan al navegador. Los diálogos de Safari iOS y la escritura en Archivos se deben comprobar en el dispositivo. El servidor de binarios de Playwright rechazó la descarga de su WebKit en el entorno local, por lo que la comprobación del motor se ejecutó con WebKitGTK.

Para repetir en local, prepara la SQLite con `fixtures-estadisticas-descargas.py` y usa el servidor de pruebas y Bootstrap local descritos en UX-03. Ejecuta `node cut/cutless/tests/browser/descargas-nativas.cjs`. Con `CUTLESS_TEST_ENGINE=webkit` se usa el WebKit de Playwright cuando esté instalado. `descargas.cjs` y `loader-descargas.cjs` comprueban los flujos de escritorio. `CUTLESS_TEST_WINDOWS_UA=1` aplica el agente de Chrome para Windows en `descargas.cjs`. [Configuración local](VIS_03_UX_03_ESTADISTICAS_DESCARGAS.md) · [Prueba de descargas nativas](../cut/cutless/tests/browser/descargas-nativas.cjs) · [Prueba de UX-04](../cut/cutless/tests/browser/loader-descargas.cjs)

## Validación física pendiente

Después del despliegue, recorrer la matriz en Safari del iPhone con JavaScript activo. Pulsar una vez cada enlace y abrir el archivo entregado. Para PDF y PNG, probar también el guardado desde la vista previa y abrir el archivo en Archivos. En Presupuestos, usar un PDF nuevo y uno archivado en listado y detalle. Repetir las rutas disponibles con JavaScript desactivado y ejecutar la matriz de escritorio en Chrome para Windows. Registrar dispositivo, versión, panel, formato y si el archivo se abrió o se guardó.
