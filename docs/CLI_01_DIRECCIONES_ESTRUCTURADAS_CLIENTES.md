# CLI-01 · Direcciones estructuradas de Clientes

**Fecha:** 23/11/2026

**Base:** `upstream/main`, `00f78af4089eb73d9ad3a4b77b5fc8c49f941859` (PR #24)

**Rama:** `feature/cli01-direcciones-clientes`

**Alcance:** ficha de Clientes y dirección del PDF de presupuesto. Validación con bases y cuentas sintéticas.

## Datos y edición

Antes, `Cliente.direccion` era el único campo postal. El formulario podía recortar espacios exteriores, convertir LF a CRLF al editar otro dato o vaciar el campo si se omitía del POST. CLI-01 conserva esa columna y añade los siguientes campos opcionales.

| Campo | Tipo | Uso |
| --- | --- | --- |
| `direccion` | Texto legado existente | Original. El formulario de CLI-01 conserva exactamente espacios, saltos y caracteres Unicode. |
| `direccion_legada_editada` | Texto nullable | Edición explícita de la dirección en modo legado. Cuando falta, se muestra el original. |
| `direccion_modo` | Texto de hasta 12 caracteres | `NULL` y `legado` usan el texto legado. `estructurada` compone la dirección. `sin_dato` oculta la dirección activa y conserva las dos versiones. |
| `direccion_pais` | Código de hasta 2 caracteres | Selector postal opcional con etiquetas del Babel ya instalado. Es independiente del país telefónico. |
| `direccion_calle`, `direccion_numero`, `direccion_unidad` | Textos de hasta 160, 32 y 64 caracteres | Calle, avenida, camino o ruta. El número admite `S/N`, `12-B` y ceros iniciales. |
| `direccion_region`, `direccion_comuna`, `direccion_localidad` | Textos de hasta 120 caracteres cada uno | Región, estado o provincia, comuna o distrito y ciudad o localidad. |
| `direccion_referencia` | Texto de hasta 240 caracteres | Referencia visible únicamente en la ficha y su historial. |

Al crear un cliente se puede agregar la dirección o dejarla vacía. Al editar, **Mantener la dirección actual** es la opción predeterminada. El propietario puede guardar los campos estructurados, editar el texto legado, recuperar la versión legada activa o dejar la ficha sin dirección activa. La ficha ofrece una vista del texto histórico original. Las secciones se abren con controles nativos, con teclado y sin requerir JavaScript. Si el formulario falla, se abre la sección de dirección y conserva los valores introducidos.

Django valida país, longitudes y caracteres de control en los campos estructurados. Una dirección nueva requiere al menos calle, región, comuna o localidad. Todos esos campos pueden quedar vacíos en una ficha sin dirección. En una edición explícita, un campo estructurado omitido conserva su valor, mientras que un campo enviado vacío puede limpiarse si la dirección sigue siendo válida. Los envíos de contacto que no seleccionan una acción de dirección escriben solo los campos de contacto enviados y la fecha normal de edición. El POST de edición trabaja en una transacción y bloquea la fila del propietario en PostgreSQL. Los errores impiden guardar tanto la dirección como el contacto. Las validaciones de RUT y teléfono y el control CSRF siguen en sus flujos existentes.

Se evaluó usar los códigos CUT de regiones y comunas de Chile. Esta versión usa texto libre porque la incorporación de un catálogo exige fijar una versión, confirmar condiciones de redistribución y definir cómo actualizar códigos y etiquetas. La interfaz acepta datos parciales y divisiones extranjeras. El selector postal usa datos CLDR locales y la validación no consulta servicios externos. No se comprueba entregabilidad postal. [Planilla CUT de SUBDERE](https://www.subdere.gov.cl/documentacion/c%C3%B3digos-%C3%BAnicos-territoriales-actualizados-al-06-de-septiembre-2018)

## Dirección activa y documentos

`Cliente.direccion_activa` centraliza la presentación. En modo estructurado combina únicamente datos presentes, evita repetir la localidad si coincide con la comuna y añade el nombre del país extranjero cuando está indicado. El listado conserva un resumen y el historial muestra el texto completo. Las lecturas no escriben en la base. Las plantillas escapan el contenido de usuario y conservan el espaciado de los textos extensos en la ficha.

| Caso | Fuente de la dirección |
| --- | --- |
| Borrador | Dirección activa del cliente en el PDF. |
| Alta en estado emitido o emisión de borrador | Se guarda el texto activo en la clave existente `detalle_emitido["cliente"]["direccion"]`. La referencia interna queda fuera. |
| Emitido con instantánea | Usa el texto guardado aunque se edite el cliente, se cambie el modo o desaparezca la FK. Una nueva llamada a `cerrar_detalle()` conserva el JSON existente. |
| Histórico sin instantánea, PDF archivado disponible | Devuelve el archivo privado existente, byte a byte. |
| Histórico sin instantánea ni archivo disponible | Regenera el PDF leyendo la dirección legada de la ficha actual. Activar campos estructurados no cambia ese origen. Si el usuario edita deliberadamente el texto legado, una regeneración posterior refleja esa edición. La fecha de emisión no acredita la dirección regenerada. |

Las claves, relaciones con proyectos y optimizaciones, instantáneas existentes, totales y exportaciones ajenas a la dirección mantienen su alcance. La política monetaria pendiente y los formatos PDF y XLSX de importes se conservan. El PDF actual puede omitir glifos japoneses aun cuando la base y la instantánea conservan el texto completo. La cobertura tipográfica queda como pendiente independiente.

## Migración y despliegue

[`0009_cliente_direcciones_estructuradas`](../cut/cutless/migrations/0009_cliente_direcciones_estructuradas.py) depende de `0008_restricciones_correlativo_optimizacion`. Contiene diez operaciones `AddField` nullable, sin defaults ni backfill. `sqlmigrate` mostró únicamente `ALTER TABLE cutless_cliente ADD COLUMN ... NULL` dentro de una transacción en ambos motores. Los registros históricos, relaciones, fechas e instantáneas de la prueba conservaron los valores originales. Se ejecutó `migrate` por segunda vez y Django reportó `No migrations to apply`.

### Comandos de Render revisados

- El **build versionado** ejecuta `python -m pip install -r requirements.txt`, `python cut/manage.py check --deploy --fail-level ERROR` y `python cut/manage.py collectstatic --noinput`. Ninguno aplica migraciones. [build.sh](../build.sh)
- La **guía de Start Command** indica `gunicorn --config gunicorn.conf.py --chdir cut cutless_project.wsgi:application --bind 0.0.0.0:$PORT`. El arranque WSGI y el hook `on_starting` de Gunicorn tampoco aplican migraciones. No existe un Blueprint ni un workflow de despliegue en la revisión auditada. Los comandos efectivos que el servicio tenga configurados en su panel privado quedan por confirmar con su responsable. [Guía de despliegue](PREPARACION_RENDER_SUPABASE.md#directorio-y-comandos-acordados) · [gunicorn.conf.py](../gunicorn.conf.py) · [wsgi.py](../cut/cutless_project/wsgi.py)
- El middleware verifica la presencia de `auth_user`. Un arranque satisfactorio y un login operativo pueden coexistir con un esquema antiguo. En la sonda local se inició Gunicorn con la configuración del repositorio, un socket Unix y PostgreSQL 16.2 desechable. Con `0008`, el login devolvió 200 y el listado autenticado de Clientes devolvió 500. Tras ejecutar `migrate`, el mismo proceso respondió 200 en Clientes. El segundo `migrate` no aplicó operaciones. Las rutas que consulten instancias de `Cliente` deben tratarse como potencialmente afectadas mientras falte `0009`. [Middleware de verificación](../cut/cutless/middleware.py)

### Condiciones previas a la fusión

1. **Confirmar con el responsable de Supabase un respaldo de producción vigente y restaurable antes de fusionar.** Acordar cuándo se tomó, cómo verificarlo y quién puede restaurarlo. Confirmar por separado la disponibilidad de los PDF históricos archivados si están en otro almacenamiento.
2. El responsable del despliegue debe verificar rama conectada, Auto Deploy, Build Command, Start Command y si existe un Pre-Deploy Command en Render. No confiar en el comando de arranque documentado como comprobación de esquema.
3. Acordar que `0009` se aplicará antes de iniciar el código nuevo. Si el servicio cuenta con Pre-Deploy, el comando previsto es `python cut/manage.py migrate --noinput` después de verificar el plan. Render limita ese mecanismo a ciertos servicios. En un servicio sin Pre-Deploy, coordinar una ejecución autorizada desde un entorno controlado antes de permitir el despliegue. La migración requiere un bloqueo de esquema en PostgreSQL y el ensayo local no mide su contención en producción. [Etapas de despliegue de Render](https://render.com/docs/deploys#pre-deploy-command)

Desde la raíz de la revisión que contiene `0009`, la secuencia para el responsable autorizado es:

```sh
python cut/manage.py migrate --plan
python cut/manage.py migrate --noinput
python cut/manage.py migrate --check
python cut/manage.py showmigrations cutless
```

Revisar que el plan solo contenga las operaciones previstas, que `0009` aparezca aplicada y que `migrate --check` finalice correctamente. Tras un eventual despliegue autorizado, verificar Clientes con una ficha sintética, guardar solo el contacto en una ficha de prueba con texto legado, comprobar que el historial presenta el dato activo y comparar un borrador con su PDF ya emitido. Confirmar que una sesión ajena no pueda editar ni descargar la ficha o el documento de prueba.

### Recuperación sin pérdida

- Si el código nuevo arrancó antes de `0009`, aplicar la migración tras confirmar respaldo, destino y plan, antes de reabrir el tráfico afectado. Si esa aplicación queda bloqueada, volver temporalmente a la versión anterior y coordinar un nuevo intento. El estado del esquema debe comprobarse tras cualquier fallo.
- Si ya se registraron direcciones con CLI-01, conservar `0009` y sus columnas. El esquema expandido admite consultas y actualizaciones de columnas conocidas desde el código anterior, pero esa versión no muestra la dirección estructurada y su formulario puede reescribir el texto legado. Suspender la edición de Clientes si se vuelve temporalmente a ese código y restaurar cuanto antes una versión que pueda leer ambas formas.
- Revertir el esquema a `0008` elimina las diez columnas añadidas. El procedimiento operativo de reversión conserva el esquema y los archivos privados. Una restauración de respaldo requiere acuerdo con el responsable de Supabase para preservar escrituras posteriores y evitar pérdidas de datos.

## Evidencia antes y después

| Escenario | Antes, auditoría local del SHA base | Después, implementación |
| --- | --- | --- |
| Guardar solo el correo con una dirección multirenglón | El textarea podía guardar CRLF donde antes había LF. Omitir el campo vaciaba el texto. | Los POST sin acción de dirección dejan el texto original exacto y mantienen el modo. |
| Alta, legado y conversión | Existía un textarea libre. | Alta estructurada opcional y modo legado consultable. La conversión y las ediciones explícitas preservan el original. |
| Cotización anterior sin instantánea | Archivo existente o regeneración con la ficha vigente. | Archivo conservado. Si falta el archivo, se sigue usando el texto legado vigente, aun con la dirección estructurada activa. |
| Nueva cotización emitida | Capturaba `Cliente.direccion`. | Captura `Cliente.direccion_activa` en la misma clave de la instantánea. |

## Pruebas

Entorno local con Python 3.13.12, Django 5.2.19, SQLite 3.50.4, PostgreSQL 16.2 sin conexión TCP y Chromium 156.0.8078.79 en `es-CL`. Bootstrap 5.3.0 se sirvió desde copias locales en Chromium. El navegador bloqueó las demás solicitudes externas.

| Comprobación | Cobertura |
| --- | --- |
| CLI-01 Django | Alta con y sin dirección, Unicode, números alfanuméricos y S/N, conservación exacta de legado al editar correo y teléfono, modos y omisiones, entradas inválidas sin escrituras, propietario, CSRF y HTML escapado. |
| Presupuestos y relaciones | Proyectos, planes y M2M, borrador, dos caminos de emisión, instantánea inmutable, FK nula, PDF archivado y alternativa cuando falta el archivo. |
| Migración CLI-01 | Copia sintética en `0008`, error de lectura con código nuevo, migración y segunda ejecución, integridad de campos, fechas y relaciones, lectura y escritura acotada desde el modelo antiguo con el esquema ampliado. |
| Chromium | Alta, errores con valores retenidos, teclado, etiquetas, edición de correo, conversión y recuperación del original a 320, 390, 768 y 1280 px, con y sin JavaScript. Consultas posteriores verificaron persistencia en SQLite. |
| Regresiones | Contacto, Presupuestos, Gestión, exportaciones y suites completas. Incluyen permisos, H02 y NUM-01 a NUM-03. Node y Worker se ejecutaron localmente. |

### Resultados

| Ejecución | Aprobadas | Fallidas | Omitidas | Errores |
| --- | ---: | ---: | ---: | ---: |
| CLI-01 dirigida · SQLite | 9 | 0 | 0 | 0 |
| CLI-01 dirigida · PostgreSQL | 9 | 0 | 0 | 0 |
| Regresiones de Clientes, Presupuestos, Gestión y exportaciones · SQLite | 28 | 0 | 1 | 0 |
| Regresiones de Clientes, Presupuestos, Gestión y exportaciones · PostgreSQL | 29 | 0 | 0 | 0 |
| Django completa · SQLite | 455 | 0 | 6 | 0 |
| Django completa · PostgreSQL | 461 | 0 | 0 | 0 |
| Node | 67 | 0 | 0 | 0 |
| Worker simulado | 8 | 0 | 0 | 0 |
| Chromium | 8 | 0 | 0 | 0 |

SQLite omitió las pruebas que requieren `select_for_update`. La suite completa ya incluye las pruebas dirigidas y de regresión. Se comprobaron posteriormente 8 altas y 8 ediciones de Chromium en la base temporal. `makemigrations --check --dry-run` informó `No changes detected` en ambos motores. `git diff --check` terminó sin errores.

La comprobación de accesibilidad cubrió foco, etiquetas, Tab, apertura por teclado y ayudas asociadas. Quedan por verificar lectores de pantalla y dispositivos físicos.

### Reproducir

Con las dependencias del proyecto instaladas, apuntar `CUTLESS_DB_*` solo a SQLite desechable o a una instancia local aislada de PostgreSQL. Ejecutar desde la raíz:

```sh
python cut/manage.py test cutless.tests.test_direcciones_clientes --noinput
python cut/manage.py test cutless.tests.test_contacto_clientes cutless.tests.test_presupuestos cutless.tests.test_gestion cutless.tests.test_exportaciones_auditoria --noinput
python cut/manage.py test --noinput
python cut/manage.py makemigrations --check --dry-run
python cut/manage.py sqlmigrate cutless 0009
node --test $(git ls-files 'cut/*.test.cjs')
node --test cloudflare/recuperacion/worker.test.mjs
git diff --check
```

Para Chromium, migrar una SQLite local vacía y preparar los datos con `CUTLESS_TEST_FIXTURE` apuntando a un archivo temporal nuevo. Ejecutar `python cut/manage.py shell < cut/cutless/tests/browser/fixtures-direcciones-clientes.py`. Servir la misma base con `python cut/manage.py runserver 127.0.0.1:8791 --noreload`. Definir `CUTLESS_TEST_ORIGIN=http://127.0.0.1:8791` y `CUTLESS_TEST_BOOTSTRAP` con la ruta del CSS local de Bootstrap 5.3.0. Con Playwright instalado, ejecutar `node cut/cutless/tests/browser/direcciones-clientes.cjs`. Opcionalmente, `CUTLESS_TEST_BOOTSTRAP_JS` apunta al JS de Bootstrap y `CUTLESS_TEST_CHROMIUM` al Chromium local. El fixture contiene una sesión sintética temporal y se descarta al terminar.

## Archivos

| Archivos | Cambio |
| --- | --- |
| [Modelo](../cut/cutless/models.py), [países](../cut/cutless/direcciones.py) y [migración](../cut/cutless/migrations/0009_cliente_direcciones_estructuradas.py) | Columnas nullable, modos, composición, cotización y etiquetas de países. |
| [Formulario](../cut/cutless/forms/clients.py) y [vistas](../cut/cutless/views/clients.py) | Validación, escritura explícita y transaccional de Cliente. |
| [Alta](../cut/cutless/templates/cutless/crear_cliente.html), [edición](../cut/cutless/templates/cutless/editar_cliente.html), [parcial](../cut/cutless/templates/cutless/includes/cliente-direccion.html), [listado](../cut/cutless/templates/cutless/lista_clientes.html), [historial](../cut/cutless/templates/cutless/historial_cliente.html), [tutorial](../cut/cutless/templates/cutless/includes/tutorial-scripts.html) y [estilos](../cut/cutless/static/cutless/css/management-refinement.css) | Interfaz y presentación de la dirección e instrucciones de edición. |
| [Exportador PDF](../cut/cutless/exports/pdf.py) | Selección de la fuente de la dirección para cada tipo de cotización. |
| [Pruebas CLI-01](../cut/cutless/tests/test_direcciones_clientes.py), [prueba previa de migraciones](../cut/cutless/tests/test_migracion_correlativos.py), [Chromium](../cut/cutless/tests/browser/direcciones-clientes.cjs) y [fixture](../cut/cutless/tests/browser/fixtures-direcciones-clientes.py) | Cobertura permanente con datos sintéticos y restauración del último esquema en pruebas. |
| [README](../README.md), este informe y [registro mensual](REGISTRO_CAMBIOS_NOVIEMBRE_2026.md) | Índice, evidencia y estado del cambio. |
