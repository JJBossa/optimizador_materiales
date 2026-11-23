# NUM-01 · Correcciones de validación numérica

## Alcance y resultados

Rama `fix/num01-errores-validacion`, basada en `upstream/main` en `cc87a98d196fd5e4ef42e8bbb7e6c3ab06ffb43d`. La referencia anterior proviene de la matriz `AUDITORIA_CAMPOS_NUMERICOS_CUTLESS.md` y sus CSV de SQLite, PostgreSQL y Chromium. Los 11 estados iniciales fueron cotejados contra esa evidencia. La repetición de las entradas de la matriz se hizo sobre la corrección, en entornos desechables. El error de la coma se volvió a comprobar en Chromium sobre la base sin corregir.

### Respuestas HTTP

Historial sumaba un día a la fecha final y desbordaba el calendario de Python en el día máximo. Ahora filtra por fecha local de forma inclusiva, con los mismos permisos y filtros de propietario. Una fecha inválida o un intervalo invertido devuelve 400 con un aviso y el formulario de filtros. Una fecha máxima válida devuelve 200 y mantiene el filtro.

Las dos preselecciones y el borrado por selección pasaban identificadores sin validar al ORM, que intentaba convertirlos a entero y lanzaba `ValueError`. Se acepta una clave positiva de dígitos ASCII dentro del rango de `BigAutoField`. Un formato inválido devuelve 400 con un mensaje breve. Una clave válida que no identifica un plan visible para el propietario devuelve 404, tanto si no existe como si pertenece a otra cuenta.

El borrado por selección utiliza una transacción, bloquea los registros propios en orden de clave y comprueba el lote completo antes de eliminar. El lote se conserva íntegro cuando alguna clave es inválida o inaccesible. Los repetidos cuentan una vez, el POST sin selección conserva el aviso existente y una consulta GET devuelve 405. Las preselecciones vacías siguen abriendo el formulario desde cero. La revisión verificó que el 404 para un plan ajeno usa la misma página genérica que un plan inexistente y que el texto del 400 no revela la existencia de ninguno de ellos.

### Los 11 casos originales

| Caso | Entrada en la auditoría | Excepción original | Antes | Después en ambos motores |
| --- | --- | --- | --- | --- |
| 01 | Historial, fecha final máxima del calendario | `OverflowError` | 500 | 200, filtro inclusivo |
| 02 | Historial, clave de borrado alfabética | `ValueError` | 500 | 400, lote conservado |
| 03 | Historial, clave de borrado fraccionaria | `ValueError` | 500 | 400, lote conservado |
| 04 | Presupuestos, preselección alfabética | `ValueError` | 500 | 400 |
| 05 | Presupuestos, preselección con cifras y letras | `ValueError` | 500 | 400 |
| 06 | Presupuestos, preselección fraccionaria | `ValueError` | 500 | 400 |
| 07 | Presupuestos, preselección en notación científica | `ValueError` | 500 | 400 |
| 08 | Plantillas, preselección alfabética | `ValueError` | 500 | 400 |
| 09 | Plantillas, preselección con cifras y letras | `ValueError` | 500 | 400 |
| 10 | Plantillas, preselección fraccionaria | `ValueError` | 500 | 400 |
| 11 | Plantillas, preselección en notación científica | `ValueError` | 500 | 400 |

### Decimales en Materiales

En Chromium 156 con contexto `es-CL`, el control `type="number"` descartaba la coma al teclear `12,5`. El contenido enviado era `125`, con y sin JavaScript. Django recibía un entero válido y lo guardaba. Un POST directo con la coma sí era rechazado por el formulario original. La diferencia ocurre en el control nativo, antes de enviar al servidor.

Alta y edición ahora utilizan `type="text"` e `inputmode="decimal"` para ancho, alto y precio. El atributo `pattern` y la validación de Django comparten la gramática. Se admite un único separador decimal, coma o punto, sin agrupación de miles, espacios, guiones bajos ni exponentes. Se rechazan también grafías que pueden significar miles o decimales, como `1.000` y `1,000`. Escribe `1000` para miles o `1,0000` para expresar un decimal equivalente a uno. Las medidas históricas con esa grafía se presentan con un cero final al editar. Por ejemplo, `122.125` se muestra como `122.1250` y conserva exactamente el mismo valor al guardarse.

Se permiten decimales como `0,5` o `.5` y un signo inicial. Siguen aplicándose las reglas de signo, rango y escala de cada campo. Solo después de validar la sintaxis, el servidor convierte la coma a punto para interpretar el número. Mientras se corrige un error, el formulario devuelve el texto tal como fue enviado.

Las dimensiones conservan el intervalo físico de 10–300 cm y la conversión existente de unidades. El precio sigue siendo opcional, no negativo, con hasta dos decimales y un máximo de $99.999.999,99. Al teclear `12,5`, Chromium mantiene el literal y el precio guardado es `12.50`. La corrección se limita al formulario de Materiales y utiliza los campos del modelo existentes.

## Archivos

| Archivo | Cambio |
| --- | --- |
| [`views/common.py`](../cut/cutless/views/common.py) | Validador de claves de optimización. |
| [`views/historial.py`](../cut/cutless/views/historial.py) | Fechas inclusivas, respuestas controladas y borrado transaccional del lote autorizado. |
| [`views/budgets.py`](../cut/cutless/views/budgets.py) y [`views/plantillas.py`](../cut/cutless/views/plantillas.py) | Validación de preselección antes de consultar o guardar. |
| [`forms/materials.py`](../cut/cutless/forms/materials.py), [`crear_material.html`](../cut/cutless/templates/cutless/crear_material.html) y [`editar_material.html`](../cut/cutless/templates/cutless/editar_material.html) | Entrada decimal común, ayuda y preservación del texto. |
| [`test_num01_validacion.py`](../cut/cutless/tests/test_num01_validacion.py) | Regresiones de estados HTTP, zona horaria, formatos, propietario, persistencia e integridad. |
| [`num01-validacion.cjs`](../cut/cutless/tests/browser/num01-validacion.cjs) y [`fixtures-num01.py`](../cut/cutless/tests/browser/fixtures-num01.py) | Verificación de navegador sobre datos sintéticos locales. |
| [`README.md`](../README.md) | Enlace desde el índice de documentación. |

## Pruebas ejecutadas

| Ejecución | Resultado |
| --- | --- |
| Pruebas dirigidas de NUM-01 | 15 aprobadas en SQLite. Los mismos casos se incluyen en las dos suites completas. |
| Suite completa Django en SQLite | 404 aprobadas y 6 omitidas por requerir bloqueo de filas. |
| Suite completa Django en PostgreSQL 16.2 local | 410 aprobadas, sin omisiones. Servidor desechable por socket Unix privado. |
| Repetición de la auditoría anterior en la corrección | 2.196 casos, incluidas 809 solicitudes por motor. Cero HTTP 500 en ambos. Coincidieron los resultados HTTP y se comprobaron los 11 cambios de estado indicados arriba. |
| Node, incluido el Worker simulado | 73 aprobadas. |
| Chromium 156, `es-CL` | En ambos modos de JavaScript pasó la creación y edición de Materiales con coma y punto, el rechazo de separadores ambiguos y de escalas incompatibles, la conservación de entradas tras el error, el filtro por la fecha máxima y las preselecciones del propietario. |
| `git diff --check` y `makemigrations --check --dry-run` | Sin errores de espacios ni cambios de esquema. |

Las regresiones verificaron que un lote inválido no elimine el plan propio ni altere sus asociaciones y que la preselección ajena devuelva 404. También verificaron que el último instante de un día de Santiago se incluya y la medianoche siguiente quede fuera, que límites y precisión monetaria se conserven y que editar materiales ajenos no cambie datos. Guardar un material histórico mantiene sus dimensiones y la asociación con un plan existente, cuyo precio por tablero permanece intacto.

Para repetir las pruebas Django en una SQLite local desechable, configura `CUTLESS_ENV=development`, `CUTLESS_DB_ENGINE=sqlite` y `CUTLESS_DB_PATH` dentro de un directorio temporal. Ejecuta `python cut/manage.py test cutless.tests.test_num01_validacion --noinput` o `python cut/manage.py test cutless usuarios --noinput` con el entorno virtual del proyecto.

Para Chromium, aplica las migraciones existentes solo en esa SQLite vacía, exporta `CUTLESS_TEST_FIXTURE` con la ruta a un archivo nuevo dentro del directorio temporal y ejecuta `python cut/manage.py shell < cut/cutless/tests/browser/fixtures-num01.py`. Inicia Django en `127.0.0.1:8797` con esa configuración. Con Playwright disponible, ejecuta `node cut/cutless/tests/browser/num01-validacion.cjs`. `CUTLESS_TEST_CHROMIUM` permite elegir un ejecutable instalado y `CUTLESS_TEST_BOOTSTRAP` una copia local de Bootstrap 5.3.0. El navegador bloquea solicitudes externas. Detén el servidor y elimina la base y la sesión sintéticas al terminar.

## Limitaciones y trabajo pendiente

- La verificación de interfaz se hizo en Chromium 156, con configuración `es-CL`. Queda por comprobar la entrada en otros navegadores y teclados móviles físicos. El costo de los filtros por fecha con un historial muy grande queda por medir.
- Para NUM-02 queda pendiente alinear los límites del administrador con los formularios públicos. La auditoría anterior sigue siendo la referencia de esos casos, que no se modificaron en NUM-01.
- Para NUM-03 quedan pendientes las discrepancias de formato y precisión fuera de Materiales, el factor de milímetros del editor de Plantillas y la conservación de campos en el alta de Optimización cuando no hay filas válidas.
- La validación de teléfonos y RUT continúa en su rama independiente. NUM-01 no requiere migraciones ni dependencias nuevas. La evidencia corresponde a bases desechables y servicios locales.
