# Navegación de los visores de Estadísticas e Historial

- Fecha de validación: 22 de noviembre de 2026.
- Rama: `fix/navegacion-modales-estadisticas-historial`.
- Base: `175433f688eb469de163d16a9cd953b997040d08` (`upstream/main`, con el PR #14).
- Estado de GitHub al 22/11/2026: commit [`b8f7474`](https://github.com/JJBossa/optimizador_materiales/commit/b8f74743a35413ec4fa3107fcc202cc97a529213) publicado en el fork; [PR #15](https://github.com/gy0kuroo/optimizador_materiales/pull/15) abierto contra `main`, aún sin fusionar y no marcado como borrador. El despliegue de esta corrección no está verificado.

## Problema

En Chromium, entrar a Estadísticas desde Presupuestos, ampliar cualquiera de los gráficos y pulsar Atrás devolvía a Presupuestos. Entrar a Historial desde Inicio, pulsar «Ampliar imagen» y luego Atrás devolvía a Inicio. En los tres casos, al abrir el modal Bootstrap no se añadía una entrada al historial del navegador. Atrás seguía apuntando a la página anterior.

El fallo ya existía antes del cambio de Django. Las plantillas y el JavaScript implicados son iguales entre `6087aa322653793606d08f520653d374d1caf7e8` (referencia anterior a SEC-01) y la base de esta rama. El visor de Resultados ya gestionaba su propia navegación y se usó como referencia.

## Cambios

- Cada visor guarda una entrada de historial con la misma URL, incluidos el período, la búsqueda, el orden y la página. El estado identifica el gráfico o el tablero mediante una clave propia y conserva las demás propiedades de `history.state`. Una apertura sobre esa entrada o un cambio de tablero la actualiza con `replaceState`.
- Atrás cierra el visor. Los botones de cierre, Escape y el clic en el fondo siguen ese recorrido cuando existe una entrada válida del visor. Si el visor ya está cerrado, Atrás continúa su navegación habitual.
- En la revisión final se comprobó que confiar en el elemento activo al abrir dejaba el foco sin un destino fiable tras la recarga. Ahora el visor busca el control correspondiente al gráfico o tablero abierto y le devuelve el foco sin desplazar la página. Estadísticas usa el filtro de período como alternativa mientras la miniatura no esté disponible. En Historial, el control «Ampliar imagen» admite Tab para recibir el foco y Enter o Espacio para abrir.
- Adelante o una recarga restauran la selección válida. `popstate` y `pageshow` ajustan el modal al estado de la entrada actual. Un estado con URL distinta, gráfico desconocido o sin un control de apertura para ese tablero queda inactivo. Si el usuario vuelve a abrir desde esa misma entrada obsoleta, se reutiliza sin añadir otra. El endpoint existente resuelve la disponibilidad efectiva del tablero.
- Estadísticas conserva el reintento y reutiliza el gráfico HD descargado o la solicitud en curso durante la visita. Una respuesta tardía queda descartada para el modal cerrado. Historial cancela la solicitud al cerrar y descarta los resultados de una apertura anterior. Continúa usando su caché dentro de cada apertura.

## Archivos

| Archivo | Cambio |
| --- | --- |
| [`modal-history.js`](../cut/cutless/static/cutless/js/modal-history.js) | Gestiona la entrada de historial y su sincronización con Bootstrap. |
| [`estadisticas.html`](../cut/cutless/templates/cutless/estadisticas.html) | Identifica el gráfico activo y protege la actualización asíncrona del modal HD. |
| [`historial.html`](../cut/cutless/templates/cutless/historial.html) | Identifica los controles de apertura y conecta los botones de cierre. |
| [`history-board-viewer.js`](../cut/cutless/static/cutless/js/history-board-viewer.js) | Restaura la optimización y el tablero y conserva la cancelación de cargas. |
| [`correlativos.test.cjs`](../cut/cutless/tests/js/correlativos.test.cjs) | Añade un doble de `createModalHistory` al test que carga `history-board-viewer.js` solo en Node. `open` invoca el render y `isOpen` permite que continúe la carga simulada. Las aserciones siguen verificando el ID de descarga y el código mostrado. |
| [`navegacion-visores.cjs`](../cut/cutless/tests/browser/navegacion-visores.cjs) | Recorre los casos de navegación con Chromium y Bootstrap. |
| [`README.md`](../README.md) | Enlaza este documento. |
| `docs/CAMBIOS_NAVEGACION_VISORES.md` | Registra la causa, la corrección y la revisión final. |

## Validación local

La prueba de navegador utiliza Django y SQLite aislados, una cuenta sintética y optimizaciones de prueba. Usa el JavaScript de Bootstrap y los endpoints locales para generar gráficos y cargar tableros. Intercepta determinadas solicitudes para dejar una carga pendiente al cerrar.

| Casos | Verificación en Chromium |
| --- | --- |
| A y B | Desde Presupuestos, abrir Aprovechamiento o Desperdicio. Atrás vuelve al panel de Estadísticas con el período semanal y el mismo desplazamiento. |
| C, G y H | Desde Inicio, abrir Historial con búsqueda, orden y página 2. Pasar al tablero 2 y volver con una sola acción de Atrás. Se conservan la URL, la búsqueda y el desplazamiento. |
| D y E | Adelante y una recarga restauran el gráfico o tablero correspondiente. Pasan los botones de cierre y Escape sin acumular entradas. El foco vuelve al control de apertura, incluso tras recargar. |
| F | Atrás cierra con una solicitud pendiente. Al avanzar, Estadísticas reutiliza una sola solicitud HD e Historial inicia una nueva tras cancelar la anterior. |
| I y J | Con el visor cerrado, Atrás navega a la sección anterior. En Resultados, Atrás cierra el visor existente y Adelante lo reabre. |

La ejecución anterior de la suite completa de Django en SQLite obtuvo 389 aprobadas, 6 omitidas por requerir `select_for_update` y 0 fallidas. La revisión final repitió 47 pruebas relacionadas en SQLite, todas aprobadas. También ejecutó la suite completa con PostgreSQL 16.2 aislado por socket Unix. Pasaron las 395 pruebas, incluidas las pruebas concurrentes, con 0 omitidas y 0 fallidas.

- Node aprobó 65 pruebas de la aplicación y 8 del Worker simulado, sin omisiones ni fallos. Se confirmó la necesidad del doble de prueba en una copia en memoria de `correlativos.test.cjs`: al retirarlo, el visor falla al inicializarse con `window.createModalHistory is not a function`.
- Playwright con Chromium 156 y Bootstrap 5.3.0 repitió los casos A–J. También verificó el foco y el teclado, la conservación de un estado de historial ajeno y la reutilización de una entrada obsoleta. En ambos paneles se confirmó la restauración desde la caché de navegación (`pageshow.persisted=true`). El siguiente Atrás cerró el visor y dejó visible el panel.
- El guion adicional de Estadísticas pasó a 390 y 1440 px en ambos temas, con Bootstrap servido localmente. Comprueba los reintentos ante error HTTP, fallo de red, tipo de respuesta inesperado y PNG inválido, el zoom y el cambio de período.

Estas comprobaciones de navegador se ejecutaron de forma automatizada. La revisión final no incluyó una sesión manual ni pruebas en otros navegadores.

### Repetir las pruebas

Ejecutar desde la raíz con dependencias instaladas y configuración local de SQLite. Para la prueba de Chromium, iniciar Django localmente y usar una sesión sintética con permiso de Estadísticas. Crear optimizaciones recientes con datos para los dos gráficos. La optimización indicada debe tener al menos dos tableros y aparecer en la segunda página del Historial al buscar `Tablero` y ordenar por fecha ascendente. Indicar el identificador en `CUTLESS_TEST_PLAN` y proporcionar la cookie sintética mediante `CUTLESS_TEST_SESSION` en la terminal local.

```bash
(cd cut && python manage.py test cutless usuarios --noinput)
node --test cut/cutless/tests/js/*.test.cjs cut/cutless/tests/*.test.cjs cut/usuarios/tests_js/*.test.cjs cloudflare/recuperacion/worker.test.mjs
CUTLESS_TEST_ORIGIN=http://127.0.0.1:8779 node cut/cutless/tests/browser/navegacion-visores.cjs
```

Playwright debe estar disponible para Node. `CUTLESS_TEST_CHROMIUM` permite indicar el ejecutable de Chromium. Si se desea aislar las dependencias de CDN, `CUTLESS_TEST_BOOTSTRAP` admite el prefijo común de dos archivos locales, `<prefijo>.js` para el bundle y `<prefijo>.css` para la hoja de Bootstrap.

## Límites, publicación y reversión

- La restauración depende de que la URL y la entrada de historial del navegador sigan disponibles. Un tablero eliminado puede mostrar el error recuperable del visor al solicitarlo de nuevo.
- La validación de navegación usa Chromium local. El comportamiento de restauración puede variar según la disponibilidad de la caché de navegación en cada navegador.
- El commit y el PR ya están publicados para revisión, sin fusionar. Render tiene Auto Deploy habilitado según lo informado. Antes de fusionar el PR, el administrador debe confirmar la rama vinculada al servicio, el plan de reversión y las verificaciones posteriores al despliegue; la etiqueta `[skip preview]` en el título no desactiva Auto Deploy al fusionar.
- Para revertir antes de publicar, revisar el diff contra el commit base y restaurar únicamente los cambios de esta corrección en los archivos rastreados. Retirar los tres archivos nuevos cuando se haya comprobado que contienen solo el trabajo de esta rama. Una vez registrada la corrección, revertir su commit completo con `git revert <SHA>` previa autorización. La reversión no requiere migraciones ni restaurar datos.
