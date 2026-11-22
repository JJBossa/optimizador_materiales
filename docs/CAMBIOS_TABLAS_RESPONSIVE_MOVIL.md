# Tablas de CutLess en teléfonos móviles

- Fecha de la revisión local: 22 de noviembre de 2026.
- Rama: `feature/tablas-responsive-movil`.
- Base: `b506e990ed9fc460be8db868c143334d30c7e01e`, verificado en `upstream/main`.
- Estado: pendiente de revisión y publicación.

## Problema

En teléfonos, varios listados mantenían las columnas del escritorio dentro de contenedores con desplazamiento horizontal. Para leer un monto o encontrar las acciones de una fila había que perder de vista el nombre del registro. Comparación fijaba un ancho mínimo de 650 px y el catálogo de piezas, 560 px. Los formularios de Administración de usuarios y el selector al crear o editar proyectos ya tenían tratamientos propios.

## Inventario y solución

Se localizaron 24 declaraciones `<table>` en las plantillas del repositorio. Las tablas compartidas se cuentan una vez, aunque se rendericen en varias páginas. Las columnas siguientes conservan los datos y las acciones de cada tabla.

| Sección y plantilla | Columnas y controles | Diseño anterior y solución móvil |
| --- | --- | --- |
| Clientes · `lista_clientes.html` | Nombre y dirección, RUT, correo, teléfono, optimizaciones, historial, editar y eliminar. Buscador externo. | Contenedor desplazable. Tarjeta con identidad, correo y acciones en filas anchas. |
| Materiales propios y de sistema · `lista_materiales.html` (2) | Nombre y descripción, dimensiones, precio CLP, área y acciones según permisos. | Dos contenedores desplazables. Tarjetas para ambos catálogos. |
| Proyectos · `lista_proyectos.html` | Nombre, cliente, estado, cantidad, costo CLP, fecha, ver, editar y eliminar. Filtros externos. | Contenedor desplazable. Tarjetas con nombre y cliente independientes. |
| Presupuestos · `lista_presupuestos.html` | Número, cliente, fechas, total CLP, estado, detalle, editar y PDF. Filtros externos. | Contenedor desplazable. Tarjetas con número, cliente y acciones a todo el ancho. |
| Detalle de proyecto · `detalle_proyecto.html` | Optimización y fecha, tablero, aprovechamiento, cantidad, costo CLP y resultado. | Contenedor desplazable. Tarjetas por optimización. |
| Detalle de presupuesto · `detalle_presupuesto.html` (2) | Optimización y fecha, dimensiones, aprovechamiento, cantidad y resultado cuando corresponde. Desglose con concepto, cantidad, unitario, subtotal y total con `colspan`. | Dos contenedores desplazables. Tarjetas por optimización y concepto. Total en una fila con su único monto. |
| Historial de cliente · `historial_cliente.html` (2) | Optimizaciones con fecha, tablero, aprovechamiento, costo y resultado. Proyectos con nombre, estado, fechas, cantidad y acción. | Dos contenedores desplazables. Tarjetas en las dos tablas, con los enlaces previos. |
| Historial de costos · `historial_costos.html` | Fecha, dimensiones, material, tableros, aprovechamiento, tres costos CLP y resultado. Filtros, exportación y pie con `colspan`, promedio y totales. | Tabla ancha. Tarjetas por registro y pie separado con etiquetas para el promedio y cada monto. |
| Estadísticas · `estadisticas.html` | Posición y optimización, fecha, aprovechamiento, medidas, piezas y resultado. Selector de período externo. | Tabla desplazable. Tarjetas por posición. |
| Resultados · `resultado.html` | Tablero, piezas, área, desperdicio y aprovechamiento con barra. | Tabla dentro de un plegable. Tarjetas por tablero en el mismo plegable. |
| Detalle de piezas · `includes/board-layout.html` (2) | Catálogo: número, nombre, medidas y unidad, cantidad, área y referencia. Plan antiguo: pieza, medidas y cantidad total. | Tablas dentro de contenedores. Tarjetas para ambas variantes, también en los visores que reutilizan el fragmento y en el HTML del endpoint de Historial. |
| Carga de piezas · `includes/optimization-loading-block.html` | Esqueleto de las seis columnas de detalle, insertado al mostrar la carga. | Tabla temporal. Columnas ajustadas al ancho del visor y esqueleto excluido del árbol accesible. |
| Comparación · `comparar_optimizaciones.html` (3) | Métricas A y B y diferencia B − A. Condiciones A y B. Piezas con medidas y cantidades A/B, con estado vacío de cuatro columnas. | Ancho mínimo de 650 px. Las tres conservan filas y columnas visibles, con anchos fijos relativos y texto que envuelve. |
| Cálculo de tiempos · `calcular_tiempo.html` | Concepto, minutos, porcentaje y total. Parámetros en formulario separado. | Tabla de tres columnas. Tarjetas por concepto y total diferenciado. El nombre de optimización del encabezado y el resumen también puede envolver a 575 px o menos. |
| Asociar optimizaciones · `agregar_optimizaciones_proyecto.html` | Seleccionar toda la página, casillas individuales, fecha, dimensiones, aprovechamiento, tableros, costo y resultado. Formulario con búsqueda, paginación, selección conservada y fila vacía con `colspan`. | Tabla desplazable. Tarjetas con la casilla junto a la identidad. La cabecera conserva la casilla original y muestra su etiqueta en móvil. |
| Selector compartido · `includes/optimization-plan-selector.html` | Casilla y optimización con fecha, tablero, aprovechamiento, cantidad y consulta. Búsqueda, paginación, selección persistente, filas ocultas y estados vacíos de seis columnas. | En proyectos ya usaba tarjetas hasta 767 px y sigue usando esas reglas. En presupuestos, tarjetas hasta 575 px. En proyectos, el nombre largo ahora puede ocupar varias líneas solo en teléfonos. |
| Administración de usuarios · `usuarios/admin_dashboard.html` | Identidad y correo, rol editable, estado, editar y eliminar según permisos. Búsqueda y paginación. | Conserva las tarjetas existentes hasta 767 px y añade roles explícitos en la estructura que cambia de presentación. |
| Impresión del plan · `imprimir_plan_corte.html` | Referencia, pieza, medidas y cantidad. | Conserva la plantilla y `imprimir_plan_corte.css`. |

El historial principal, el editor de piezas y las plantillas reutilizables de trabajos usan tarjetas o formularios. El selector y los visores generan contenido a partir de las plantillas inventariadas. La administración técnica de Django en `/admin/` usa sus propias plantillas y estilos responsive de Django. La administración de usuarios de CutLess sí forma parte de este cambio. La generación de PDF y Excel permanece fuera del alcance.

## Implementación y archivos

- `cut/cutless/static/cutless/css/mobile-tables.css` concentra los estilos para `.mobile-table-cards`, `.mobile-table-comparison` y `.mobile-table-placeholder`. Se carga desde `cut/cutless/templates/cutless/base.html`. El resto de estilos continúa en `management-refinement.css`, `analysis-refinement.css`, `estadisticas.css`, `calcular_tiempo.css`, `board-landscape.css`, `resultado.css`, `history-result-refinement.css`, `project-selection.css` y `budget-selection.css` según la sección. Los estilos nuevos de distribución se limitan a `screen` y `max-width: 575px`.
- Las plantillas modificadas son las de la tabla de inventario, excepto la de impresión. Las etiquetas de las tarjetas son texto HTML visible. Los encabezados de la tabla y la relación con las celdas se conservan para la lectura accesible. Se mantiene una sola fila y una sola copia de cada control. Las celdas, insignias y acciones permiten envoltura. Las filas `[hidden]` permanecen ocultas.
- `cut/cutless/tests/browser/tablas-movil.cjs` compara ambas versiones con Playwright. `cut/cutless/tests/browser/fixtures-tablas-movil.py` prepara una cuenta, contactos, materiales, planes y un presupuesto de prueba en SQLite vacía. No se añadieron dependencias a la aplicación.
- `README.md` enlaza el informe. `docs/REGISTRO_CAMBIOS_NOVIEMBRE_2026.md` registra el trabajo local.

## Validación de la implementación inicial

| Prueba | Resultado |
| --- | --- |
| Chromium 156 a 320, 360, 390, 430 y 575 px, en claro y oscuro | 170 combinaciones de ancho, tema y sección aprobadas. Se midió el ancho del documento, de las tablas y de sus contenedores. Comparación conservó sus columnas. |
| Chromium 156 a 576, 768 y 1280 px, en claro y oscuro | 102 comparaciones con la base sin diferencias en la geometría de las tablas, los textos y las columnas. Las dos capturas del listado de Clientes a 1280 px son idénticas byte por byte. |
| Flujos de Chromium a 320 px | Selección de una optimización en Presupuestos, cambio de página, búsqueda sin resultados y conservación de la casilla. En Proyectos, foco de teclado, seleccionar la página completa, búsqueda y asociación real de registros sintéticos. También se guardó una edición de cliente, se consultó su historial y se eliminó un cliente de prueba. Se verificaron la paginación y el estado vacío de Administración y la apertura de la tabla de impresión. |
| Desgloses CLP a 390 px | Coincidieron todos los importes del detalle de presupuesto y los totales del historial de costos. En el ejemplo, el presupuesto mostró un total de `$49.397.246` en las dos versiones. |
| Django con SQLite local | 389 aprobadas, 6 omitidas por requerir `select_for_update` y 0 fallidas. |
| Django con PostgreSQL 16.2 por socket Unix | 395 aprobadas, 0 omitidas y 0 fallidas. |
| Node | 65 pruebas de la aplicación y 8 del Worker simulado aprobadas. |

Las capturas se guardaron fuera del repositorio. La referencia y el cambio se sirvieron con los mismos registros sintéticos y Bootstrap 5.3.0 local. La comparación automatizada fija el momento de carga de las fuentes con `font-display: swap` solo en la prueba, ya que la configuración `optional` puede mostrar una fuente de respaldo en una de las visitas. Se deja fuera la posición vertical absoluta, que depende del contenido anterior a la tabla. Se comparan alto, ancho, anchos de celdas, textos visibles, `colspan` y ancho de los contenedores.

## Revisión final

- El inventario conserva 24 declaraciones: 18 con tarjetas en alguna variante, 3 tablas de comparación, 1 de carga, 1 de Administración de usuarios y 1 de impresión. El selector compartido conserva sus variantes de Proyectos y Presupuestos en una misma plantilla.
- Los cambios de distribución se aplican solo en pantalla hasta 575 px. Por encima de ese ancho, la hoja nueva solo oculta las etiquetas adicionales. Se mantienen los estilos previos del selector de Proyectos y de Administración a 767 px, y sus ajustes de anchura y espaciado hasta 1023 px. Se retiró una regla duplicada de `[hidden]` que ya aportaba `budget-selection.css`. Bootstrap conserva sus indicadores de foco y las clases de estado. Se comprobó que las etiquetas, casillas y enlaces mantienen el orden del HTML y los selectores que usa JavaScript.
- En el detalle de Presupuestos y el Historial de costos, las etiquetas de las filas de totales eran celdas genéricas. Ahora se exponen como encabezados de fila (`role="rowheader"`) y mantienen `colspan="3"` y `colspan="4"`, respectivamente. Los valores permanecen en sus celdas originales. Las etiquetas visuales repetidas se omiten del árbol accesible para que se conserve la lectura con encabezados de columna.
- La prueba de navegador comprueba esos roles y `colspan`, compara todos los importes CLP visibles de los dos desgloses con la base a 320 px y prueba la activación mediante `label`, el orden de Tab y el formato de tabla al emular impresión. Las comprobaciones se suman a los flujos de selección, paginación, edición, consulta y eliminación.
- El generador solo admite SQLite en desarrollo y sin usuarios. Se comprobó que rechaza reutilizar esa base. El archivo de sesión sintética se crea con permisos `0600`, incluso con `umask 022`. Playwright usa orígenes de bucle local, Bootstrap local, bloquea los service workers y rechaza redirecciones en la carga interna de fuentes. Los contextos y el navegador se cierran al terminar. La matriz y el flujo con escritura usaron copias separadas. En estos servidores locales, la consulta externa de indicadores se sustituyó por una respuesta vacía de prueba.
- El diff contiene plantillas, una hoja de estilos, pruebas y documentación. Al comparar las 18 plantillas modificadas con la base, coincidieron los destinos de enlaces, las URLs de Django, los formularios y sus controles. Los modelos, las migraciones, las consultas, las dependencias, los generadores PDF y Excel, la plantilla de impresión y los demás worktrees quedaron intactos.

| Prueba repetida | Resultado de la revisión final |
| --- | --- |
| Chromium 156 a 320, 360, 390, 430 y 575 px, en ambos temas | 170 verificaciones aprobadas. A 320 px se mantuvieron los `colspan` y todos los importes CLP visibles de Presupuestos y Costos coinciden con la base. |
| Chromium 156 a 576, 767, 768, 1023, 1024 y 1280 px, en ambos temas | 204 comparaciones aprobadas. El tamaño de las tablas, los anchos de las celdas y sus textos visibles coinciden con la base en las 17 secciones. |
| Flujos de Chromium a 320 px | Pasaron el clic en la etiqueta de una casilla, la secuencia de Tab, la selección entre páginas y el flujo con escrituras sobre la copia desechable. La impresión conservó `display: table`. |
| Comprobación negativa en Clientes y Presupuestos a 320 px | La base desbordó su contenedor de Clientes en 2087 px y no expuso «TOTAL» como encabezado de fila. La rama dejó el desbordamiento en 0 px y expuso un encabezado «TOTAL». |
| Muestra de contraste en Clientes a 320 px | La etiqueta de tarjeta midió 7,33:1 en claro y 7,92:1 en oscuro frente al fondo de la fila. |
| Django en SQLite | 389 aprobadas, 6 omitidas por requerir `select_for_update`, 0 fallos. |
| Django en PostgreSQL 16.2 local por socket Unix | 395 aprobadas, 0 omitidas, 0 fallos. |
| Node | 65 pruebas de la aplicación y 8 del Worker simulado aprobadas, 0 fallos. |

### Hallazgo funcional preexistente

En la tabla **Proyectos** del historial del cliente, `cut/cutless/templates/cutless/historial_cliente.html`, línea 165, el enlace «Ver resultado» apunta a `href="#"`. La misma línea existe en el commit base `b506e990ed9fc460be8db868c143334d30c7e01e`. Queda pendiente definir un destino funcional en un cambio independiente.

## Cómo repetir la validación

Crear una base SQLite vacía fuera del repositorio y definir `CUTLESS_ENV=development`, `CUTLESS_DB_ENGINE=sqlite`, `CUTLESS_DB_PATH`, `CUTLESS_MEDIA_ROOT`, `CUTLESS_SECRET_KEY` sintética y `CUTLESS_TEST_FIXTURE` para un archivo nuevo en el mismo directorio temporal. Ejecutar con un entorno de pruebas que ya tenga las dependencias del proyecto.

```bash
umask 077
(cd cut && python manage.py migrate --noinput)
(cd cut && python manage.py shell < cutless/tests/browser/fixtures-tablas-movil.py)
```

Iniciar la base de referencia y la copia modificada en dos servidores locales con la misma SQLite, medios y clave sintética. Por defecto, el guion usa `http://127.0.0.1:8790` para la referencia y `http://127.0.0.1:8791` para la nueva. `CUTLESS_TEST_BASE` y `CUTLESS_TEST_ORIGIN` permiten cambiar los puertos. `CUTLESS_TEST_BOOTSTRAP` debe apuntar al prefijo de dos archivos locales de Bootstrap 5.3.0 (`.css` y `.js`). Usar Playwright disponible en Node y `CUTLESS_TEST_CHROMIUM` si se usa Chromium del sistema. `CUTLESS_TEST_EVIDENCE` permite guardar capturas. `CUTLESS_TEST_MUTATIONS=1` envía las operaciones de asociación, edición y eliminación sobre los datos sintéticos. Para repetir esa variante, preparar una base nueva.

Para incluir los bordes de 767 y 1023 px, usar `CUTLESS_TEST_WIDTHS=320,360,390,430,575,576,767,768,1023,1024,1280`. Al terminar, detener los dos servidores y retirar el directorio temporal con SQLite, los medios y la sesión sintética.

```bash
node cut/cutless/tests/browser/tablas-movil.cjs
(cd cut && python manage.py test cutless usuarios --noinput)
node --test cut/cutless/tests/js/*.test.cjs cut/cutless/tests/*.test.cjs cut/usuarios/tests_js/*.test.cjs cloudflare/recuperacion/worker.test.mjs
```

## Límites y reversión

- Chromium verifica roles, nombres accesibles y foco. Queda pendiente validar la navegación celda por celda y el anuncio de encabezados, en particular con `display: grid` y `colspan`, en Safari con VoiceOver y con otros lectores de pantalla. Los navegadores antiguos sin `:has()` pueden conservar el borde o desplazamiento del contenedor original.
- Antes de publicar, revisar el diff contra el commit base y retirar únicamente las modificaciones y archivos nuevos de esta rama si se decide revertir. Si el cambio se registra más adelante, revertir su commit completo. La reversión no requiere migraciones ni cambios de datos.
