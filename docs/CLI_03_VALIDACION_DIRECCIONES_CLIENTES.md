# CLI-03 · Validación de direcciones de clientes

La rama parte de `gy0kuroo/optimizador_materiales:main` en `b2afd7826ad92b9619cb71fdac2aeab4b8247bba`, que incorpora VAL-01B y VAL-02. [PR #41](https://github.com/gy0kuroo/optimizador_materiales/pull/41) · [PR #42](https://github.com/gy0kuroo/optimizador_materiales/pull/42)

## Hallazgo reproducido

En una SQLite desechable del commit base, un POST de alta con país válido `PT` y `aaaaaaaaaa` en región, ciudad, calle y número devolvió 302 y guardó los cuatro valores sintéticos. El formulario ya comprobaba país, campos obligatorios, longitudes, controles básicos, catálogo chileno y código postal chileno. Para el resto aceptaba cualquier texto no vacío dentro de la longitud. La validación de teléfono y RUT vive en `validacion_contacto.py`. El selector JavaScript y el botón de recarga sin JavaScript solo organizan los campos de ubicación.

## Contrato de guardado

| Campo | Regla |
| --- | --- |
| Dirección opcional | Una ficha nueva puede guardar todos los campos de dirección vacíos o con espacios. Empezar por cualquier campo de dirección exige completar país, ciudad o comuna, calle y número. |
| País y ubicación chilena | El país debe estar en el catálogo local de países y territorios. Para Chile se exige un código de región y un código de comuna de esa región, entre las 16 regiones y 346 comunas del catálogo DPA. Se valida la combinación recibida por POST. |
| Región extranjera y ciudad | La región es opcional fuera de Chile y se valida si se envía. El nombre debe contener al menos una letra Unicode. Se admiten nombres breves, escritura no latina, tildes, guiones y apóstrofos. |
| Calle, avenida o camino | Debe contener al menos una letra o un dígito decimal, de modo que una vía numerada también sea válida. Región, ciudad y calle rechazan una entrada compuesta enteramente por ocho o más repeticiones de una misma letra, comparadas sin distinción de mayúsculas después de NFC. |
| Número | Admite `100`, `12-B`, `100A` y `S/N`, además de prefijos o sufijos de una letra, rangos o bloques con guiones o barra y sufijos `bis`, `ter` o `quater`. La comprobación admite dígitos Unicode y usa NFKC sin sustituir el texto que guarda el formulario. Una cadena arbitraria de letras se rechaza. |
| Campos opcionales y controles | El código postal sigue siendo opcional. En Chile, si se escribe, debe tener siete dígitos ASCII. Los campos de texto son de una línea y rechazan categorías Unicode Cc, Cf, Cs, Zl y Zp. Se admiten los conectores de escritura ZWNJ y ZWJ. Las longitudes existentes se conservan. |

Se valida la sintaxis y el contenido mínimo. Una dirección con formato correcto puede ser ficticia y algunas convenciones locales de numeración pueden quedar fuera de los formatos admitidos. La repetición se comprueba en el campo completo, de modo que un nombre corto o uno con repeticiones internas sigue siendo válido. Las pruebas incluyen `Y`, `!Kheis`, nombres con diacríticos y apóstrofos, direcciones japonesas, árabes, persas y canaresas, y calles numeradas.

## Historial, permisos y escrituras

- Al editar una ficha, una dirección estructurada guardada puede conservarse literalmente aunque incumpla la regla actual. Se compara el envío con los valores del propio registro, incluidos los campos omitidos, la representación del navegador y los códigos equivalentes en la ubicación chilena. El país histórico fuera de catálogo se muestra para conservarlo en la ficha. Si se modifica algún campo de dirección, el guardado exige el contrato actual completo.
- Las fichas con dirección legada activa mantienen el paso de conversión de CLI-02. La conversión conserva el texto legado original. La edición de Clientes tampoco reescribe el detalle ni los PDF archivados de Presupuestos emitidos. [Conversión de direcciones legadas](CLI_02_DIRECCIONES_SIMPLIFICADAS_CLIENTES.md)
- Los errores se muestran debajo del campo correspondiente y bloquean las escrituras de la ficha completa. La vista mantiene la transacción, la selección por propietario y la protección CSRF. El botón «Actualizar opciones de ubicación» vuelve a representar los campos sin guardar. El alta rápida desde Presupuestos sigue creando clientes sin dirección introducida.

## Verificación

Las pruebas de Django ejercitan POST directos, incluidos país inválido, combinaciones CUT incompatibles, campos faltantes, controles, números inválidos, conservación histórica y un presupuesto emitido antes de corregir la ficha. El recorrido de Chromium verifica los errores accesibles al usar el formulario, conserva los datos del POST rechazado, corrige una dirección internacional y edita el correo con una dirección histórica intacta. [Pruebas de Django](../cut/cutless/tests/test_validacion_direcciones.py) · [Recorrido de Chromium](../cut/cutless/tests/browser/direcciones-clientes.cjs)

| Comprobación en entorno local aislado | Resultado |
| --- | --- |
| Django completo con SQLite 3.50.4 | 530 aprobadas, 0 fallidas y 8 omitidas. Las omitidas requieren `SELECT FOR UPDATE`. |
| Django completo con PostgreSQL 16.16 | 538 aprobadas, 0 fallidas y 0 omitidas, incluidas las pruebas de concurrencia. |
| JavaScript con Node 24 | 75 aprobadas, 0 fallidas y 0 omitidas. |
| Chromium 156 con Playwright | Aprobados los recorridos de direcciones y contacto. Direcciones cubre ocho combinaciones de ancho y modo, además del flujo CLI-03 con y sin JavaScript a 390 px. |
| `makemigrations --check --dry-run` | Sin cambios detectados en SQLite ni PostgreSQL. |
| `git diff --check` | Sin errores de espacios. |

En una ejecución de navegador con el servidor multihilo, un POST del recorrido de direcciones falló con `database is locked` en SQLite. El recorrido completo pasó al repetirlo con un solo hilo. El recorrido de contacto pasó con la configuración multihilo y registró un tiempo de espera en una ejecución con un solo hilo. La comprobación visual se limitó a Chromium en Linux.

### Reproducción

Ejecutar `python manage.py test --noinput -v 2` y `python manage.py makemigrations --check --dry-run` desde `cut/` con `CUTLESS_ENV=development` y una base local desechable. Desde la raíz, `git ls-files '*.test.cjs' '*.test.mjs' -z | xargs -0 node --test` ejecuta las suites JavaScript.

Para Chromium, migrar una SQLite local vacía, cargar `fixtures-direcciones-clientes.py` mediante `python cut/manage.py shell` y servir la base en loopback con `runserver --noreload --nothreading`. Configurar `CUTLESS_TEST_FIXTURE`, `CUTLESS_TEST_ORIGIN` y las copias locales de Bootstrap 5.3.0 en `CUTLESS_TEST_BOOTSTRAP` y `CUTLESS_TEST_BOOTSTRAP_JS`. Ejecutar `node cut/cutless/tests/browser/direcciones-clientes.cjs` con Playwright y, si se usa Chromium del sistema, definir `CUTLESS_TEST_CHROMIUM`. Para `contacto-clientes.cjs`, usar SQLite y fixture propios con `runserver --noreload`. [Fixture de direcciones](../cut/cutless/tests/browser/fixtures-direcciones-clientes.py) · [Fixture de contacto](../cut/cutless/tests/browser/fixtures-contacto-clientes.py)
