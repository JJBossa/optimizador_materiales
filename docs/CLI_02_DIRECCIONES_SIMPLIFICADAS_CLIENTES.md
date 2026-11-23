# CLI-02 · Direcciones simplificadas de Clientes

**Fecha** 23/11/2026

**Base verificada** `55d162e296cc1bfdaf5800f5208c55c2c0860f4b` en `upstream/main` · [PR #25](https://github.com/gy0kuroo/optimizador_materiales/pull/25)

**Rama** `feature/cli02-direcciones-simplificadas`

## Flujo y compatibilidad

| Caso | CLI-01 | CLI-02 |
| --- | --- | --- |
| Alta | Campos estructurados en una sección desplegable. | Un bloque de ocho campos. Todos pueden quedar vacíos al registrar un cliente sin dirección. |
| Edición de una dirección legada activa | Selector de acciones y un textarea editable. | Aviso con referencia de solo lectura. Para guardar cualquier cambio se debe completar una dirección estructurada válida. |
| Edición de una dirección estructurada | Selección explícita del modo. | Formulario precargado. Los cambios de dirección se validan al guardar la ficha. |
| Ficha sin dirección activa | Distintos modos internos. | Puede editarse sin inventar una dirección. Se respeta el estado `sin_dato` que el propietario pudo elegir en CLI-01, incluso si se conserva una dirección archivada internamente. |

El control de actualización vive en Django. Una ficha legada mantiene disponibles el listado, su historial y los recursos asociados. La edición muestra «Continuar al formulario» y «Volver al listado». El diálogo nativo abre al entrar por GET. Al continuar o al cerrarlo por primera vez, el foco pasa al selector de país. Si se abre con «Revisar aviso», Escape devuelve el foco al botón. Después de un error o de actualizar las opciones de ubicación, la explicación queda en línea y el diálogo solo se abre si se solicita. Abrir o cerrar el aviso, regresar al listado y actualizar opciones no guardan datos.

Los valores postales guardados por CLI-01 se precargan. Para una dirección estructurada chilena se buscan equivalencias por nombre en los catálogos de cada región, tolerando diferencias de tildes, puntuación y mayúsculas. Los textos estructurados antiguos sin equivalencia se pueden conservar al editar solo el contacto. Para cambiar la dirección se exige el catálogo y los campos mínimos actuales. El formulario jamás intenta extraer campos del texto libre histórico. `direccion` y `direccion_legada_editada` se conservan exactamente, incluidos espacios, saltos y caracteres internacionales.

## Contrato postal

- La dirección nueva o modificada requiere país, ciudad o comuna, calle y número. Para Chile también requiere región. Número admite texto como `100`, `12-B` y `S/N`. La región extranjera es opcional y de entrada manual.
- Chile envía códigos CUT en sus dos selectores. Django valida que la comuna pertenezca a la región y guarda sus nombres en `direccion_region` y `direccion_comuna`. Fuera de Chile, los campos región y ciudad son de texto, y la ciudad se guarda en `direccion_localidad`. Se conserva una localidad o comuna adicional de CLI-01 cuando se edita un dato postal sin cambiar la ubicación de esa ficha. Una ubicación nueva usa únicamente la representación de su país. El país postal está separado del país telefónico.
- El código postal es opcional y se guarda como texto de hasta 16 caracteres para conservar ceros a la izquierda. Para Chile se exige siete dígitos cuando se proporciona. Para otros países se permite texto postal sin comprobación de entregabilidad.
- La dirección activa se presenta en líneas. Primero va calle, número y unidad. Luego ciudad o comuna, región y código postal, si están presentes. En la última línea figura el país. Se evita repetir localidad y comuna al componer. La referencia queda en la ficha y queda fuera de las cotizaciones y exportaciones.
- Con JavaScript, el cambio de país reemplaza los controles de región y ciudad. Al cambiar de región se descarta la comuna anterior y se ofrecen solo las de la región seleccionada. Sin JavaScript se elige el país y se pulsa «Actualizar opciones de ubicación». Si es Chile, se elige la región y se pulsa de nuevo para cargar sus comunas. Cada actualización conserva el resto del formulario y pasa por CSRF sin guardar. En ambos casos un POST de guardado se valida en el servidor.

## Catálogo local de Chile

`cut/cutless/dpa_chile.json` incluye **16 regiones y 346 comunas**. Se conservaron los códigos CUT y nombres de la capa abierta de la Biblioteca del Congreso Nacional de Chile (BCN), mediante la copia de datos normalizados de chile-hub fijada al commit `833a69a2b40a445b8b3d34f074e6617ba9512aef` del 16/11/2026. Los metadatos de esa copia indican extracción el 08/11/2026 a las 16:28 UTC. La plataforma de datos abiertos de BCN declara **Creative Commons Atribución (CC BY)** sin indicar número de versión en la página citada. La redistribución de este JSON se atribuye a BCN bajo ese aviso. El archivo selecciona códigos, nombres y jerarquía, sin geometrías, estadísticas ni datos de personas. Se usa la grafía «Región del Biobío». [Datos abiertos y licencia de BCN](https://datos.bcn.cl/es/informacion/lo-que-esta-haciendo-bcn) · [Capa original](https://arcgiswebad.bcn.cl/arcgis/rest/services/Hosted/Capa_Factores/FeatureServer/0) · [Metadatos de la copia](https://github.com/cortega26/chile-hub/blob/833a69a2b40a445b8b3d34f074e6617ba9512aef/data/normalized/pipeline_metadata.json)

La copia ya excluye una fila sin código y añade Antártica (`12202`), cuyo código se contrastó con SUBDERE y el decreto territorial. Se verificaron cardinalidad oficial, unicidad y jerarquía, además de Santa Juana (`08109`) y su pertenencia a Biobío. El acceso HTTP directo a la capa desde el ejecutor recibió 403, por lo que la versión integrada es la copia con procedencia fijada. El catálogo abarca comunas administrativas. La validación de calles, localidades subcomunales y entrega postal queda fuera de su cobertura. [Código territorial de SUBDERE](https://www.subdere.gov.cl/sites/default/files/documentos/articles-73111_recurso_2.pdf) · [Decreto CUT](https://www.bcn.cl/leychile/navegar?idNorma=168185) · [Cobertura nacional del INE](https://www.ine.gob.cl/herramientas/portal-de-mapas/geodatos-abiertos/2024/08/01/censo-2024-finaliz%C3%B3-en-las-346-comunas-del-pa%C3%ADs)

## Migración y documentos

La migración [`0010_cliente_codigo_postal`](../cut/cutless/migrations/0010_cliente_codigo_postal.py) depende de `0009_cliente_direcciones_estructuradas` y añade únicamente `direccion_codigo_postal varchar(16) NULL`. No hay defaults de base, actualización masiva ni eliminación de columnas. Se probó desde `0009` con texto histórico, relaciones y cotización emitida, y se repitió `migrate` sin operaciones pendientes. El modelo anterior puede seguir leyendo y escribiendo columnas conocidas con el esquema expandido.

La prueba de arranque con Gunicorn y PostgreSQL local reprodujo login HTTP 200 y Clientes HTTP 500 mientras faltaba `0010`. Clientes volvió a responder 200 en el mismo proceso tras aplicar la migración. La segunda ejecución de `migrate` no aplicó cambios.

Las nuevas emisiones capturan el formato de la dirección activa en la clave JSON existente. Los presupuestos ya emitidos mantienen sus instantáneas. Los PDF archivados se sirven intactos. Si una cotización histórica no tiene instantánea ni archivo, se sigue regenerando con el texto legado disponible, como en CLI-01. Los importes, cálculos, formatos monetarios y relaciones con clientes, proyectos y optimizaciones se mantienen.

### Antes de fusionar

Render tiene Auto Deploy habilitado según el usuario. El [build versionado](../build.sh) instala dependencias, ejecuta `check --deploy` y recopila estáticos. El arranque documentado es Gunicorn mediante `gunicorn --config gunicorn.conf.py --chdir cut cutless_project.wsgi:application --bind 0.0.0.0:$PORT`. Ninguno ejecuta `migrate`. Queda por confirmar el Build Command, Start Command y eventual Pre-Deploy Command efectivos con el responsable de Render. [Guía de despliegue](PREPARACION_RENDER_SUPABASE.md)

Confirmar un respaldo vigente y restaurable con el responsable de Supabase antes de fusionar. Coordinar la aplicación de `0010` antes del arranque del código nuevo y revisar el bloqueo que requiere el DDL de PostgreSQL. En una ventana autorizada desde la revisión nueva, comprobar el plan, aplicar la migración y verificar su estado.

```sh
python cut/manage.py migrate --plan
python cut/manage.py migrate --noinput
python cut/manage.py migrate --check
```

Para recuperar el servicio, volver temporalmente al código de CLI-01 conservando el esquema expandido. CLI-01 no muestra el código postal, pero una actualización de sus campos conocidos no borra la columna nueva. Suspender temporalmente la edición de Clientes durante la recuperación para evitar que el formulario anterior reintroduzca los flujos técnicos. Volver a `0009` mediante reversión de esquema elimina el código postal, por lo que el procedimiento de recuperación conserva `0010`. Una comprobación posterior debe cubrir ficha, alta, conversión legada, borrador PDF e instantánea emitida usando solo datos sintéticos en un entorno autorizado.

## Pruebas y evidencia

Entorno local con Python 3.13.12, Django 5.2.19, SQLite 3.50.4, PostgreSQL 16.2 en socket privado y Chromium 156 en `es-CL`. El navegador utilizó Bootstrap local y bloqueó los otros orígenes. La cobertura dirigida incluye permisos y CSRF, entradas inválidas sin escritura parcial, alta vacía o con dirección, catálogo, cambio de ubicación, edición extranjera, preservación de texto original, compatibilidad con CLI-01, historial, PDF e instantáneas. La suite de migración comprueba el error de lectura del código nuevo con `0009`, integridad tras expandir e idempotencia.

| Ejecución | Aprobadas | Omitidas | Fallidas | Errores |
| --- | ---: | ---: | ---: | ---: |
| Django dirigida CLI-02 · SQLite | 10 | 0 | 0 | 0 |
| Django dirigida CLI-02 · PostgreSQL | 10 | 0 | 0 | 0 |
| Regresiones de contacto, presupuestos, gestión y PDF/XLSX · SQLite | 28 | 1 | 0 | 0 |
| Regresiones de contacto, presupuestos, gestión y PDF/XLSX · PostgreSQL | 29 | 0 | 0 | 0 |
| Django completa · SQLite | 456 | 6 | 0 | 0 |
| Django completa · PostgreSQL | 462 | 0 | 0 | 0 |
| Node | 67 | 0 | 0 | 0 |
| Worker simulado | 8 | 0 | 0 | 0 |
| Chromium, con y sin JavaScript a 320, 390, 768 y 1280 px | 8 | 0 | 0 | 0 |

Las omisiones en SQLite requieren `select_for_update`. La suite completa incluye las comprobaciones dirigidas. La lectura posterior en SQLite comprobó 8 altas y 8 actualizaciones del navegador, incluida la conservación exacta del texto original. `makemigrations --check --dry-run` informó `No changes detected` en ambos motores. `git diff --check` pasó.

Las pruebas de Chromium cubren teclado, devolución de foco, error con datos retenidos, retorno al listado y persistencia. No se usaron dispositivos físicos ni lectores de pantalla. Sigue pendiente la cobertura de glifos japoneses en PDF documentada en CLI-01. [Informe CLI-01](CLI_01_DIRECCIONES_ESTRUCTURADAS_CLIENTES.md)

Capturas con datos sintéticos. [Alta móvil a 390 px](evidencia/cli02/alta-390.png) · [Alta de escritorio a 1280 px](evidencia/cli02/alta-1280.png) · [Aviso móvil](evidencia/cli02/aviso-390.png) · [Aviso de escritorio](evidencia/cli02/aviso-1280.png)

### Repetir localmente

Con las dependencias del proyecto instaladas y `CUTLESS_DB_*` apuntando a una base local desechable, ejecutar desde la raíz:

```sh
python cut/manage.py test cutless.tests.test_direcciones_clientes --noinput
python cut/manage.py test --noinput
python cut/manage.py makemigrations --check --dry-run
python cut/manage.py sqlmigrate cutless 0010
node --test $(git ls-files 'cut/*.test.cjs')
node --test cloudflare/recuperacion/worker.test.mjs
```

Para Chromium usar una SQLite vacía, migrarla y definir `CUTLESS_TEST_FIXTURE` con la ruta de un archivo temporal nuevo. Cargar los fixtures mediante `python cut/manage.py shell < cut/cutless/tests/browser/fixtures-direcciones-clientes.py`. Levantar `python cut/manage.py runserver 127.0.0.1:8791 --noreload` sobre esa misma base. Configurar `CUTLESS_TEST_ORIGIN=http://127.0.0.1:8791` y `CUTLESS_TEST_BOOTSTRAP` con el CSS de Bootstrap 5.3.0 local. Ejecutar `node cut/cutless/tests/browser/direcciones-clientes.cjs` con Playwright disponible. El archivo de fixtures contiene una sesión sintética temporal. Eliminarlo junto con la base de pruebas al terminar.

## Archivos afectados

- `cut/cutless/direcciones.py` y `dpa_chile.json` proporcionan el catálogo y el acceso a nombres territoriales.
- `cut/cutless/models.py` y la migración `0010` incorporan el código postal y el formato multilínea.
- `cut/cutless/forms/clients.py`, `views/clients.py`, plantillas de alta y edición, parcial `cliente-direccion.html`, JS y CSS de gestión implementan la validación y el flujo.
- `cut/cutless/tests/test_direcciones_clientes.py` y los dos archivos `cut/cutless/tests/browser/*direcciones-clientes*` amplían las pruebas con fixtures sintéticos. El README y el registro mensual enlazan esta documentación.
