# VIS-05 · Importes en formularios

La rama `fix/vis05-formato-importes-formularios` parte de `upstream/main` `bed8581ddd4a493b320730e17b478bf26de98a04`, que incluye PRE-02. [PR #32](https://github.com/gy0kuroo/optimizador_materiales/pull/32)

## Inventario verificado en Chromium

| Pantalla | Campos | Hallazgo y alcance |
| --- | --- | --- |
| Presupuestos · alta y edición | `precio_tablero`, `mano_obra` | La mano de obra inicial se mostraba como `0.00`. La precarga desde un plan y la edición mostraban `10000.00`, `5500.00` y `12500.50`. Ambos campos usan la presentación de importes. |
| Materiales · biblioteca y Django Admin | `precio` | En alta y con precio ausente el campo ya aparecía vacío. En edición, el precio numérico guardado incluía ceros sobrantes. Ambos formularios comparten la corrección. |
| Optimización · alta y edición | `precio_tablero`, `mano_obra` | La pantalla de alta ya mostraba precio vacío y mano de obra `0`. La edición con importes guardados mostraba `10000.00`, `5500.00` y `12500.50`. El formulario compartido aplica la corrección a esos valores iniciales. |
| Optimización · selector de catálogo | `precio_tablero` | Ya cargaba `10000`, `12500.5`, `12500.25`, `0` o un campo vacío. La selección en edición respeta un precio precargado. La carga existente se conserva. |
| Django Admin · Optimización | `precio_tablero`, `mano_obra` | Mano de obra `0.00` en el alta y ceros sobrantes en los dos campos al editar. Se aplica la presentación a ambos. |
| Django Admin · PerfilUsuario | `precio_tablero_predeterminado`, `mano_obra_predeterminada` | Mano de obra `0.00` en el alta y `10000.00` y `5500.00` con valores guardados. Se aplica la presentación a los dos campos. |

Los anchos, altos y márgenes conservan su propio formato. Por ejemplo, el ancho `122.1234` conservó todos sus dígitos en Materiales y Optimización. Se revisaron también los campos de cantidades y medidas en Plantillas y Configuración, y las salidas de lectura CLP de los listados, detalles y exportaciones. [Formateador de lectura CLP](../cut/cutless/formato_clp.py) · [Catálogo de materiales](../cut/cutless/views/common.py)

## Presentación y precisión

Solo los campos monetarios optan por la preparación de importes. El formateador elimina los ceros finales de un `Decimal` finito mediante su representación exacta y conserva el valor numérico. No aplica redondeos ni separadores de miles. Un valor vacío sigue vacío. El texto enviado en un POST se conserva tal como llega al campo. Los campos `type=number` mantienen la sintaxis de Django y el comportamiento nativo del navegador. Los campos de texto decimal mantienen la lectura de coma y punto y el rechazo de ambigüedades como `1,000`. [Formateador](../cut/cutless/formatos_numericos.py) · [Campos de formulario](../cut/cutless/forms/numeros.py)

| Antes | Después |
| --- | --- |
| `10000.00` | `10000` |
| `5500.00` | `5500` |
| `12500.50` | `12500.5` |
| `12500.25` | `12500.25` |
| `0.00` | `0` |
| Vacío | Vacío |

## Evidencia visual

Se usaron copias de una SQLite sintética con el mismo catálogo y los mismos importes para comparar la base con VIS-05.

| Pantalla | Antes | Después |
| --- | --- | --- |
| Materiales · 390 px | [Precio entero](evidencia/vis05/material_entero-antes-390.png) | [Precio sin ceros decimales](evidencia/vis05/material_entero-despues-390.png) |
| Materiales en Django Admin · 1280 px | [Precio entero](evidencia/vis05/material_admin_entero-antes-1280.png) | [Precio sin ceros decimales](evidencia/vis05/material_admin_entero-despues-1280.png) |
| Presupuestos · 1280 px | [Precio y mano de obra](evidencia/vis05/presupuesto_entero-antes-1280.png) | [Ambos importes enteros](evidencia/vis05/presupuesto_entero-despues-1280.png) |
| Optimización · 390 px | [Importes con fracción](evidencia/vis05/opt_fraccion-antes-390.png) | [Fracciones íntegras](evidencia/vis05/opt_fraccion-despues-390.png) |

## Verificación

| Prueba | Resultado |
| --- | --- |
| Chromium 156 a 390 y 1280 px | 32 casos de formulario por ancho antes y después, incluidos alta, edición y Django Admin. La prueba comprobó el valor efectivo y el tipo de cada input y probó los cinco precios del catálogo al crear, editar sin precio y editar con precio ya precargado. |
| POST inválido en Chromium | Se conservaron importes escritos como `12500,50`, `12500.50`, `10000.00` y `5500.00`, según el campo de cada formulario. |
| Django dirigida · PostgreSQL local | 79 aprobadas. Comprueba precisión con contexto decimal reducido, formatos ambiguos, alta y edición, conservación de datos históricos, totales exactos y permisos. |
| Django completa · SQLite | 485 aprobadas, 8 omitidas por requerir bloqueo de filas. |
| Django completa · PostgreSQL 16.16 local | 493 aprobadas. |
| Esquema y diff | `makemigrations --check --dry-run` sin cambios y `git diff --check` limpio. |

Al reenviar `12500.5` y `12500.25` en un presupuesto de dos tableros se conservó el total `37501.25`. El alta y la edición de una optimización de un tablero conservaron el total `25000.75`. Las pruebas existentes verificaron que editar metadatos de un material preserva el precio histórico almacenado, incluso cuando SQLite conserva más decimales que los expuestos por Django. [Regresiones de importes](../cut/cutless/tests/test_importes_formularios.py) · [Regresiones de Materiales](../cut/cutless/tests/test_num02_materiales.py)

Para reproducir el recorrido, carga `fixtures-importes-formularios.py` en una SQLite local vacía y ejecuta `node cut/cutless/tests/browser/importes-formularios.cjs` con la configuración de Chromium y Bootstrap local. `CUTLESS_TEST_AUDIT=1` registra la base y `CUTLESS_TEST_EVIDENCE` guarda las capturas. Los controles numéricos siguen sujetos a la representación de valores del navegador. En particular, Chromium puede mostrar un campo vacío si el servidor vuelve a renderizar un literal que `type=number` no admite. [Configuración local](VIS_03_UX_03_ESTADISTICAS_DESCARGAS.md) · [Recorrido de Chromium](../cut/cutless/tests/browser/importes-formularios.cjs)
