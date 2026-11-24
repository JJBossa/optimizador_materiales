# VAL-02 · Fechas de proyectos

La rama parte de `gy0kuroo/optimizador_materiales:main` en `0dcba553e3146bf30e9e302ffb9b707f5d79311f`, que incorpora VAL-01B. [PR #41](https://github.com/gy0kuroo/optimizador_materiales/pull/41)

## Reglas

- Las dos fechas son opcionales. Una fecha nueva o modificada debe ser igual o posterior al día civil vigente en `America/Santiago`. El servidor calcula ese día para cada formulario, incluido cada POST, aunque la página se haya abierto antes de medianoche.
- Si hay dos fechas, la finalización debe ser igual o posterior al inicio. Un rango invertido que ya estaba almacenado se puede conservar si ambas fechas siguen iguales. Cambiar una de ellas obliga a que el rango resultante cumpla el orden.
- Una fecha pasada se puede reenviar si coincide con la que tenía guardada ese campo en el proyecto autorizado. En edición, omitir el campo conserva su fecha y enviar un valor explícitamente vacío la elimina. Los datos históricos se mantienen sin migraciones.
- Proyectos aplica `min` con el día de Chile a los campos nuevos o sin fecha histórica vencida. Un campo con fecha pasada guardada muestra cómo conservarla, borrarla o cambiarla. El orden entre campos se comprueba en Django, de modo que se puedan cambiar ambas fechas en el mismo envío.
- Alta y edición usan los mismos campos HTML de Django. Los errores en español aparecen debajo de la fecha correspondiente, con referencias accesibles al error y a la ayuda. Un POST rechazado conserva las fechas enviadas, incluidas las vacías. Si un valor malformado no puede visualizarse en el control nativo, aparece como texto debajo del campo.
- La edición valida contra la fila del propietario, con bloqueo de fila en PostgreSQL. La validación precede al guardado y a los cambios de asociaciones. El formulario solo permite elegir clientes y optimizaciones del propietario. VAL-01B sigue aplicándose al nombre del proyecto.

## Resultados locales

| Comprobación | Resultado |
| --- | --- |
| Django 5.2.19 con SQLite 3.50.4 | 529 casos, 521 aprobados, 0 fallidos y 8 omitidos por falta de `select_for_update`. |
| Django 5.2.19 con PostgreSQL 16.16 aislado | 529 aprobados, 0 fallidos y 0 omitidos. |
| JavaScript con Node 24.22.1 | 75 aprobados, incluidos 8 del Worker de recuperación, 0 fallidos y 0 omitidos. |
| Chromium 156 con Playwright 1.62.1 | VAL-02 pasó seis escenarios a 320, 390 y 1280 px con y sin JavaScript. También pasaron los recorridos de estados de Proyectos y de límites de VAL-01B. |
| Esquema y diff | `makemigrations --check --dry-run` informó que no había cambios en ambos motores. `git diff --check` pasó. |

Las pruebas de Django cubren ayer, hoy, mañana, valores vacíos o malformados, orden del rango, medianoche chilena en verano e invierno, conservación histórica, POST manipulado, permisos y ausencia de escrituras parciales. La demora entre GET y POST se prueba con reloj simulado y tanto la zona por defecto como la activa en UTC. [Pruebas de Django](../cut/cutless/tests/test_fechas_proyectos.py)

El recorrido de navegador comprobó la restricción nativa, el rechazo tras saltarla, la conservación de los valores en la respuesta, el guardado de fechas históricas y la corrección del rango. Usó una zona del navegador distinta de Chile y una base desechable. El entorno devolvió 403 al descargar WebKit y también al descargar las capas de la imagen oficial de Playwright. La interacción con el selector nativo de Safari en iOS queda pendiente de verificación. [Fixture](../cut/cutless/tests/browser/fixtures-fechas-proyectos.py) · [Recorrido](../cut/cutless/tests/browser/fechas-proyectos.cjs)

## Reproducción

Desde `cut/`, ejecutar `python manage.py test --noinput -v 2` y `python manage.py makemigrations --check --dry-run` con `CUTLESS_ENV=development` y la configuración de cada motor apuntando a una base local desechable. Desde la raíz, `git ls-files '*.test.cjs' '*.test.mjs' -z | xargs -0 node --test` ejecuta las pruebas de JavaScript.

Para Playwright, migrar una SQLite local vacía, indicar un archivo nuevo en `CUTLESS_TEST_FIXTURE` y cargar el fixture con `python cut/manage.py shell < cut/cutless/tests/browser/fixtures-fechas-proyectos.py`. Servir la misma base en loopback y definir `CUTLESS_TEST_ORIGIN` y las rutas locales de Bootstrap 5.3.0 en `CUTLESS_TEST_BOOTSTRAP` y `CUTLESS_TEST_BOOTSTRAP_JS`. Ejecutar `node cut/cutless/tests/browser/fechas-proyectos.cjs`. `CUTLESS_TEST_CHROMIUM` selecciona un Chromium instalado y `CUTLESS_TEST_ENGINE=webkit` usa WebKit con el perfil iPhone 13 cuando el motor está instalado.
