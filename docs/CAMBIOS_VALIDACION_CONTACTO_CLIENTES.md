# Validación de teléfono internacional y RUT en Clientes

## Problema y alcance

El formulario de Clientes permitía guardar letras y hasta 20 dígitos como teléfono. También comprobaba el formato del RUT sin verificar su dígito final. El alta y la edición usan `ClienteForm`, por lo que la validación se aplica en ambos recorridos antes de guardar.

Base revisada `upstream/main`, commit `cc87a98d196fd5e4ef42e8bbb7e6c3ab06ffb43d`. Rama local `fix/validacion-contacto-clientes`.

## Reglas de entrada

- **Teléfono.** Sigue siendo opcional. La lista HTML muestra bandera, nombre en español y prefijo. Chile (`+56`) es el valor inicial en el alta. Un número nacional se interpreta en la región seleccionada. Un número pegado con `+` usa su prefijo internacional, incluso si el selector indica otra región. En la edición se intenta recuperar la región de un teléfono guardado con `+`.
- **Validación y almacenamiento.** `phonenumbers==9.0.44` comprueba el plan de numeración. Django rechaza letras, extensiones y caracteres fuera del formato admitido. Se pueden usar espacios, guiones, puntos y paréntesis para agrupar los dígitos. Se guarda E.164, con `+` y hasta 15 dígitos. Esta comprobación cubre la estructura del número y su plan de numeración. La asignación a una persona o la disponibilidad de la línea requieren verificación aparte.
- **Búsqueda de países.** `Babel==2.18.0` aporta los nombres en español. El filtro local busca por nombre o prefijo, admite búsquedas sin tildes, conserva la selección y anuncia cuántos resultados hay. Enter pasa al selector y sus controles nativos permiten elegir con el teclado. Con JavaScript desactivado se usa la lista completa. La representación de las banderas depende de las fuentes del dispositivo. El país y el prefijo siempre están en texto.
- **RUT.** Sigue siendo opcional. Django acepta las formas habituales con o sin puntos y guion. Calcula el dígito mediante módulo 11, recorriendo los dígitos del cuerpo de derecha a izquierda con factores cíclicos de 2 a 7. Los resultados `0` y `10` se escriben como `0` y `K`. El formato guardado es `cuerpo-DV`, sin puntos y con `K` mayúscula. La comprobación valida el dígito y no consulta registros fiscales.
- **Errores.** El formulario conserva los valores enviados y asocia cada mensaje al campo correspondiente. Las dos vistas comparten el bloque de teléfono. A partir de 768 px se muestran el país y el número en columnas. Por debajo de ese ancho, los campos se apilan.

## Compatibilidad de datos

Al editar otros campos, el teléfono y el RUT existentes se preservan tal como están. Esto incluye valores inválidos, identificadores fiscales extranjeros ya guardados y formatos anteriores válidos. Si cambia el número o su país, el teléfono se valida de nuevo. Si cambia el RUT, el valor debe ser un RUT chileno válido o quedar vacío. La política de identificadores extranjeros queda pendiente.

E.164 cabe en los 20 caracteres del campo existente. No se requieren cambios de modelo, migraciones de esquema ni conversiones masivas. Las asociaciones mantienen el mismo identificador de cliente. Las cotizaciones emitidas conservan su instantánea, incluido el teléfono y el RUT que tenían al emitirse. Los borradores pueden mostrar los datos vigentes del cliente. El listado y la búsqueda mantienen sus reglas actuales.

## Archivos

| Archivo | Cambio |
| --- | --- |
| [`validacion_contacto.py`](../cut/cutless/validacion_contacto.py) y [`forms/clients.py`](../cut/cutless/forms/clients.py) | Catálogo de regiones y validaciones. Conservación de valores anteriores en la edición. |
| [`crear_cliente.html`](../cut/cutless/templates/cutless/crear_cliente.html), [`editar_cliente.html`](../cut/cutless/templates/cutless/editar_cliente.html) y [`cliente-telefono.html`](../cut/cutless/templates/cutless/includes/cliente-telefono.html) | Selector, entrada telefónica y ayuda asociada al campo. |
| [`cliente-telefono.js`](../cut/cutless/static/cutless/js/cliente-telefono.js) | Filtro opcional sobre el selector nativo. |
| [`requirements.txt`](../cut/requirements.txt) | Dos dependencias fijadas. Las versiones declaradas del resto permanecen iguales. |
| [`test_contacto_clientes.py`](../cut/cutless/tests/test_contacto_clientes.py) y [`test_revision_herramientas.py`](../cut/cutless/tests/test_revision_herramientas.py) | Pruebas de validación, persistencia, acceso, búsqueda, asociaciones e instantáneas. Se corrigieron los ejemplos de dígitos de la prueba anterior. |
| [`contacto-clientes.cjs`](../cut/cutless/tests/browser/contacto-clientes.cjs) y [`fixtures-contacto-clientes.py`](../cut/cutless/tests/browser/fixtures-contacto-clientes.py) | Recorrido de Chromium con sesión y cliente sintéticos en SQLite local. |
| [`README.md`](../README.md#documentación-de-cambios) | Enlace desde el índice. |

## Pruebas locales

Se usaron Python 3.13.12 y Django 5.2.19 con datos sintéticos. SQLite usó una base de pruebas en memoria. PostgreSQL 16.2 se inició en un directorio temporal con socket Unix privado y TCP deshabilitado.

| Ejecución | Resultado |
| --- | --- |
| Clientes y revisión de herramientas en SQLite | 33 aprobadas |
| Clientes y revisión de herramientas en PostgreSQL 16.2 | 33 aprobadas |
| Suite completa de Django en SQLite | 404 aprobadas y 6 omitidas por requerir bloqueo de filas o concurrencia de PostgreSQL |
| Suite completa de Django en PostgreSQL 16.2 | 410 aprobadas |
| Pruebas de Node, incluido el Worker simulado | 73 aprobadas |
| Chromium 156 | Crear y editar a 320, 390, 768 y 1440 px, en ambos temas. Búsqueda y recorrido por teclado en móvil. Alta válida, errores y edición de un cliente histórico con JavaScript desactivado. |
| `makemigrations --check --dry-run` | Sin cambios de esquema detectados |
| `pip check` | Sin conflictos |

Las pruebas de Clientes cubren números chilenos e internacionales, campos opcionales, rechazos, RUT con distintos verificadores, conservación ante errores y acceso por propietario. Las pruebas de regresión abren el listado y buscan clientes por RUT. También crean presupuestos, comprueban las asociaciones y verifican que el PDF de una cotización emitida contenga los datos históricos mientras el de un borrador usa el contacto actualizado.

En la revisión final de Chromium se comprobó que el selector muestra el prefijo del país elegido, que un número pegado con `+44` se guarda en formato E.164 aunque Chile esté seleccionado y que los mensajes del teléfono y del RUT se asocian a sus campos mediante `aria-describedby`. Los recorridos se hicieron con tamaños de ventana controlados. Queda pendiente una revisión en dispositivos físicos y con lectores de pantalla. La evidencia corresponde a entornos locales.

Para repetir en SQLite, crea un entorno virtual con las dependencias declaradas y ejecuta desde la raíz, con una base temporal y sin variables de producción.

```bash
contacto_tmp=$(mktemp -d)
export CUTLESS_ENV=development CUTLESS_DB_ENGINE=sqlite
export CUTLESS_DB_PATH="$contacto_tmp/contacto.sqlite3"
.venv/bin/python cut/manage.py test cutless.tests.test_contacto_clientes cutless.tests.test_revision_herramientas --noinput
.venv/bin/python cut/manage.py test cutless usuarios --noinput
.venv/bin/python cut/manage.py makemigrations --check --dry-run
```

Para Chromium, prepara la base desechable anterior con `manage.py migrate`, exporta `CUTLESS_TEST_FIXTURE="$contacto_tmp/fixture.json"` y ejecuta `manage.py shell < cut/cutless/tests/browser/fixtures-contacto-clientes.py`. Inicia Django en `127.0.0.1:8791` con la misma configuración. Con Playwright disponible en el entorno de pruebas, exporta `CUTLESS_TEST_BOOTSTRAP` con la ruta a una copia local de `bootstrap.min.css` 5.3.0 y ejecuta `node cut/cutless/tests/browser/contacto-clientes.cjs`. `CUTLESS_TEST_CHROMIUM` permite elegir un Chromium instalado y `CUTLESS_TEST_EVIDENCE` permite guardar capturas fuera del repositorio. El navegador bloquea solicitudes externas. Al terminar, detén el servidor y elimina la base y el archivo de sesión temporales.
