# Auditoría del sistema de tutoriales de CutLess

## Estado de integración

La rama `fix/tutoriales-reapertura-responsive` parte de `main` del repositorio original en `5025a37`. La corrección está pendiente de revisión, fusión y despliegue.

## Reproducción y causa raíz

En la base local `4c50e06`, abrir Ayuda, llegar al último paso y volver a abrirla en la misma tarea del navegador que **Finalizar** dejaba una capa de Intro.js visible sin cuadro ni botones. Se reprodujo en Inicio, Historial, Estadísticas, Historial de costos y en los 36 recorridos de la matriz. En los cuatro paneles reportados, cerrar con la X, esperar 650 ms y reabrir funcionó. El caso de la X seguida de una reapertura con una sola llamada en la misma tarea tampoco produjo un bloqueo en esas cuatro pruebas. Varias llamadas inmediatas sí dejaron capas e instancias adicionales.

`mostrarGuia()` llamaba a `exit(true)` sobre `guiaActiva` y empezaba otra guía sin esperar. La finalización anterior aún podía ejecutar la limpieza de Intro.js 7.2.0, que busca y elimina capas compartidas del documento. Incluso cuando `exit()` ya resolvió, la capa de resaltado puede tardar 500 ms en retirarse por el fundido. Si la siguiente instancia la reutiliza en ese intervalo, la retirada anterior puede alcanzarla. Un cambio de paso también programa un repintado para 350 ms que la salida de Intro.js no cancela. El sombreado podía pertenecer a la capa de resaltado, aun cuando `.introjs-overlay` ya hubiera desaparecido. `buttons.js` decora los botones mediante un observador. La reproducción no implicó ese archivo ni requirió cambiar los valores de `z-index`.

En móvil, el posicionamiento lateral de Intro.js usaba coordenadas del elemento resaltado. Los pasos **Información Personal** y **Seguridad** en Perfil comenzaban en `x = −5 px` en los cuatro anchos medidos. También se midieron cuadros fuera del borde derecho en **Favoritos** de Historial, **Mejores resultados del período** de Estadísticas y **Tabla detallada** de Historial de costos. En Inicio, Resultado, creación de Presupuesto y creación de Proyecto hubo cuadros o controles por debajo del área visible.

## Cambios

- `cut/cutless/static/cutless/js/tutorial.js` serializa aperturas, navegación y cierres. Espera a que Intro.js retire la capa anterior, cancela el repintado diferido durante el cierre y libera la entrada de su propia instancia. El menú móvil y el modal de bienvenida completan su transición de Bootstrap antes de abrir la ayuda. Se mantienen Anterior, Siguiente, Finalizar, la X y Escape. El foco queda dentro del cuadro durante la guía y vuelve a su lanzador o al botón que abre el menú móvil al salir. Solo **Finalizar** registra la finalización de Inicio.
- `cut/cutless/static/cutless/css/help-redesign.css` fija el cuadro al área visible hasta 600 px de ancho, con márgenes laterales simétricos de al menos 12 px. Ajusta el texto al ancho y permite desplazarlo verticalmente. La flecha decorativa se oculta en este modo y el contorno del elemento destacado se conserva. Se reutilizan colores y tipografías de ambos temas.
- `cut/cutless/templates/cutless/base.html` actualiza la versión de la hoja de estilos compartida. `cut/cutless/templates/cutless/includes/tutorial-scripts.html` usa el controlador compartido y corrige referencias a filtros, tablas, acciones de creación, selectores de optimizaciones y botones de guardado, entre otros. Los pasos con elementos ausentes u ocultos se omiten. Si no quedan pasos, se muestra orientación sin un elemento destacado.
- `cut/cutless/templates/cutless/editar_optimizacion.html` dirige el botón de ayuda de costos a los campos de precio y mano de obra de la edición. `cut/cutless/templates/cutless/calcular_tiempo.html` identifica los parámetros de tiempo y el resumen de piezas que describe la guía.
- `cut/cutless/tests/test_tutorial_shell.py` comprueba la carga única del controlador y su exclusión de páginas anónimas o que ocultan la ayuda. `tools/tutorial/servidor.py` y `tools/tutorial/chromium.cjs` preparan los datos sintéticos y ejecutan los recorridos en el navegador con una contraseña generada para la sesión. `README.md` incorpora el informe al índice de documentación.

## Cobertura por panel

La columna «Base» corresponde a **Finalizar** y reabrir inmediatamente. La configuración inicial de la cuenta es un asistente distinto y oculta Intro.js expresamente. La bienvenida que sí arranca Intro.js se verifica por separado con una cuenta sintética nueva.

| Panel | Recorridos | Base |
| --- | --- | --- |
| Inicio | Ayuda general, dimensiones del tablero y piezas | Bloqueo en los 3 |
| Historial | Guía del historial | Bloqueo |
| Resultado | Guía de resultado | Bloqueo |
| Estadísticas | Guía de estadísticas | Bloqueo |
| Historial de costos | Guía de costos | Bloqueo |
| Presupuestos | Lista, creación, edición, detalle, edición de emitido y agregar optimizaciones | Bloqueo en los 6 |
| Proyectos | Lista, creación, edición, detalle y agregar optimizaciones | Bloqueo en los 5 |
| Clientes | Lista, creación, edición e historial del cliente | Bloqueo en los 4 |
| Materiales | Lista, creación y edición | Bloqueo en los 3 |
| Plantillas | Lista, creación y edición | Bloqueo en los 3 |
| Perfil | Preferencias y Cuenta y contraseña | Bloqueo |
| Configuración | Guía de configuración del sistema | Bloqueo |
| Comparación | Guía con dos optimizaciones cargadas | Bloqueo |
| Calculadora de tiempo | Guía de parámetros, piezas y estimación | Bloqueo |
| Editar optimización | Ayuda general, tablero, piezas y costos de la edición | Bloqueo en los 4 |

## Resultados en Chromium

Se recorrió cada paso y se revisaron los elementos destacados, el foco, los límites del cuadro, el ajuste de texto y el área accesible de los botones mediante `getBoundingClientRect()`. Al salir, la prueba espera que desaparezcan las capas y clases transitorias, verifica que se libere el registro de Intro.js y comprueba que el lanzador vuelva a aceptar clics. Los números de la base corresponden a 31 pasos de ocho pantallas en tema claro por ancho. Una incidencia se cuenta una vez por paso aunque se detectara más de un problema de geometría.

| Ancho | Base · incidencias en tema claro | Corregido · pasos claro / oscuro | Corregido · incidencias |
| --- | ---: | ---: | ---: |
| 320 px | 17 de 31 | 130 / 130 | 0 |
| 360 px | 17 de 31 | 130 / 130 | 0 |
| 390 px | 16 de 31 | 130 / 130 | 0 |
| 430 px | 14 de 31 | 130 / 130 | 0 |

- Escritorio a 1366 px. 130 pasos distintos. En los 36 recorridos pasaron cinco finalizaciones, cinco cierres mediante la X y un cierre mediante Escape por recorrido.
- Móvil. 288 combinaciones de guía, ancho y tema, con 1040 mediciones de pasos. En cada combinación pasaron la finalización, el cierre mediante la X y Escape.
- Las 36 pruebas de reapertura rápida pasaron con movimiento reducido y con transiciones normales. Con transiciones normales se verificó además volver a abrir después de Escape. También pasaron el cambio de página y regreso, Tab y Mayús+Tab, la ausencia de anclas, el área visible reducida, el texto largo desplazable y la bienvenida. Cerrar el último paso de bienvenida no hizo el POST de finalización. Finalizar con el teclado hizo un solo POST con CSRF válido y recibió HTTP 200.
- Con transiciones normales también pasaron cinco recorridos en escritorio y sus 40 combinaciones móviles. Se repitieron Inicio, Historial, Estadísticas, Historial de costos y las dimensiones del tablero en edición.
- Django con SQLite temporal. 366 pruebas detectadas, 360 aprobadas y 6 omitidas porque requieren bloqueo de filas. La suite detectó que los primeros selectores de creación introducían rutas de herramientas ocultas en el HTML. Se corrigieron para buscar las acciones disponibles en el DOM y la regresión volvió a pasar.
- JavaScript. 36 pruebas aprobadas, sin fallos ni omisiones. `node --check` y `git diff --check` terminaron sin errores.

## Caso adicional en móvil · Configuración del sistema

Se recorrieron los seis pasos desde **Ayuda** en `/usuarios/configuracion-sistema/`. En la base local `4c50e06`, con un viewport de 390 × 664 px, los tres últimos pasos empezaban en `x = −5 px`. **Guardar Configuración** tenía 37 px de separación a la derecha y un alto de 317 px. Intro.js calculaba la posición del cuadro absoluto a partir de la referencia del control resaltado. El error también aparecía en otros pasos del mismo recorrido.

El primer ajuste compartido ya dejaba 12 px a cada lado al 100 %, pero seguía usando `100vw` para calcular el ancho. Con zoom al 150 %, el área verdaderamente visible se reducía a 260 px de ancho y el cuadro anterior sobresalía 118 px hacia la derecha. El controlador ahora toma ancho, alto y desplazamiento de `VisualViewport` y los actualiza al cambiar el tamaño o desplazar la vista. El CSS compartido conserva márgenes simétricos, reduce el espacio de los controles y limita la altura del texto para que se pueda leer mediante desplazamiento. El cambio usa las mismas reglas en todos los pasos y conserva la paleta, tipografía y estilos de foco de ambos temas.

| Escenario de «Guardar Configuración» | Área visible | Posición del cuadro (x, y) | Tamaño del cuadro | Márgenes izq. / der. |
| --- | ---: | ---: | ---: | ---: |
| Chromium con perfil iPhone 13, al 100 % | 390 × 664 px | 12, 363 px | 366 × 289 px | 12 / 12 px |
| Chromium con altura reducida | 390 × 300 px | 12, 52 px | 366 × 236 px | 12 / 12 px |
| Chromium con zoom al 150 % | 260 × 442,7 px | 12, 56,6 px | 236 × 374,1 px | 12 / 12 px |
| WebKitGTK en marco de 390 × 664 px | 382 × 664 px | 12, 367 px | 358 × 285 px | 12 / 12 px |

Las 32 mediciones en Chromium incluyeron ambos temas, los seis pasos y la comprobación mediante `elementFromPoint()` del centro de cada control visible. En la prueba de desplazamiento de página el cuadro conservó su posición. Con la altura reducida se desplazó el texto dentro del cuadro y sus botones siguieron accesibles. Se probó **Anterior** y se volvió a avanzar hasta **Guardar Configuración**. También se reabrió inmediatamente después de **Finalizar**, la **X** y **Escape**. En cada reapertura se comprobó que había una sola instancia y que la guía volvía al primer paso.

La red del entorno bloqueó la descarga de WebKit de Playwright con HTTP 403. Se completó una verificación adicional con WebKitGTK 2.52.6 en Linux y agente de usuario de iPhone, dentro de un marco local de 390 × 664 px. La barra de desplazamiento del motor dejó 382 px de ancho visible. En ambos temas pasaron los seis pasos, la navegación hacia atrás, el desplazamiento de la página y las reaperturas inmediatas después de las tres formas de cierre. Se midieron 24 estados en total. Queda pendiente comprobar Safari en un iPhone físico, incluidas sus barras dinámicas y zonas seguras.

Tras el ajuste pasaron las 288 combinaciones de la matriz móvil compartida en Chromium, con 1040 mediciones de pasos. El servidor de prueba serializa sus peticiones para evitar contención entre los contextos del navegador sobre SQLite temporal. También pasaron las 13 pruebas Django de ayuda y dimensiones, las 36 pruebas JavaScript y `git diff --check`.

La validación final sobre `5025a37` volvió a ejecutar las suites Django y JavaScript, la matriz móvil completa, el modo `configuracion` y las reaperturas rápidas de Inicio, Historial, Estadísticas, Historial de costos y Configuración del sistema.

## Reproducir la validación

Desde la raíz del repositorio, usar Python con las dependencias de Django del proyecto instaladas y Chromium local. El servidor solo escucha en `127.0.0.1`, fuerza SQLite temporal, crea datos sintéticos y deshabilita el correo y el consumidor de recuperación. La prueba de navegador permite la aplicación local y las versiones fijadas de Bootstrap e Intro.js. Para trabajar con copias locales de esos recursos, `TUTORIAL_ASSETS` acepta una carpeta con `bootstrap.min.css`, `bootstrap.bundle.min.js`, `introjs.min.css` e `intro.min.js`.

```bash
export TUTORIAL_TEST_PASSWORD="$(python -c 'from secrets import token_urlsafe; print(token_urlsafe(24))')"
python tools/tutorial/servidor.py &
```

En la misma terminal, ejecutar las pruebas para que hereden la contraseña temporal. Se necesitan Node.js, npm y Playwright. `CHROMIUM_BIN` admite una ruta distinta para Chromium.

```bash
npm install --prefix /tmp/cutless-browser playwright@1.62.1
NODE_PATH=/tmp/cutless-browser/node_modules \
TUTORIAL_ARTIFACTS=/tmp/cutless-resultados \
node tools/tutorial/chromium.cjs todas
```

Los modos `desktop`, `movil` y `especial` permiten ejecutar las verificaciones por separado. Se pueden indicar nombres de recorridos después del modo. La matriz usa movimiento reducido por defecto. Con `TUTORIAL_MOTION=no-preference` se prueban las transiciones normales. Reiniciar el servidor temporal antes de repetir `especial` o `todas`, porque la prueba de bienvenida guarda la finalización en su cuenta sintética.

El modo `configuracion` ejecuta el caso adicional con el perfil iPhone 13 de Playwright en ambos temas. `TUTORIAL_BROWSER=webkit` permite usar WebKit donde esté disponible. La simulación de zoom del gesto pertenece a Chromium.

```bash
NODE_PATH=/tmp/cutless-browser/node_modules \
TUTORIAL_ARTIFACTS=/tmp/cutless-configuracion \
node tools/tutorial/chromium.cjs configuracion

/tmp/cutless-browser/node_modules/.bin/playwright install webkit
NODE_PATH=/tmp/cutless-browser/node_modules TUTORIAL_BROWSER=webkit \
TUTORIAL_ARTIFACTS=/tmp/cutless-configuracion-webkit \
node tools/tutorial/chromium.cjs configuracion
```

Para repetir la reproducción de la base, extraer `cut/` de `4c50e06` con `git archive` en una carpeta temporal, copiar allí `tools/tutorial/servidor.py` con su misma ruta, iniciar ese servidor con `--puerto 8776` y ejecutar el cliente de esta revisión con `TUTORIAL_BASE_URL=http://127.0.0.1:8776` y el modo `base`.

```bash
CUTLESS_ENV=development CUTLESS_DB_ENGINE=sqlite CUTLESS_DB_PATH=:memory: \
CUTLESS_SECRET_KEY="$(python -c 'from secrets import token_urlsafe; print(token_urlsafe(48))')" \
CUTLESS_BREVO_RECOVERY_ENABLED=false \
CUTLESS_RECOVERY_QUEUE_CONSUMER_ENABLED=false \
python cut/manage.py test cutless usuarios --noinput
node --test cut/cutless/tests/js/*.test.cjs
git diff --check
```

## Límites de la revisión

Se probó con Chromium 156.0.8078.79 e Intro.js 7.2.0. Se simuló un área visible reducida de 320 × 320 px y se desplazó un texto largo dentro de la guía. La aparición del teclado virtual nativo requiere un dispositivo físico. Tampoco se realizaron pruebas con un lector de pantalla. Si se actualiza Intro.js, repetir las pruebas de carrera y de geometría porque el controlador depende de la retirada diferida de su capa y del temporizador interno de repintado de esta versión.
