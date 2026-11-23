# VIS-02 · Acciones de gestión de CutLess

La revisión parte de `fd2594215ea931a92e6dab8ceac837add4fab3ec` en `fix/ux01-pre01-modal-fechas`. La base de `upstream/main` era `a43a5264dc3d951271b4ebe544830a9624b8f6ef`.

«Ver detalle», «Ver historial» y «Editar» mezclaban `btn-sm` con el botón normal dentro de un mismo patrón de fila. El ancho dependía del texto y algunos grupos empujaban la acción destructiva al final mediante un margen automático. En Historial, `flex-fill` distribuía el espacio entre Editar y Duplicar, mientras el desplegable vivía en un contenedor independiente. El pseudo-elemento vacío del desplegable también ocupaba espacio.

La clase `management-action-set` adopta el botón normal de CutLess, con **44 px de alto** con texto en una línea, tipografía de **14 px**, relleno de **10 × 18 px**, radio de **11 px**, separación icono-texto de **8 px** y separación entre botones de **12 px** con fuente raíz predeterminada. Los botones siguen usando las variantes primaria, secundaria y destructiva y sus estados interactivos existentes.

| Contexto | Ancho de referencia | Distribución |
| --- | ---: | --- |
| Acciones de filas y tarjetas móviles de las cuatro tablas de gestión | `10rem` (160 px) | Una columna en tablas. En tarjetas, el grupo envuelve según el espacio disponible. |
| Editar, Duplicar y Más opciones de Historial | `10rem` (160 px) | El botón del menú comparte las medidas del grupo. Ver resultado conserva el ancho completo por su función de acceso principal. |
| Plantillas y grupos de detalle de Proyectos y Presupuestos | `14rem` (224 px) | El ancho admite «Crear copia personal» y «Agregar Optimizaciones». El grupo envuelve y cada control se limita al ancho disponible. |
| Acciones de Administración de usuarios | Mitad del espacio disponible, descontando la separación | Dos columnas iguales. A 390 px cada botón mide 162 × 40 px. El alto mínimo de 40 px conserva el patrón compacto de Administración. |

En tablas, la columna Acciones reserva una sola anchura de botón. El relleno lateral de sus celdas se adapta al viewport, y el contenido puede ajustarse en las columnas. El orden de lectura y de tabulación conserva el orden del HTML. La altura puede crecer para acomodar texto ampliado.

## Pantallas auditadas

| Pantalla | Resultado |
| --- | --- |
| Proyectos, Presupuestos y Clientes | Se normalizaron tamaños, márgenes y alineación de las acciones por registro. |
| Materiales | Se normalizó el grupo personal y Editar del catálogo cuando el usuario tiene permiso. La etiqueta Sistema conserva su propio tamaño. |
| Plantillas | Se igualaron las acciones tanto en tarjetas personales como en las predefinidas. |
| Historial de optimizaciones | Editar, Duplicar y Más opciones comparten medidas. La selección múltiple, los favoritos, la paginación y el visor conservan sus controles propios. |
| Detalle de Proyectos y Presupuestos | Los grupos generales comparables comparten las medidas amplias. Las acciones de consulta de un plan dentro del detalle siguen siendo controles compactos de una sola acción. |
| Historial del cliente, Historial de costos y asociación de optimizaciones | Se inspeccionaron en Chromium. Las consultas individuales, la acción de agregar y la navegación tienen funciones distintas de las acciones múltiples por registro. |
| Administración de usuarios | Editar y Eliminar medían 170 y 154 px a 390 px. Una cuadrícula de dos columnas igualó sus anchos y conserva el estilo compacto, el enlace de edición y la confirmación del formulario de eliminación. |
| Cabeceras, filtros, formularios y visores | Se revisaron las clases compartidas en las pantallas anteriores. Crear, Buscar, Guardar, Cancelar y los iconos compactos conservan la jerarquía de cada pantalla. |
| Estados de Proyectos y Presupuestos | Proyectos conserva los 120 × 42 px de VIS-01. A 768 px, algunas etiquetas de Presupuestos se partían dentro de una palabra al ajustar la tabla. Se protege el ancho intrínseco del texto en la vista de tabla y los cinco estados conservan el alto de 42 px y su relleno. |

## Capturas comparativas

Se usaron cuentas y registros sintéticos. Los recortes se centran en la fila, tarjeta o grupo de acciones.

| Vista | Antes | Después |
| --- | --- | --- |
| Proyectos, 390 px | [Antes](evidencia/vis02/proyectos-antes-390.png) | [Después](evidencia/vis02/proyectos-despues-390.png) |
| Proyectos, 1280 px | [Antes](evidencia/vis02/proyectos-antes-1280.png) | [Después](evidencia/vis02/proyectos-despues-1280.png) |
| Presupuestos, 390 px | [Antes](evidencia/vis02/presupuestos-antes-390.png) | [Después](evidencia/vis02/presupuestos-despues-390.png) |
| Presupuestos, 1280 px | [Antes](evidencia/vis02/presupuestos-antes-1280.png) | [Después](evidencia/vis02/presupuestos-despues-1280.png) |
| Clientes, 390 px | [Antes](evidencia/vis02/clientes-antes-390.png) | [Después](evidencia/vis02/clientes-despues-390.png) |
| Materiales, 390 px | [Antes](evidencia/vis02/materiales-antes-390.png) | [Después](evidencia/vis02/materiales-despues-390.png) |
| Plantillas, 390 px | [Antes](evidencia/vis02/plantillas-antes-390.png) | [Después](evidencia/vis02/plantillas-despues-390.png) |
| Historial, 390 px | [Antes](evidencia/vis02/historial-antes-390.png) | [Después](evidencia/vis02/historial-despues-390.png) |
| Detalle de Proyecto, 390 px | [Antes](evidencia/vis02/proyecto-antes-390.png) | [Después](evidencia/vis02/proyecto-despues-390.png) |
| Detalle de Presupuesto, 390 px | [Antes](evidencia/vis02/presupuesto-antes-390.png) | [Después](evidencia/vis02/presupuesto-despues-390.png) |
| Administración de usuarios, 390 px | [Antes](evidencia/vis02/admin-antes-390.png) | [Después](evidencia/vis02/admin-despues-390.png) |

## Archivos y verificación

- `action-semantics.css` contiene el grupo reutilizable. `base.html` actualiza la versión del recurso. `historial.css` retira el pseudo-elemento vacío.
- Las plantillas de los listados `lista_proyectos.html`, `lista_presupuestos.html`, `lista_clientes.html`, `lista_materiales.html` y `lista_plantillas.html`, `historial.html`, `detalle_proyecto.html` y `detalle_presupuesto.html` aplican el patrón a los grupos auditados.
- `management-refinement.css` concentra el ajuste específico de Administración. `admin_dashboard.html` actualiza la versión de esa hoja de estilos.
- El recorrido permanente mide rectángulos, estilos según la acción, contraste, alineación y destinos. Para repetirlo, cargar `fixtures-acciones-gestion.py` en una SQLite vacía. Ejecutar el recorrido contra Django local con Playwright, `CUTLESS_TEST_ORIGIN`, el JSON de `CUTLESS_TEST_FIXTURE` y copias locales de Bootstrap 5.3.0 en `CUTLESS_TEST_BOOTSTRAP` y `CUTLESS_TEST_BOOTSTRAP_JS`. `CUTLESS_TEST_BASE` permite comparar con un segundo servidor local que use los mismos datos y clave de sesión. `CUTLESS_TEST_EVIDENCE` guarda capturas. [Recorrido de Chromium](../cut/cutless/tests/browser/acciones-gestion.cjs)

| Prueba | Resultado |
| --- | --- |
| Django completa en SQLite | 468 aprobadas y 8 omitidas por bloqueo de filas |
| Django completa en PostgreSQL local | 476 aprobadas |
| Regresiones dirigidas en SQLite y PostgreSQL | 115 aprobadas y 3 omitidas en SQLite. 118 aprobadas en PostgreSQL. |
| Administración de usuarios y permisos | 9 pruebas dirigidas aprobadas en SQLite |
| Chromium 156.0.8078.79 | 320, 390, 768 y 1280 px en claro y oscuro. Se probaron además un zoom de 125 % simulado y texto de 18 px a 390 px. |
| Interacción en Chromium | Tab, Shift+Tab, foco visible, apertura del detalle y de la confirmación de eliminación, descarga de PDF y menú de Historial. |
| Node y Worker simulado | 67 y 8 aprobadas |
| `makemigrations --check --dry-run` en ambos motores y `git diff --check` | Sin migraciones ni incidencias |

La cobertura visual corresponde a las pantallas indicadas y a Chromium Linux. El escalado de página y de texto se simularon en el navegador. Quedan fuera otros motores de renderizado y los gestos de zoom en dispositivos físicos.
