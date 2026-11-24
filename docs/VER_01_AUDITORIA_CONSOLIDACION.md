# VER-01 · Auditoría de consolidación de CutLess

La auditoría se realizó el 23 y 24 de noviembre de 2026, hora de Chile, sobre `upstream/main` en `e52536b514890bc945f5a5988acc60480e51db57`, commit de fusión del PR #35 (SEC-08). Se verificó el historial de primer padre desde la fusión del PR #26. Los ensayos se realizaron en Linux con datos sintéticos, SQLite y PostgreSQL locales y servidores HTTP en loopback. [Commit de fusión](https://github.com/gy0kuroo/optimizador_materiales/commit/e52536b514890bc945f5a5988acc60480e51db57)

## Diagnóstico

- **APROBADO** · Las comprobaciones locales permiten pasar a una validación operativa controlada con cuentas y datos de prueba, previa identificación del artefacto y del esquema del entorno. El alcance excluye el uso del enlace de Proyectos que figura entre los hallazgos.
- **PENDIENTE DE VERIFICACIÓN** · Versión activa y estado operativo en Render, migraciones aplicadas en Supabase, controles operativos de SEC-07, descargas posteriores a UX-05 en Safari de un iPhone físico y Chrome para Windows.
- **PROBLEMA CONFIRMADO** · `main` conserva tres defectos de prueba. Los reensayos con correcciones limitadas a las pruebas pasaron. También persiste un enlace sin destino funcional en el historial del cliente. El registro de noviembre mostraba SEC-08 y el redondeo de Historial como pendientes de integración. Se corrigieron ambas referencias. [Registro de noviembre](REGISTRO_CAMBIOS_NOVIEMBRE_2026.md)

## Inventario de los cambios presentes en main

| PR | Fusión | Tipo | Cambios integrados |
| --- | --- | --- | --- |
| [#27](https://github.com/gy0kuroo/optimizador_materiales/pull/27) | `fd90c92` | Funcional y visual | UX-01 ajusta el aviso de dirección histórica. PRE-01 valida vencimientos nuevos con el día civil de Chile. VIS-01 ajusta el selector de estados de Proyectos y VIS-02 unifica acciones de gestión. UX-02 enlaza a Findic. |
| [#28](https://github.com/gy0kuroo/optimizador_materiales/pull/28) | `671e6a0` | Visual y funcional | VIS-03 ajusta las acciones de Estadísticas. UX-03 centraliza la indicación de descarga y el tratamiento de las respuestas. |
| [#29](https://github.com/gy0kuroo/optimizador_materiales/pull/29) | `07edb2b` | Funcional y visual | UX-04 permite pintar el indicador antes de iniciar la descarga, incluido el flujo de PDF rápido. |
| [#30](https://github.com/gy0kuroo/optimizador_materiales/pull/30) | `35aa5d5` | Visual | VIS-04 distribuye las acciones de Historial según el ancho disponible. |
| [#31](https://github.com/gy0kuroo/optimizador_materiales/pull/31) | `2da936f` | Funcional | UX-05 usa la activación nativa de los enlaces de descarga en iOS y conserva la navegación de los PDF archivados. |
| [#32](https://github.com/gy0kuroo/optimizador_materiales/pull/32) | `bed8581` | Funcional | PRE-02 valida la fecha al editar y permite conservar exactamente un vencimiento histórico en un borrador. |
| [#33](https://github.com/gy0kuroo/optimizador_materiales/pull/33) | `2d118dc` | Visual | VIS-05 elimina decimales sobrantes al presentar importes iniciales y conserva la precisión y las entradas de formularios con errores. |
| [#34](https://github.com/gy0kuroo/optimizador_materiales/pull/34) | `b34b6a4` | Visual | VIS-06 muestra ambos costos de una optimización nueva como campos vacíos con ayuda `0`; en edición conserva los valores, incluido el cero almacenado. |
| [#35](https://github.com/gy0kuroo/optimizador_materiales/pull/35) | `e52536b` | Seguridad | SEC-08 protege el catálogo compartido y su propiedad histórica en Materiales y Django Admin. |

El diff entre `a43a526` y `e52536b` abarca 155 archivos y deja intactas las migraciones. Las entradas de los PR #27 a #34 concordaban con el historial. El commit `4204f5c`, que redondeó los selectores de Historial, entró en `main` con el PR #7 y la fusión `a98f00d`. El modo directo de Brevo en `2715ab5` sigue pendiente de integración en el fork. La activación operativa de la recuperación pública queda pendiente de verificación. [Registro de noviembre](REGISTRO_CAMBIOS_NOVIEMBRE_2026.md) · [PR #7](https://github.com/gy0kuroo/optimizador_materiales/pull/7) · [Modo directo en el fork](https://github.com/JJBossa/optimizador_materiales/tree/feature/recuperacion-password-brevo-directa)

## Regresiones y estado de módulos

| Comprobación | Estado | Resultado |
| --- | --- | --- |
| Django 5.2.19, PostgreSQL 19.0 local | **PROBLEMA CONFIRMADO** | 501 pruebas, 500 aprobadas, una fallida y cero omitidas sobre `e52536b`. |
| Django 5.2.19, SQLite 3.50.4 local | **PROBLEMA CONFIRMADO** | 501 pruebas, 492 aprobadas, una fallida y ocho omitidas porque SQLite carece de `select_for_update`. Los ocho casos aprobaron en PostgreSQL. |
| Reensayo Django de la edición ajena | **APROBADO** | El caso corregido aprobó por separado en ambos motores y confirmó que el precio conservó su valor. Las cifras de las suites de `main` se mantienen arriba. |
| JavaScript de CutLess, Node 24.22.1 | **APROBADO** | 67 aprobadas, cero fallidas. Se recuperó el resumen final de la ejecución anterior. |
| Cloudflare Worker, Node 24.22.1 | **APROBADO** | Ocho aprobadas, cero fallidas, con dobles de servicios. Se recuperó el resumen final de la ejecución anterior. |
| Contacto y NUM-01 en Chromium | **APROBADO** con pruebas corregidas | Dos guiones reejecutados con y sin JavaScript. Los fallos de los guiones originales se describen abajo. |
| Otros recorridos en Chromium | **APROBADO** | Pasaron 13 guiones de la primera ejecución. Incluyen dirección histórica y RUT, estados de Proyectos, acciones de gestión, Findic, alta y edición de Presupuestos, importes, costos VIS-06, Estadísticas, Historial, descargas, activación nativa emulada e indicador de descarga. |
| Precisión NUM-03 y navegación de visores en Chromium | **APROBADO** | Dos guiones adicionales sin cambios. NUM-03 aprobó 20 escenarios con y sin JavaScript. En los visores de Estadísticas, Historial y Resultados se verificaron Atrás, Adelante, foco, recarga y restauración desde caché en los paneles de Estadísticas e Historial. |
| Dispositivos y navegadores de UX-05 | **PENDIENTE DE VERIFICACIÓN** | Safari en un iPhone físico y Chrome en Windows. El recorrido nativo de esta auditoría emuló iOS en Chromium. |
| Integridad del diff | **APROBADO** | `git diff --check` para la documentación y para el commit local de pruebas. |

Las suites Django se ejecutaron desde `cut/` con `python manage.py test --noinput -v 2`, Python `3.13.12` y cada motor local en desarrollo. Se usaron `node --test` para los archivos `*.test.cjs` de `cut/` y una ejecución aparte para `cloudflare/recuperacion/worker.test.mjs`. Los recorridos utilizaron Chromium `156.0.8078.79`. Se recuperó el borrador y la evidencia final disponible del historial de la ejecución anterior. Sus suites Django tenían código de salida 1 y un resumen incompleto, por lo que se ejecutaron de nuevo con registros completos. [Recorridos de navegador](../cut/cutless/tests/browser/)

### Problemas confirmados

- **Django, NUM-01.** `test_edicion_ajena_no_cambia_datos` espera la redirección `302` anterior a SEC-08. La vista ahora limita la búsqueda al material propio o compartido. El POST sobre un material personal ajeno devuelve `404` y la prueba específica de SEC-08 exige ese estado. Al corregir la expectativa de NUM-01, el caso confirma `404` y conserva el precio `20.00` en ambos motores. [Prueba NUM-01](../cut/cutless/tests/test_num01_validacion.py) · [Contrato de SEC-08](../cut/cutless/tests/test_permisos_catalogo.py)
- **Chromium, Contacto.** La coincidencia parcial de `País o territorio` localiza el campo de teléfono y el de dirección. Con coincidencia exacta en las dos llamadas, aprobaron alta y edición entre 320 y 1440 px en ambos temas, búsqueda, teclado, revalidación y el flujo sin JavaScript. Se comprobó el flujo sobre la misma aplicación. [Guion de Contacto](../cut/cutless/tests/browser/contacto-clientes.cjs)
- **Chromium, NUM-01.** El guion espera `12.50` y `0.50` al volver a editar, aunque VIS-05 muestra `12.5` y `0.5`. Ajustar las dos expectativas conserva las comprobaciones del literal tecleado, de errores, de reapertura y de preselección. Las pruebas Django también verifican la precisión almacenada. [Guion NUM-01](../cut/cutless/tests/browser/num01-validacion.cjs) · [PR #33](https://github.com/gy0kuroo/optimizador_materiales/pull/33)
- **Aplicación, historial del cliente.** En la tabla Proyectos, «Ver resultado» usa `href="#"`. Se confirmó en la respuesta HTTP 200 de un cliente con proyecto y optimización sintéticos. El enlace ya existía en `b506e990`, antes del PR #19, y sigue pendiente de destino funcional. [Plantilla](../cut/cutless/templates/cutless/historial_cliente.html) · [Hallazgo histórico](CAMBIOS_TABLAS_RESPONSIVE_MOVIL.md#hallazgo-funcional-preexistente)

Las tres correcciones de prueba quedaron en la rama local `test/ver01-regresiones`, commit `e481cca5c3ef1370f321aaae8c8307a1803ca4a9`. La rama publicada contiene los dos documentos.

| Módulo | Evidencia revisada |
| --- | --- |
| Materiales personales y compartidos, Django Admin | Suite de catálogos, altas, cambios y borrado individual o por lote. La matriz de roles cubre propietario, personal sin gestión del catálogo, personal delegado y superusuario. |
| Optimización y costos | Alta, edición, asociación de material, parámetros y resultados persistidos. Se revisaron los importes de catálogo, el cero explícito y la mano de obra vacía. |
| Presupuestos | Creación y edición con día civil de Chile, conservación exacta de fechas vencidas en borradores y preservación de emitidos y PDF históricos. |
| Proyectos y clientes | Permisos, rutas, estado de proyectos, direcciones, conservación de texto legado y contacto. |
| Formatos decimales | Materiales, importes de Optimización, Presupuestos y formularios de administración. Casos de fracciones, cero, vacío, coma y punto, y conservación de lo escrito ante un error. |
| Exportaciones e Historial | PDF, Excel y PNG, archivos históricos, autorización, botones de Estadísticas e Historial, loader y flujo nativo emulado. |
| Rutas críticas y acceso | Pruebas Django de vistas protegidas, permisos entre propietarios, autenticación, recuperación con dobles locales y navegación principal. |

## Migraciones

- **APROBADO** · Las dos bases locales aplicaron el esquema en limpio y pasaron la prueba de regresión de correlativos desde `cutless/0006` con datos sintéticos. Esa regresión comprueba numeración, relaciones, datos históricos y el informe de correspondencia.
- **APROBADO** · Se preparó una base sintética por motor en `cutless/0008` con un cliente y una dirección histórica. El único plan de actualización fue `0009_cliente_direcciones_estructuradas` seguido de `0010_cliente_codigo_postal`. Se conservaron la identidad, el propietario y la dirección. Los campos estructurados comprobados quedaron nulos. `MigrationLoader.check_consistent_history()`, `migrate --check` y `makemigrations --check --dry-run` pasaron en ambos motores.
- **PENDIENTE DE VERIFICACIÓN** · Confirmar desde el registro del despliegue y el historial autorizado de migraciones que el esquema operativo llega a `cutless/0010_cliente_codigo_postal` y `usuarios/0003_perfilusuario_preferencias_menu`. Revisar en particular `cutless/0005` para datos de presupuestos emitidos, `0007` y `0008` para el backfill y las restricciones de correlativos, y `0009` y `0010` para las columnas de dirección. Si falta alguna versión, registrar el desfase y gestionar una ventana separada con respaldo y reversión. [Guía de correlativos](MIGRACION_CORRELATIVOS_OPTIMIZACIONES.md) · [Direcciones simplificadas](CLI_02_DIRECCIONES_SIMPLIFICADAS_CLIENTES.md)

## Seguridad y dependencias

- **APROBADO** · SEC-08 conserva en ambos motores los límites de acceso normal al catálogo en CutLess y Django Admin. Ocho casos por motor cubren la separación entre materiales personales y compartidos, la propiedad histórica, los roles, los lotes mixtos y la protección de referencias existentes. [Pruebas de SEC-08](../cut/cutless/tests/test_permisos_catalogo.py)
- **PENDIENTE DE VERIFICACIÓN** · La protección frente al borrado vive en las vías auditadas. Una asociación nueva concurrente con el borrado, las cascadas al eliminar cuentas y las escrituras por otras vías siguen fuera de la garantía documentada. Su alcance requiere una revisión de política y de integridad. [Límites de SEC-08](SEC_08_PERMISOS_MATERIALES_COMPARTIDOS.md)
- **PENDIENTE DE VERIFICACIÓN** · SEC-07 sigue abierto para la configuración efectiva de TLS, proxy, cookies, cabeceras y privilegios de PostgreSQL. Los valores del entorno de prueba no prueban la configuración de un despliegue. [SEC-01 y seguimiento operativo](SEC_01_ACTUALIZACION_DJANGO.md)
- **APROBADO** · La resolución local de dependencias es compatible según `uv pip check` (27 paquetes). El código fija Django `5.2.19`, Pillow `11.0.0` y sqlparse `0.5.1`. **PENDIENTE DE VERIFICACIÓN** · Se mantiene el aplazamiento de Pillow y sqlparse. Falta evaluar los avisos y su aplicabilidad a CutLess, y luego ensayar las actualizaciones por separado. [Versiones fijadas](../cut/requirements.txt) · [Decisión de aplazamiento](DEPENDENCIAS_APLAZADAS_SQLPARSE_PILLOW.md)

## Prioridades y comprobaciones operativas

1. **Antes del ensayo** · En Render, identificar el SHA, la rama conectada y la versión de Django en el artefacto activo. Revisar el registro de arranque y el paso de migración. En Supabase, confirmar la versión de PostgreSQL y contrastar en modo de solo lectura el historial de migraciones aplicado. Si hay desfase de artefacto, error de arranque o esquema incompleto, detener el recorrido y registrar el hallazgo. Verificar que haya un respaldo recuperable y un procedimiento de reversión antes de plantear cambios de esquema.
2. **Durante el ensayo** · Usar cuentas y datos de prueba en un entorno aislado o autorizado. Comprobar sesión y cierre de sesión, accesos por rol en Materiales y Admin, creación de una optimización con costo, un borrador de presupuesto con fecha chilena, y navegación por Proyectos, Clientes, Historial y Estadísticas. Mantener las operaciones de borrado, envío de correo y escritura masiva en un entorno aislado.
3. **Durante el ensayo** · Completar la matriz UX-05 con Safari en iPhone físico y Chrome para Windows. En cada panel donde exista el formato, pulsar una vez, abrir el PDF, Excel o PNG, verificar nombre y contenido, y probar el guardado desde la vista previa en iOS. Incluir PDF nuevo y archivado, y enlaces disponibles sin JavaScript. Registrar dispositivo, versión, panel y resultado. [Matriz de descargas](UX_05_DESCARGAS_SAFARI_IOS.md)
4. **Antes de cerrar la validación operativa** · Recoger evidencia de SEC-07 sin exponer secretos ni datos de clientes: TLS, cabeceras, atributos de cookies, configuración de proxy y alcance del rol de la aplicación en PostgreSQL.
5. **Seguimiento** · Integrar por separado las correcciones de prueba para recuperar una ejecución verde sobre `main`. Definir el destino de «Ver resultado» en el historial del cliente. Revisar las dependencias aplazadas y la política de integridad fuera de los flujos normales de SEC-08.

Esta auditoría se limitó a GitHub, el repositorio y entornos locales. La ejecución no consultó Render, Supabase ni datos de producción.
