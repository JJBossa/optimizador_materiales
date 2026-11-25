# PRO-03 · Ciclo de vida de proyectos

La base `8ae95c815ad8ef7df68c57de8c45fd14ca592890` incorpora PRE-03. Antes, los formularios de proyectos permitían seleccionar cualquier estado al crear o editar, y las fechas de finalización pasadas no se reflejaban en el estado mostrado.

## Estados y acciones

Cada proyecto nuevo empieza en Planificación. Django conserva los cuatro códigos operativos existentes. Atrasado es el estado visible de un proyecto en Planificación o En proceso cuando tiene una fecha de finalización anterior al día civil en `America/Santiago`. Su fecha de término incluye todo ese día.

| Estado operativo | Acciones disponibles |
| --- | --- |
| Planificación | Iniciar proyecto o Cancelar proyecto |
| En proceso | Completar proyecto o Cancelar proyecto |
| Completado o Cancelado | Consultar y editar los datos del proyecto según los permisos existentes |

El atraso conserva las acciones propias del estado operativo. Iniciar antes de la fecha prevista muestra un aviso y el proyecto conserva sus fechas. La finalización y la cancelación requieren confirmación. Cancelar conserva el proyecto y sus relaciones. La eliminación mantiene su flujo y sus permisos propios.

El listado filtra el estado visible en SQL. Planificación y En proceso excluyen los atrasados. El detalle, el formulario de edición y el historial del cliente muestran el mismo estado calculado. Al reprogramar un proyecto atrasado hasta hoy o una fecha futura, o al borrar explícitamente la fecha de término, vuelve a verse su estado operativo. Los GET no escriben estados ni fechas. No se requiere migración.

Los formularios de alta y edición ya no cambian estados. Un POST legado con un solo estado idéntico al guardado se admite sin modificarlo. Un cambio debe enviarse a la acción POST del detalle con CSRF. Los proyectos completados y cancelados conservan la edición de datos y la gestión de optimizaciones que ya tenían. Esas operaciones no reabren su ciclo. Las reglas de VAL-01B, VAL-02 y VAL-03 siguen aplicándose.

## Integridad y concurrencia

El endpoint de estado valida autenticación, permiso, propietario, método POST y CSRF. Lee la fila bajo bloqueo y verifica que el origen enviado coincida con el estado real. El servicio valida la transición y vuelve a exigir ese estado en la actualización. Solo se escriben `estado` y la marca de actualización. Las confirmaciones se muestran con detalles HTML nativos y funcionan sin JavaScript.

La edición usa un identificador de revisión que incorpora estado, marca de actualización y planes asociados. El formulario visible siempre lo envía. También es obligatorio para reemplazar la selección de planes. Si la lista se envía vacía mediante su marcador, se quitan los planes seleccionables. Al omitir la selección entera se conservan los planes. Omitir el cliente conserva la relación y enviar la opción vacía la elimina. VAL-02 distingue de la misma forma las fechas omitidas y vacías y conserva los rangos invertidos históricos intactos.

Al editar o asociar desde el módulo, Django bloquea el proyecto antes de los planes y bloquea los planes en orden de clave. En PostgreSQL se usa un bloqueo de proyecto que permite comprobar claves foráneas. Solo se pueden vincular planes propios sin proyecto y mantener planes ya vinculados al mismo proyecto. Los cambios de estado no alteran fechas estimadas, clientes, planes, precios ni presupuestos. La fecha real de finalización podría registrarse en una mejora independiente.

## Integración futura

`services/proyectos.py` comparte el predicado SQL de atraso entre la anotación de estado visible y `proyectos_atrasados`. En una consulta acotada al usuario, NOTI-01 podrá usar `inicios_planificados` para buscar fechas previstas de inicio de proyectos todavía en Planificación y `finales_planificados` para buscar finales estimados de planes activos. Ambos reciben límites inclusivos. Para los inicios ya pasados se puede usar como límite superior el día comercial menos uno. La fecha comercial se comparte con PRE-03 a través de `services/calendario.py`. Las consultas de PRO-03 no crean notificaciones.

## Archivos

| Grupo | Cambios |
| --- | --- |
| `services/calendario.py`, `services/presupuestos.py` y `services/proyectos.py` | Fecha comercial compartida con PRE-03, cálculo de estado visible y matriz de transiciones. |
| `forms/projects.py`, `views/projects.py`, `views/clients.py` y `urls.py` | Validación de edición, bloqueo, endpoint POST, filtros y estados en el historial. |
| Plantillas de alta, edición, detalle, listado, historial e inclusiones | Estado inicial, confirmaciones, aviso de inicio futuro, etiquetas y acciones. El tutorial explica el filtro Atrasado. |
| Pruebas de Django y Chromium | Ciclo, compatibilidad histórica, permisos, fecha de Chile, concurrencia y regresiones de VAL-02, VAL-03 y PRE-03. |

Las regresiones que enviaban un estado distinto desde la edición ahora comprueban el guardado de otros campos sin cambiar el estado. Las pruebas que reemplazan planes envían la revisión del formulario. El caso de fraude de estado y las transiciones autorizadas se comprueban de forma separada.

## Verificación local

Desde `cut/`, con una base desechable en desarrollo, ejecutar `python manage.py test --noinput -v 2`, `python manage.py check`, `python manage.py makemigrations --check --dry-run`, `python manage.py migrate --noinput` y `python manage.py migrate --plan`. Desde la raíz, ejecutar `git ls-files '*.test.cjs' '*.test.mjs' -z | xargs -0 node --test` y `git diff --check`.

Para Chromium, migrar una SQLite desechable, cargar `fixtures-ciclo-proyectos.py` mediante `python cut/manage.py shell` y servirla en loopback con `runserver --noreload --nothreading`. Configurar `CUTLESS_TEST_FIXTURE`, `CUTLESS_TEST_ORIGIN`, las copias locales `CUTLESS_TEST_BOOTSTRAP` y `CUTLESS_TEST_BOOTSTRAP_JS`, y `CUTLESS_TEST_CHROMIUM` si se usa el binario del sistema. Ejecutar `node cut/cutless/tests/browser/ciclo-proyectos.cjs`. `CUTLESS_TEST_EVIDENCE` permite guardar capturas sintéticas fuera de Git.

| Comprobación | Resultado |
| --- | --- |
| Django completo con PostgreSQL 16.16 | 568 aprobadas, 0 fallidas, 0 omitidas. Incluye concurrencia de PRO-03 y PRE-03. |
| Django completo con SQLite 3.50.4 | 556 aprobadas, 0 fallidas, 12 omitidas por requerir `SELECT FOR UPDATE`. Las doce aprobaron en PostgreSQL. |
| JavaScript con Node 24.22.1 | 79 aprobadas, 0 fallidas, 0 omitidas. |
| Chromium 156.0.8078.79 y Playwright 1.62.1 | 5 recorridos aprobados, 0 fallidos. PRO-03 y PRE-03 pasaron a 320, 390, 768 y 1440 px, con temas claro y oscuro, teclado y JavaScript deshabilitado a 320 px. También pasaron las regresiones de fechas VAL-02, etiquetas de Proyectos y acciones de gestión. |
| `check`, `makemigrations --check --dry-run`, `migrate --plan` y `git diff --check` | Sin incidencias ni cambios de migración. Ambos esquemas locales resultaron sin migraciones pendientes. |

El recorrido de proyectos usa la zona del navegador `Pacific/Kiritimati` y comprueba las fechas que determinó el servidor en Chile. Las pruebas de Django cubren medianoche en verano e invierno y el salto al horario de verano. Las capturas `pro03-reprogramacion-movil.png` y `pro03-reprogramado-escritorio.png` muestran un error de rango conservando la entrada y la recuperación del estado operativo después de corregir la fecha. Se guardaron fuera de Git.

Firefox y WebKit quedaron sin ejecutar porque las descargas de Playwright devolvieron HTTP 403. El viewport móvil se probó en Chromium y Safari de iPhone queda sin verificar.
