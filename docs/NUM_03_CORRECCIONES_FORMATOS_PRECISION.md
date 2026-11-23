# NUM-03 · Formatos y precisión en Plantillas y Optimización

Rama `fix/num03-formatos-precision`, desde `upstream/main` en `660e355a16b6ec8688338e340ec68abcbfcdcd45`, con NUM-01 y NUM-02 integrados.

## Contrato numérico

- Los campos individuales conservan el texto enviado. Admiten coma o punto decimal, sin agrupación, exponentes, guiones bajos ni valores no finitos. Las grafías ambiguas como `1.000` y `1,000` se rechazan. `1.0000` expresa un decimal inequívoco. Las cantidades aceptan únicamente dígitos ASCII y un valor de 1 a 100. Una cantidad vacía de una pieza de Optimización conserva el valor predeterminado de una unidad.
- Se admiten cm, mm, m, in y ft, con factores a centímetros de 1, 0.1, 100, 2.54 y 30.48. El tablero admite 10–300 cm y las piezas 0.1–300 cm. La conversión física para entradas nuevas mantiene seis decimales en cm. Las piezas siguen almacenadas en la unidad de entrada. Los límites del editor visual se derivan del contrato del servidor.
- El ancho de sierra se introduce en mm y se almacena en cm. Admite valores de 0 a 10 mm y resolución de 0.01 mm o más fina. No se impone un paso de una décima ni se redondean las precargas. Se conserva el comportamiento fraccionario que ya admitía el servidor.
- CSV mantiene coma entre columnas y punto decimal en dimensiones, con comillas dobles para campos con comas, comillas o saltos. Las comillas literales se escapan duplicándolas. El editor visual usa los mismos valores estructurados y los serializa de forma reversible. Se conserva la lectura estricta del JSON versionado y del texto histórico de H02, incluida la detección de filas incompletas.
- Editar solo metadatos conserva los valores numéricos originales. Un valor presentado equivalente al inicial en la misma unidad conserva el valor canónico al editar. Los errores devuelven los valores del POST y no escriben parcialmente. Una lista histórica ilegible sigue bloqueada.
- La cadena enviada se valida antes de convertir. El valor persistido y el usado para cálculo se mantienen separados de la cifra formateada para lectura. En moneda se conserva la precisión de dos decimales y la política visual vigente.

## Objetivo y hallazgos

La corrección abarca entradas de Plantillas y Optimización, conservación tras errores, unidades y compatibilidad de piezas. La auditoría reprodujo los defectos con datos sintéticos. Su informe y matrices se conservan fuera del repositorio, en `/workspace/shared/cutless-num03/`.

| Auditoría | Antes y causa | Corrección y verificación |
| --- | --- | --- |
| NUM03-01 · Decimales | Chromium `es-CL` quitaba la coma en `type=number` y enviaba un valor diferente. | Django y el editor visual usan texto con teclado decimal. Teclear `12,5` en tablero o precio y `0,5` en sierra mantiene el literal en el POST. Se valida y solo después se normaliza. |
| NUM03-02 · Reintento | El catálogo volvía a llenar el formulario enlazado mediante temporizadores. | Se eliminó ese autocompletado de carga. Elegir un material solo llena campos sin entrada propia. La prueba corrige únicamente la pieza que no cabe y conserva tablero `132.125 × 242.25` cm, precio `37.25`, sierra, mano de obra, rotación y asociaciones. Se introduce el ancho como `132.1250` para desambiguar la grafía de tres cifras tras el punto. |
| NUM03-03 · Piezas en mm | El editor omitía el factor de mm y rechazaba `400 × 500 mm`. | Las cinco unidades y los límites físicos del servidor se entregan al editor. La pieza de `400 × 500 mm` se guarda con el mismo significado con y sin JS. |
| NUM03-04 · Pasos | El paso HTML impedía enviar medidas válidas como `1.22125 m` o una sierra de `2.15 mm`. | El control acepta la precisión numérica validada por Django. Se probó la medida y se duplicó el plan con el margen exacto. |
| NUM03-05 · Medidas históricas | El redondeo de ida y vuelta podía cambiar un largo almacenado o bloquear `300 cm` en pies. | El formulario compara los valores editables y conserva la medida original si son equivalentes y la unidad se mantiene. Un valor modificado se convierte y valida una vez. Las vistas usan los cm validados tanto para calcular como para guardar. |
| NUM03-06 · Sierra | La precarga redondeaba `2.15` a `2.1 mm` y podía persistir la diferencia. | Las precargas presentan la precisión disponible. Se probó `0.01 mm` para una entrada nueva y la conservación de `2.15 mm` históricos. El algoritmo ya admite el margen fraccionario y se sigue usando su geometría existente. |
| NUM03-07 · Nombres | El editor concatenaba columnas sin escape y prohibía comas. | Django entrega filas estructuradas. El editor permite nombres con comas, comillas, Unicode y saltos, y escapa las columnas mediante CSV. Los nombres complejos pasan del navegador a la base. |
| NUM03-08 · Cantidades | `1.000` podía terminar como una pieza. | Los formularios nuevos exigen cantidades enteras estrictas y rechazan separadores, exponentes y fracciones. En CSV nuevo también se rechazan medidas ambiguas; las piezas históricas conservan su interpretación. |
| NUM03-09 · Moneda | El portal y las dos clases de exportación presentan `12.50` de forma distinta. | Se verificó la diferencia y el importe de cálculo. La decisión de cambiar exportaciones queda pendiente. |

## Conservación y compatibilidad

Editar un plan o plantilla compara el valor numérico recibido con la representación del registro autorizado. Cuando coinciden, se reutilizan los centímetros o el margen originales. Si la lista de piezas representa las mismas filas, se conserva su texto histórico. Los cambios nuevos conservan el almacenamiento `piezas:v1:`. Una plantilla ilegible mantiene el textarea para que la corrección sea explícita, y los recorridos que podrían descartar filas mantienen el bloqueo de H02.

Duplicar un plan o usar una plantilla envía una copia firmada de sus dimensiones y margen, vinculada a la cuenta que abrió el formulario. Así se mantiene la precisión aunque el alta se envíe a otra ruta. Se verifica la firma y la cuenta y se validan los límites físicos en Django. La copia contiene cantidades de geometría, sin permisos, precios ni identificadores de recursos. Crear una plantilla desde una optimización utiliza el plan autorizado por la ruta. Las vistas conservan sus controles de propiedad y el catálogo mantiene la validación de precio de NUM-02.

El tipo almacenado de las medidas permanece `FloatField`. El margen admite al menos centésimas de milímetro, con la precisión real disponible en el tipo existente. Los costos siguen usando `DecimalField`; su escala continúa limitada a dos decimales. La aceptación sintáctica de un decimal y la escala de cada campo se validan por separado.

## CSV y moneda

El CSV manual continúa usando coma para separar cuatro columnas y punto para las dimensiones, por ejemplo `"Puerta, norte",12.50,30,1`. El lector de H02 continúa aceptando las representaciones históricas soportadas. Las entradas individuales del editor visual pueden usar coma decimal inequívoca y se convierten a punto al serializar; el CSV manual con coma decimal se rechaza. Queda pendiente decidir si se ofrece otro mecanismo de importación que admita una coma decimal sin confundirla con el separador de columnas.

Se volvió a comprobar la comparación de C01 con datos sintéticos:

| Superficie | Resultado |
| --- | --- |
| Edición de material y dato guardado | `12.50` CLP |
| Biblioteca, Historial de costos y presupuesto web | `$13`, filtro CLP con redondeo visual de mitades alejándose de cero |
| Cálculo de dos tableros | `25.00` CLP |
| PDF y XLSX de la optimización | `$12`, redondeo legado a cero decimales. La celda XLSX es texto. |
| PDF de presupuesto | `$12.50`, representación con dos decimales. |

La decisión sobre uniformidad puede conservar y documentar los formatos actuales, aplicar el CLP visual también en los archivos o exponer dos decimales en las exportaciones para permitir conciliación de costos. Reutilizar el CLP de pantalla alinearía la lectura pero ocultaría fracciones; dos decimales conservarían la cifra de origen y exigirían acordar el formato local y el tipo de celda de XLSX. Las tres alternativas son de presentación y dejan fuera cambios a datos guardados y cálculos.

## Archivos

| Archivos | Función |
| --- | --- |
| [formatos_numericos.py](../cut/cutless/formatos_numericos.py), [forms/numeros.py](../cut/cutless/forms/numeros.py), [forms/materials.py](../cut/cutless/forms/materials.py) | Gramática compartida y controles decimal, dimensional y entero. Materiales reutiliza el mismo analizador, con sus reglas existentes. |
| [forms/optimization.py](../cut/cutless/forms/optimization.py), [forms/plantillas.py](../cut/cutless/forms/plantillas.py), [units.py](../cut/cutless/units.py), [pieces.py](../cut/cutless/pieces.py) | Validación, conversiones para edición, preservación de origen, lectura histórica y contrato CSV. |
| [views/optimization.py](../cut/cutless/views/optimization.py), [views/plantillas.py](../cut/cutless/views/plantillas.py) | Consumen las cantidades ya validadas y preservan los recorridos de alta, edición y copia. |
| [dimension-feedback.js](../cut/cutless/static/cutless/js/dimension-feedback.js), [units.js](../cut/cutless/static/cutless/js/units.js), [medidas-pred.js](../cut/cutless/static/cutless/js/medidas-pred.js), [template-piece-editor.js](../cut/cutless/static/cutless/js/template-piece-editor.js) | Validación interactiva y conversión de unidades, autocompletado y serialización del editor. |
| [index.html](../cut/cutless/templates/cutless/index.html), [editar_optimizacion.html](../cut/cutless/templates/cutless/editar_optimizacion.html), [crear_plantilla.html](../cut/cutless/templates/cutless/crear_plantilla.html), [editar_plantilla.html](../cut/cutless/templates/cutless/editar_plantilla.html) | Controles de ingreso, conservación del POST y datos del editor. |
| [test_num03_formatos_precision.py](../cut/cutless/tests/test_num03_formatos_precision.py), [test_precision_rnf09.py](../cut/cutless/tests/test_precision_rnf09.py), [template-piece-editor.test.cjs](../cut/cutless/tests/js/template-piece-editor.test.cjs), [num03-formatos-precision.cjs](../cut/cutless/tests/browser/num03-formatos-precision.cjs) | Regresiones permanentes HTTP, geometría, CSV, límites de piezas y recorridos Chromium. RNF-09 verifica el control de texto que sustituye el paso HTML. |
| [README.md](../README.md) y [registro de noviembre](REGISTRO_CAMBIOS_NOVIEMBRE_2026.md) | Índice y seguimiento de la rama. |

## Verificación

Python 3.13.12, Django 5.2.19, SQLite 3.50.4, PostgreSQL 16.2 local con socket privado, Node.js 24.22.1, Playwright 1.62.1 y Chromium 156.0.8078.79. El navegador usó solo Django en loopback y la base SQLite desechable. Los ensayos bloquearon peticiones del navegador fuera de ese origen. PostgreSQL y los archivos de medios se crearon para las pruebas y se limpiaron al terminar.

| Ejecución final | Aprobadas | Fallidas | Omitidas | Errores |
| --- | ---: | ---: | ---: | ---: |
| Django dirigido en SQLite, con H02, NUM-01, NUM-02 y NUM-03 | 130 | 0 | 0 | 0 |
| Django completo, SQLite | 446 | 0 | 6 | 0 |
| Django completo, PostgreSQL 16.2 | 452 | 0 | 0 | 0 |
| Node, incluido el Worker simulado | 75 | 0 | 0 | 0 |
| Chromium `es-CL`, 10 casos por modo de JavaScript | 20 | 0 | 0 | 0 |
| Lecturas de SQLite tras el navegador | 19 | 0 | 0 | 0 |
| Caracterización C01 de precios y exportaciones | 1 | 0 | 0 | 0 |

Las seis omisiones de SQLite corresponden a `select_for_update`, disponible en PostgreSQL, donde aprobaron. `makemigrations --check --dry-run` devolvió `No changes detected` y `git diff --check` pasó.

Las primeras ejecuciones detectaron una incompatibilidad con el contrato HTML de RNF-09 y dos regresiones de presentación del margen. El control de RNF-09 ahora verifica texto con teclado decimal en lugar del atributo `step`, y se restauraron la representación `0` del margen entero y su mensaje de error en milímetros. Se repitieron ambas suites completas sobre la versión final. Un arranque del arnés de Chromium excedió su espera y la primera pasada de SQLite exitosa encontró un error al cerrarse el lanzador editado en paralelo. Ambas verificaciones se repitieron hasta terminar con código 0.

Los archivos `sqlite-publicacion.log`, `postgresql-publicacion.log`, `node-publicacion.log`, `final-chromium.jsonl` y `precios.jsonl` contienen los resultados finales.

Reproducir usando el lanzador y los fixtures aislados disponibles en `/workspace/shared/cutless-num03-correccion/`. El lanzador usa la rama local de la corrección por defecto. `NUM03_WORKTREE`, `NUM03_PYTHON`, `NUM03_PGBIN` y `NODE_PATH` permiten indicar un checkout y binarios locales equivalentes.

```sh
cd /workspace/shared/cutless-num03-correccion
bash ejecutar.sh sqlite regresiones
bash ejecutar.sh sqlite completa
bash ejecutar.sh postgresql completa
bash ejecutar.sh sqlite navegador
bash ejecutar.sh sqlite precios
bash ejecutar.sh sqlite migraciones
cd /workspace/cutless-num03-fix
node --test $(git ls-files 'cut/*.test.cjs' 'cloudflare/*.test.mjs')
git diff --check
```

Las pruebas de navegador cubren teclado en Chromium Linux en `es-CL`. Los resultados no se extrapolan al comportamiento de teclados móviles, otros navegadores o datos de producción. La revisión no requiere migraciones o dependencias nuevas porque los formatos persistidos, los modelos y el motor de cálculo permanecen vigentes.
