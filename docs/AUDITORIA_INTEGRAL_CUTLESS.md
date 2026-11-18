# Corrección integral de CutLess

## A. Resumen ejecutivo

Se verificaron los 17 hallazgos en la rama local `work`, sobre la base `8b0b661f59fbde1431fcc1b3a272433db55c9d52`. Los cambios están preparados para revisión en el árbol de trabajo. Las verificaciones usaron SQLite temporal, un clúster PostgreSQL 16.2 por socket local, correo en memoria y un navegador con las solicitudes externas bloqueadas. Render, Supabase y las ramas remotas quedaron fuera de la ejecución.

Los riesgos que requieren seguimiento antes del despliegue son la capacidad con la configuración real de Gunicorn, las cotizaciones históricas sin desglose recuperable y la recuperación ante una reversión después de guardar piezas en el formato nuevo.

## B. Registro de hallazgos

| Hallazgo | Estado | Problema y solución | Verificación |
| --- | --- | --- | --- |
| H01 | Verificado | La administración de cuentas privilegiadas y el otorgamiento del rol de administrador exigen un superusuario. La edición aplica validadores de Django y guarda dentro de una transacción. | Las solicitudes del administrador común reciben 403 sobre una cuenta privilegiada, sus datos siguen intactos, un superusuario puede editar y se rechazan contraseñas inválidas. `usuarios/views.py`, `usuarios/forms.py`, `usuarios/test_seguridad_auditoria.py`. |
| H02 | Verificado | El prefijo `piezas:v1:` puede formar parte de un nombre histórico. El lector valida el JSON completo y conserva el formato histórico cuando todas sus filas son válidas. Un listado ambiguo conserva su texto original y queda bloqueado para operaciones que puedan perder filas. | Se reprodujo la colisión con el lector anterior. Pasaron creación, edición, duplicación, plantillas y exportaciones PDF y XLSX con prefijos literales, comas, Unicode y saltos de línea. Se verificó HTTP 422 sin reescritura de registros ambiguos. `cutless/pieces.py`, `cutless/tests/test_pieces.py`, `cutless/tests/test_plantillas.py`, `cutless/tests/test_resultado_recarga.py`. |
| H03 | Verificado | Conforme a la política aprobada, el borrador se calcula con las líneas vigentes y se vuelve a guardar al editar o emitir. La emisión guarda una copia de los planes y datos del cliente. Luego se puede cambiar el estado sin alterar las cifras. Los históricos conservan el total registrado y, cuando está disponible y autorizado, su PDF original. | El borrador refleja cambios y eliminaciones de planes. Una cotización nueva mantiene el total y sus líneas incluso después de eliminar un plan. Los históricos se muestran con un aviso y sin reconstruir un desglose que no se puede verificar. `cutless/models.py`, `cutless/views/budgets.py`, `cutless/tests/test_presupuestos.py`. |
| H04 | Verificado | Alta y edición comparten la autorización de costos. Los selectores limitan las relaciones al propietario y a los materiales predefinidos. La edición sin permiso conserva costos y asociaciones previamente guardados. | Un POST con relaciones ajenas produce errores. Se guarda el material compartido autorizado y una edición posterior sin permiso conserva el costo original. `cutless/permissions.py`, `cutless/forms/optimization.py`, `cutless/views/optimization.py`, `cutless/tests/test_resultado_recarga.py`. |
| H05 | Verificado | Django genera y comprueba los enlaces de recuperación. Las cuentas elegibles con correo compartido reciben enlaces separados en ese mismo buzón. Las respuestas públicas son genéricas. Los correos repetidos se admiten para conservar las cuentas existentes. Una futura política de correo único requeriría verificar direcciones y resolver duplicados explícitamente. | Casos de correo compartido, ausente e inactivo. Los enlaces inválidos, vencidos y usados se rechazan. El token inicial se sustituye por una URL sin token antes de mostrar el formulario. `usuarios/views.py`, `usuarios/urls.py`, `usuarios/test_seguridad_auditoria.py`. |
| H06 | Verificado | Favoritos, tutorial y cierre de sesión exigen POST. Favoritos conserva los retornos autorizados por host y esquema. | Los GET no modifican estado. POST con CSRF inválido se rechaza y el retorno de favoritos se limita a destinos permitidos. `usuarios/views.py`, `cutless/views/historial.py`, `cutless/tests/test_history_horizontal.py`. |
| H07 | Verificado | Las celdas con texto libre del usuario se escriben como cadenas de Excel. | OpenPyXL reabre las tres variantes de XLSX. Se verifican nombres con signos de fórmula, Unicode y un literal que parece un error de Excel. `cutless/exports/excel.py`, `cutless/tests/test_exportaciones_auditoria.py`. |
| H08 | Verificado | Los planos excluyen la reserva de sierra antes de girar el tablero. La superficie reservada y los sobrantes se distinguen en la geometría compartida por web, PDF y PNG. | Pruebas de área, rotación, ausencia de solapamiento y reservas de 0, 3 y 10 mm. La superficie geométrica sigue dependiendo del modelo de corte. `cutless/packing.py`, `cutless/services/board_presentation.py`, `cutless/tests/test_board_presentation.py`. |
| H09 | Verificado | La estimación rechaza parámetros no finitos, negativos o velocidad cero y utiliza la cantidad de tableros guardada cuando existe. | Se verificaron cálculo con varios tableros, estimación para registros antiguos, división exacta y desbordamientos. `cutless/views/analytics.py`, `cutless/tests/test_tiempo_auditoria.py`. |
| H10 | Verificado | La creación bloquea la fila del propietario antes de asignar el número. El sufijo se compara como número y la restricción única por usuario se conserva. | Dos altas simultáneas del primer presupuesto en PostgreSQL reciben `0001` y `0002`. Se cubren cuentas distintas y la transición de `9999` a `10000` y `10001`. `cutless/models.py`, `cutless/views/budgets.py`, `cutless/tests/test_presupuestos.py`. |
| H11 | Verificado | El PDF de presupuesto pagina las piezas y notas, repite encabezados de tabla y muestra el total con dos decimales. | Se generaron presupuestos cortos y un caso con 65 planes. Se comprobó el encabezado repetido, el último plan y el total. `cutless/exports/pdf.py`, `cutless/tests/test_exportaciones_auditoria.py`. |
| H12 | Verificado | Se documentó el criterio existente por área, rectángulos libres, orientación y tablero. La optimización de rendimiento ejecuta la colocación una sola vez, después de elegir el mismo candidato. | Caso determinista con rotación, pieza imposible y 650 comparaciones completas con la base. `README.md`, `cutless/packing.py`, `cutless/tests/test_precision_rnf09.py`. |
| H13 | Verificado | El script de plantillas crea una cuenta desechable sin contraseña reutilizable en SQLite en memoria. Las herramientas comparten un arranque que sustituye el entorno heredado y comprueba el motor. | Un archivo centinela indicado mediante variables heredadas permanece intacto, una respuesta HTTP 500 provoca un fallo y 16 páginas respondieron HTTP 200. `smoke_test_templates.py`, `cutless_project/standalone.py`, `cutless/tests/test_smoke_auditoria.py`, `tools/performance_rnf03.py`. |
| H14 | Verificado | Modelos, formularios y preferencias usan las mismas opciones de unidad. Las conversiones comparten sus factores. | Persistencia y reapertura de materiales y plantillas en milímetros, validación del modelo y regresiones de conversión y edición. `cutless/units.py`, `cutless/models.py`, `cutless/tests/test_precision_rnf09.py`. |
| H15 | Verificado | «Omitir por ahora» tiene un formulario separado. El envío implícito del primer paso avanza al segundo. | Enter en un control de opciones, clic en Continuar y clic explícito en Omitir comprobados en Chromium y en las pruebas JavaScript. `usuarios/templates/usuarios/configuracion_inicial.html`, `usuarios/static/usuarios/js/configuracion-inicial.js`. |
| H16 | Verificado | Omitir conserva un perfil ya configurado. En un primer acceso aplica el modo esencial y conserva la apariencia. | Se comprobaron ambos casos y la persistencia de una herramienta opcional al reabrir. `usuarios/views.py`, `usuarios/test_inicio.py`. |
| H17 | Verificado | El borrador se retira después de una confirmación del servidor para esa revisión. Un error conserva las opciones válidas y permite recuperar la selección. | Error de validación en Django y HTTP 500 simulado en Chromium, con recuperación tras reabrir. La persistencia entre páginas depende de que el navegador permita almacenamiento local. `usuarios/test_inicio.py`, `usuarios/tests_js/configuracion-inicial.test.cjs`. |

## C. Resultados de pruebas

| Pruebas | Aprobadas | Fallidas | Omitidas |
| --- | ---: | ---: | ---: |
| Django con SQLite temporal | 305 | 0 | 1 |
| Django con PostgreSQL 16.2 local | 306 | 0 | 0 |
| JavaScript con Node | 52 | 0 | 0 |
| Páginas del comprobador aislado | 16 | 0 | 0 |

Se conservaron las 267 pruebas Django y las 48 JavaScript existentes. Se añadieron 39 pruebas Django, incluidas seis para la revisión de H02, y cuatro JavaScript. La omisión en SQLite corresponde a la prueba de bloqueo por fila, aprobada en PostgreSQL. También pasaron `makemigrations --check --dry-run`, la comprobación local de configuración de Gunicorn y `git diff --check`.

La primera ejecución en PostgreSQL encontró 11 errores de conexión en dos módulos de descargas. La base `8b0b661` reprodujo los mismos 11. Las pruebas cerraban manualmente una respuesta que el cliente de Django cierra al consumir su flujo, lo que interrumpía la transacción del caso de prueba. Se ajustó el consumo de respuestas preservando las verificaciones de contenido, seguridad y almacenamiento. La revisión final de H02 aprobó 29 pruebas relacionadas y los 306 casos de la suite con PostgreSQL local.

Las pruebas de seguridad cubren la jerarquía, los validadores, la recuperación, los métodos HTTP, la protección CSRF y la autorización por propietario. En el navegador se probaron los eventos nativos de teclado y mouse y un HTTP 500 simulado sin salir del entorno local.

## D. Rendimiento y estabilidad

Misma carga en dos copias locales, tablero de 122 × 244 cm, rotación activa y sierra de 3 mm. Una ejecución por caso y versión, en procesos separados, con el cliente Django siguiendo el POST hasta el GET de resultado. Límite de 25 segundos y 900 MiB de espacio de direcciones por proceso. RSS mide el máximo del proceso Python. La tabla mide tiempo del servidor y renderizado de HTML, sin cronometrar un navegador.

| Piezas | Tableros | POST y GET antes | POST y GET después | RSS antes | RSS después |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 1 | 1,060 s | 0,790 s | 117,3 MiB | 82,8 MiB |
| 50 | 3 | 1,281 s | 0,731 s | 140,5 MiB | 83,4 MiB |
| 300 | 14 | 2,737 s | 0,773 s | 198,9 MiB | 85,4 MiB |
| 1.000 | 28 | 5,200 s | 0,847 s | 268,8 MiB | 91,1 MiB |
| 2.000 | 67 | 11,202 s | 0,966 s | 324,3 MiB | 100,0 MiB |
| 100 | 100 | 13,441 s | 0,774 s | 359,1 MiB | 88,8 MiB |

El alta, la edición y los PDF vectoriales aprovechan la geometría sin generar PNG de todos los tableros. La descarga de un PNG genera el tablero solicitado. El motor calcula la puntuación de los candidatos antes de actualizar la geometría del ganador. El servidor limita el formulario a 20 tipos antes de construir los formularios, con el límite existente de 100 unidades por tipo.

En una prueba adicional, cuatro cuentas solicitaron a la vez planes de 300 piezas sobre PostgreSQL local. Las cuatro llegaron a HTTP 200 y colocaron todas sus piezas. El mayor tiempo fue 1,093 s y el RSS de Python alcanzó 106,1 MiB. Las mediciones sirven como referencia para verificar límites de memoria, tiempos de espera y cantidad de workers con una carga representativa en un entorno de preproducción. El informe RNF-03 anterior conserva sus propias mediciones del navegador.

## E. Compatibilidad

- `cutless.0005` agrega una columna JSON anulable a presupuestos. No reconstruye cotizaciones existentes.
- `cutless.0006` amplía las opciones de unidades de materiales, optimizaciones y plantillas a milímetros. No convierte registros existentes.
- El lector nuevo admite las piezas históricas. Un binario anterior a esta corrección requiere un lector compatible antes de abrir piezas guardadas en formato JSON versionado.
- PostgreSQL 16.2 local ejecutó ambas migraciones y la batería completa. Queda por validar una copia representativa de datos históricos y la capacidad de los servicios administrados.
- La interfaz restringe a los superusuarios el otorgamiento de roles privilegiados. A partir de la emisión, el formulario de presupuesto permite cambiar el estado manteniendo sus términos congelados.

## F. Archivos de revisión

Los archivos se enumeran respecto de la raíz del repositorio.

- `README.md`
- `cut/cutless/exports/excel.py`
- `cut/cutless/exports/pdf.py`
- `cut/cutless/forms/optimization.py`
- `cut/cutless/forms/plantillas.py`
- `cut/cutless/migrations/0005_presupuesto_detalle_emitido.py`
- `cut/cutless/migrations/0006_alter_material_unidad_medida_and_more.py`
- `cut/cutless/models.py`
- `cut/cutless/packing.py`
- `cut/cutless/permissions.py`
- `cut/cutless/pieces.py`
- `cut/cutless/render.py`
- `cut/cutless/services/board_presentation.py`
- `cut/cutless/services/comparison.py`
- `cut/cutless/services/optimization.py`
- `cut/cutless/static/cutless/css/sidebar-navigation.css`
- `cut/cutless/templates/cutless/base.html`
- `cut/cutless/templates/cutless/calcular_tiempo.html`
- `cut/cutless/templates/cutless/detalle_presupuesto.html`
- `cut/cutless/templates/cutless/editar_estado_presupuesto.html`
- `cut/cutless/templates/cutless/editar_optimizacion.html`
- `cut/cutless/templates/cutless/includes/authenticated-navigation.html`
- `cut/cutless/templates/cutless/lista_presupuestos.html`
- `cut/cutless/tests/test_board_presentation.py`
- `cut/cutless/tests/test_exportaciones_auditoria.py`
- `cut/cutless/tests/test_history_horizontal.py`
- `cut/cutless/tests/test_media_privada.py`
- `cut/cutless/tests/test_pieces.py`
- `cut/cutless/tests/test_png_actual.py`
- `cut/cutless/tests/test_precision_rnf09.py`
- `cut/cutless/tests/test_presupuestos.py`
- `cut/cutless/tests/test_resultado_recarga.py`
- `cut/cutless/tests/test_smoke_auditoria.py`
- `cut/cutless/tests/test_tiempo_auditoria.py`
- `cut/cutless/units.py`
- `cut/cutless/utils.py`
- `cut/cutless/views/analytics.py`
- `cut/cutless/views/budgets.py`
- `cut/cutless/views/common.py`
- `cut/cutless/views/exports.py`
- `cut/cutless/views/historial.py`
- `cut/cutless/views/optimization.py`
- `cut/cutless/views/plantillas.py`
- `cut/cutless/views/projects.py`
- `cut/cutless_project/standalone.py`
- `cut/smoke_test_templates.py`
- `cut/usuarios/forms.py`
- `cut/usuarios/models.py`
- `cut/usuarios/static/usuarios/js/configuracion-inicial.js`
- `cut/usuarios/templates/usuarios/admin_dashboard.html`
- `cut/usuarios/templates/usuarios/configuracion_inicial.html`
- `cut/usuarios/templates/usuarios/email_reset_password.html`
- `cut/usuarios/templates/usuarios/reset_password_email.txt`
- `cut/usuarios/templates/usuarios/reset_password_subject.txt`
- `cut/usuarios/test_inicio.py`
- `cut/usuarios/test_seguridad_auditoria.py`
- `cut/usuarios/tests_js/configuracion-inicial.test.cjs`
- `cut/usuarios/urls.py`
- `cut/usuarios/views.py`
- `docs/AUDITORIA_INTEGRAL_CUTLESS.md`
- `tools/performance_rnf03.py`
- `cut/cutless/templates/cutless/editar_plantilla.html`
- `cut/cutless/templates/cutless/includes/tutorial-scripts.html`
- `cut/cutless/tests/test_plantillas.py`

## G. Preparación para integrar

1. Revisar el diff de `work` y, una vez aprobado, registrar los cambios en commits locales para incorporarlos a `fix/auditoria-integral-cutless` en el fork. Verificar la base de destino antes de aplicar los commits.
2. Probar el conjunto en preproducción con una copia sanitizada que incluya cotizaciones históricas, piezas con nombres ambiguos y cuentas con correos compartidos. Comprobar la recepción de correo y la carga con los límites de Gunicorn previstos.
3. Antes de una aplicación autorizada en producción, preparar un respaldo verificable de Supabase y de los archivos privados. Aplicar `0005` y `0006` antes de habilitar el código que guarda las instantáneas.
4. Si se requiere volver a una versión anterior después de nuevas escrituras, conservar la columna de instantáneas y usar una versión de recuperación con el lector de piezas versionadas. Un retorno a la base original exige un plan separado para recuperar o conservar los datos escritos desde la actualización.
5. Después de una integración autorizada, revisar login, recuperación, asistente, edición y exportación de un plan, emisión de presupuestos, numeración y métricas de errores, latencia y memoria.
