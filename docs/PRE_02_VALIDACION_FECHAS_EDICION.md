# PRE-02 · Validación de vencimiento al editar presupuestos

La rama `fix/pre02-validacion-fechas-edicion` parte de `upstream/main` `2da936f689274ebefac38383115629942aae8d14`. Esa revisión incluye la fusión de UX-05. [PR #31](https://github.com/gy0kuroo/optimizador_materiales/pull/31)

## Causa y corrección

`PresupuestoForm.clean_fecha_validez` comparaba la fecha con el día actual solo en el alta. La edición de un borrador aceptaba un POST con cualquier fecha válida en el calendario, incluso si ya había pasado. Ese formulario tampoco tenía un mínimo en el selector de fecha.

| Operación | Regla |
| --- | --- |
| Crear un presupuesto | La fecha debe ser hoy o posterior. El selector arranca en hoy y usa ese mismo día como mínimo. |
| Editar un borrador con fecha vigente | La fecha debe ser hoy o posterior. El selector usa el mismo mínimo que el alta. |
| Editar un borrador con fecha vencida | Se puede conservar exactamente la fecha guardada al editar otros datos, o cambiarla a hoy o una fecha posterior. Cualquier otra fecha pasada se rechaza. El selector muestra la fecha guardada y una ayuda que explica las opciones. |
| Editar un presupuesto emitido | Se valida el estado mediante su formulario dedicado. La fecha, los datos de la cotización, el detalle emitido y el PDF archivado se conservan. |

El formulario calcula el día civil de `America/Santiago` mediante la zona predeterminada de Django. El mínimo HTML y la validación del POST usan el mismo día para cada solicitud. Un envío después de medianoche en Chile se evalúa con la fecha nueva, incluso si el formulario se abrió el día anterior. La vista carga el borrador por clave y propietario y bloquea la fila durante la edición en PostgreSQL. La excepción compara la fecha enviada con una copia de la fecha de esa instancia guardada. Los valores adicionales del POST no establecen la fecha de referencia ni la identidad del presupuesto. [Formulario](../cut/cutless/forms/budgets.py) · [Vista de edición](../cut/cutless/views/budgets.py) · [Permisos de las rutas](../cut/cutless/urls.py)

## Evidencia anterior y posterior

Se compararon dos servidores locales con copias de la misma SQLite sintética. El día civil de la prueba fue 23/11/2026. Se partió de un vencimiento guardado para el 26/11/2026 y se intentó sustituirlo por el 22/11/2026.

- **Base `2da936f`.** El selector aceptó la fecha, el POST devolvió 302 y tanto el detalle como una nueva apertura del formulario mostraron el 22/11/2026 guardado.
- **PRE-02.** El selector detectó que la fecha era inferior a `min`. Al retirar el atributo para forzar el POST, Django devolvió el formulario con HTTP 200 y un error asociado al campo. Las notas y la selección del plan siguieron en el formulario. Guardar con hoy o mañana funcionó.
- **Borrador vencido.** Se guardaron notas conservando el 18/11/2026. El servidor rechazó sustituirlo por el 22/11/2026 y aceptó actualizarlo a hoy o mañana. Al volver a abrir el formulario con la fecha ya vigente se aplicó el mínimo.

| Chromium | Base · fecha pasada guardada | PRE-02 · fecha pasada rechazada |
| --- | --- | --- |
| Móvil · 390 px | [Captura anterior](evidencia/pre02/antes-390.png) | [Captura posterior](evidencia/pre02/despues-390.png) |
| Escritorio · 1280 px | [Captura anterior](evidencia/pre02/antes-1280.png) | [Captura posterior](evidencia/pre02/despues-1280.png) |

[Captura de la ayuda para conservar una fecha vencida](evidencia/pre02/borrador-vencido-390.png)

## Pruebas

| Prueba | Resultado |
| --- | --- |
| Django dirigida · Presupuestos, permisos, descargas y medios privados | 56 aprobadas en PostgreSQL local. Incluye POST manipulados, fecha desactualizada desde la apertura del formulario, propietario y permisos, preservación de emitidos y PDF, y el mensaje visible. |
| Medianoche en Chile | Se comprobó antes y después de las 00:00 en UTC y `America/Santiago`, tanto en enero (UTC−3) como en julio (UTC−4). La preservación de una fecha guardada siguió disponible al vencer el borrador. |
| Django completa · SQLite | 480 aprobadas, 8 omitidas por requerir bloqueo de filas. |
| Django completa · PostgreSQL 16.16 local | 488 aprobadas. |
| Chromium 156 · PRE-02 | 390 y 1280 px, con y sin JavaScript. Navegador configurado en `Pacific/Kiritimati` y `UTC`, respectivamente. Pasaron la comparación con la base, la validación del POST, el guardado de hoy y mañana y la excepción. |
| Chromium 156 · PRE-01 | Pasaron los cuatro recorridos de alta a 390 y 1280 px con y sin JavaScript. |
| Esquema y diff | `makemigrations --check --dry-run` sin cambios y `git diff --check` limpio. |

Para repetir el recorrido, usa `fixtures-fecha-presupuestos.py` con una SQLite local desechable y la configuración de Chromium y Bootstrap local de PRE-01. Ejecuta `node cut/cutless/tests/browser/fecha-edicion-presupuestos.cjs`. Para comparar, `CUTLESS_TEST_BASE` debe apuntar al segundo servidor local con la revisión base, una copia de la SQLite y la misma clave de sesión. `CUTLESS_TEST_EVIDENCE` permite guardar capturas. Cada combinación de ancho y JavaScript tiene dos borradores propios porque la prueba guarda cambios. [Configuración de PRE-01](UX_01_PRE_01_AJUSTES_INTERFAZ_PRESUPUESTOS.md) · [Pruebas de Django](../cut/cutless/tests/test_presupuestos.py) · [Recorrido de Chromium](../cut/cutless/tests/browser/fecha-edicion-presupuestos.cjs)

## Límites

El control HTML solo admite un mínimo continuo. Por eso se omite `min` cuando la fecha guardada está vencida y Django distingue el valor permitido de cualquier otra fecha pasada. La presentación del calendario depende del navegador. La regla se aplica en el formulario de alta y edición de CutLess. Las columnas, los PDF y los registros históricos se conservan sin migración ni actualización masiva.
