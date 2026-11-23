# UX-01, PRE-01 y VIS-01 en CutLess

La rama `fix/ux01-pre01-modal-fechas` parte de `upstream/main` en `a43a5264dc3d951271b4ebe544830a9624b8f6ef`, SHA contrastado con la referencia remota antes de crear la rama. Esa revisión incorpora CLI-02. [PR #26](https://github.com/gy0kuroo/optimizador_materiales/pull/26)

## UX-01 · Aviso de dirección histórica

En Chromium, el diálogo aparecía en la esquina superior izquierda. El selector universal de `main.css` establece `margin: 0` y prevalecía sobre el margen automático que usa el navegador para centrar un `<dialog>` modal. Las capturas de la base registraron `x = 0` e `y = 0` a 390 y 1280 px.

`management-refinement.css` restaura `margin: auto` para `.cliente-direccion-dialogo` y permite desplazar el contenido dentro del diálogo. El ancho conserva un máximo de 36 rem y márgenes laterales. La altura máxima deja 1 rem arriba y abajo mediante `100dvh`, con `100vh` como respaldo. `editar_cliente.html` renueva la versión de la hoja para que el navegador solicite el CSS actualizado.

El diálogo nativo conserva el fondo oscurecido, las etiquetas accesibles y las acciones. Chromium comprobó el foco inicial en «Continuar al formulario», Tab y Shift+Tab, Escape, el retorno al país o a «Revisar aviso» según la acción, y el enlace al listado. Con JavaScript desactivado, el aviso sigue en línea. Guardar una ficha con dirección legada activa sigue exigiendo completar la nueva dirección. [Prueba de Chromium](../cut/cutless/tests/browser/direcciones-clientes.cjs)

| Viewport | Antes | Después |
| --- | --- | --- |
| Móvil, 390 × 844 | [Aviso arriba a la izquierda](evidencia/ux01-pre01/ux-antes-390.png) | [Aviso centrado](evidencia/ux01-pre01/ux-despues-390.png) |
| Escritorio, 1280 × 920 | [Aviso arriba a la izquierda](evidencia/ux01-pre01/ux-antes-1280.png) | [Aviso centrado](evidencia/ux01-pre01/ux-despues-1280.png) |

## PRE-01 · Fecha de validez al crear presupuestos

El campo de fecha comprobaba la presencia y el formato. El formulario aceptaba fechas anteriores al día actual y el control HTML carecía de `min`.

`forms/budgets.py` valida `fecha_validez` al crear. Calcula el día civil con `timezone.localdate()` y la zona predeterminada de Django, `America/Santiago`. El formulario nuevo propone hoy y fija esa fecha como `min`. Al validar un envío, Django vuelve a consultar el día vigente. Las pruebas congelan el reloj a ambos lados de la medianoche chilena, en horario de verano e invierno y con UTC como zona activa.

Una fecha anterior muestra «La fecha de validez no puede ser anterior a hoy. Selecciona la fecha actual o una posterior.». `crear_presupuesto.html` vincula el texto de ayuda y el mensaje del campo mediante los identificadores que usa Django para `aria-describedby`. La respuesta conserva el formulario vinculado al POST y sus selecciones. La vista ya condiciona la creación de clientes, la numeración, el guardado y la notificación a que el formulario sea válido. [Pruebas de Django](../cut/cutless/tests/test_presupuestos.py) · [Pruebas de Chromium](../cut/cutless/tests/browser/fecha-presupuestos.cjs)

Las ediciones con una instancia existente mantienen sus reglas. Se comprobó la edición de un borrador con fecha pasada y la consulta de un presupuesto histórico vencido con su PDF archivado, comparado byte a byte. Los recorridos de alta desde una optimización validan asociaciones, cálculos y la generación de la instantánea al guardar como «Enviado».

| Viewport | Antes | Después |
| --- | --- | --- |
| Móvil, 390 × 844 | [Fecha anterior aceptada por el control](evidencia/ux01-pre01/pre-antes-390.png) | [Error del servidor y fecha conservada](evidencia/ux01-pre01/pre-despues-390.png) |
| Escritorio, 1280 × 920 | [Fecha anterior aceptada por el control](evidencia/ux01-pre01/pre-antes-1280.png) | [Error del servidor y fecha conservada](evidencia/ux01-pre01/pre-despues-1280.png) |

## VIS-01 · Etiquetas de estado de Proyectos

Planificación, En Proceso, Completado y Cancelado tomaban el ancho de su texto y del relleno compartido. El listado y el detalle aplican ahora la clase `proyecto-estado` al badge existente. El ancho de `7.5em` se ajusta a la tipografía y el máximo del 100 % respeta el espacio del contenedor. Flexbox centra el texto en ambos ejes. El relleno horizontal deja espacio para «Planificación» y se conservan el alto de línea, el relleno vertical, la tipografía, el fondo y el borde de cada estado.

Entre 576 y 991 px, el listado de Proyectos usa menos relleno lateral en las celdas y permite que los textos y la columna de acciones se ajusten al ancho disponible. Esto conserva la tabla en tablet y las tarjetas existentes en móvil. El cambio se limita a las etiquetas de estado y a la tabla del listado de Proyectos. [Prueba de Chromium](../cut/cutless/tests/browser/estados-proyectos.cjs)

En el listado, las etiquetas medían entre 99,75 y 117,44 px de ancho. Con el ajuste, las cuatro miden 120 × 42 px en el listado y el detalle a 320, 390, 768 y 1280 px, tanto en tema claro como oscuro. A 768 px, el desbordamiento del contenedor de la tabla pasó de 134 a 0 px.

| Viewport y tema | Antes | Después |
| --- | --- | --- |
| Móvil, 390 × 844, claro | [Cuatro estados](evidencia/ux01-pre01/vis01-antes-390.png) | [Cuatro estados alineados](evidencia/ux01-pre01/vis01-despues-390.png) |
| Escritorio, 1280 × 920, oscuro | [Cuatro estados](evidencia/ux01-pre01/vis01-antes-1280.png) | [Cuatro estados alineados](evidencia/ux01-pre01/vis01-despues-1280.png) |

Para repetir la medición, cargar `fixtures-estados-proyectos.py` en una SQLite vacía. Ejecutar `estados-proyectos.cjs` con `CUTLESS_TEST_FIXTURE`, `CUTLESS_TEST_ORIGIN` y `CUTLESS_TEST_BOOTSTRAP`. Para comparar con la revisión anterior (`32da65ce730864c7a328d1f157d0550c4904d146`), usar `CUTLESS_TEST_BASE` con un segundo servidor local y los mismos datos y clave de sesión de desarrollo.

## Verificación local de UX-01 y PRE-01

Python 3.13.12, Django 5.2.19, SQLite 3.50.4, PostgreSQL 16.16 local, Node.js 24.22.1 y Chromium 156.0.8078.79 con `es-CL`. Chromium usó cuentas y datos sintéticos, un servidor en loopback y una copia local de Bootstrap. Las solicitudes fuera del origen local se bloquearon o se sirvieron desde esa copia.

| Prueba | Aprobadas | Omitidas |
| --- | ---: | ---: |
| Django completa · SQLite | 467 | 8 |
| Django completa · PostgreSQL | 475 | 0 |
| Clientes, Presupuestos, permisos, asociaciones, exportación y NUM-01/02/03 · SQLite | 136 | 3 |
| Mismas regresiones · PostgreSQL | 139 | 0 |
| PRE-01 dirigido · SQLite | 8 | 0 |
| Node | 67 | 0 |
| Worker simulado | 8 | 0 |
| Chromium UX-01 · 320, 390, 768 y 1280 px, con y sin JavaScript | 8 recorridos | 0 |
| Chromium PRE-01 · 390 y 1280 px, con y sin JavaScript | 4 recorridos | 0 |
| Chromium NUM-01 y NUM-03 · con y sin JavaScript | 2 recorridos y 20 casos | 0 |
| `makemigrations --check --dry-run` en SQLite y PostgreSQL | Sin cambios | |
| `git diff --check` | Sin incidencias | |

UX-01 también pasó el caso de 320 × 240 px con desplazamiento dentro del diálogo. Las omisiones de SQLite corresponden a pruebas que requieren `select_for_update`, ejecutadas en PostgreSQL. La entrega carece de cambios de esquema y de migraciones nuevas.

Para reproducir las suites Django, ejecutar `python manage.py test --noinput` desde `cut/` con la configuración de desarrollo de cada motor y bases locales. Para Chromium, aplicar las migraciones existentes en una SQLite desechable. Cargar `fixtures-direcciones-clientes.py` en una base vacía y luego `fixtures-fecha-presupuestos.py` mediante `python cut/manage.py shell`, con un `CUTLESS_TEST_FIXTURE` nuevo para cada archivo. Iniciar Django en `127.0.0.1`, configurar `CUTLESS_TEST_ORIGIN` y `CUTLESS_TEST_BOOTSTRAP`, y ejecutar los dos recorridos de navegador con Playwright usando el JSON de cada caso. `CUTLESS_TEST_CHROMIUM` permite elegir el ejecutable y `CUTLESS_TEST_EVIDENCE` el directorio de capturas.

## Archivos modificados

- UX-01 actualiza el CSS de gestión, la plantilla de edición de clientes, las pruebas de navegador de CLI-02 y las capturas del aviso.
- PRE-01 actualiza el formulario de presupuestos, la plantilla de alta, las pruebas Django de presupuesto y las fechas de alta de algunas pruebas existentes de contacto, direcciones, CLP e indicadores. Añade el recorrido de navegador, los datos sintéticos y las capturas del campo de fecha.
- El README y el registro mensual enlazan este informe.

## Límites de la verificación

- Las dimensiones y el desplazamiento se probaron en Chromium, con alturas de viewport controladas. La interfaz del calendario y las barras dinámicas de los navegadores móviles físicos quedan fuera de esa comprobación.
- La etiqueta visual «Vencido» de lista y detalle se calcula con UTC en `Presupuesto.esta_vencido()`. Durante las horas en las que UTC ya pasó de día y Chile aún no, un presupuesto con validez hasta hoy en Chile puede mostrar esa etiqueta. PRE-01 aplica la fecha civil de Chile al alta. La política existente de visualización es independiente de esta validación.
