# Matriz consolidada de evidencias de pruebas — CutLess

**Fecha de consolidación:** 22 de noviembre de 2026.

**Procedencia:** archivo de `docs/matriz-evidencias-auditoria-cutless-20261122` en el fork, integrado en `main` por el [PR #18](https://github.com/gy0kuroo/optimizador_materiales/pull/18).

**Alcance:** revisión documental de ejecuciones históricas y posteriores, hasta el ajuste móvil de los botones de Comparación. Las suites citadas corresponden a sus respectivas etapas. Esta revisión no volvió a ejecutarlas ni consultó producción.

## 1. Cómo leer la evidencia

La fuente principal es la [auditoría integral de CutLess v2](AUDITORIA_INTEGRAL_CUTLESS.md), junto con los informes de las etapas posteriores. La matriz original también cita el informe histórico `CutLess_v2_Informe_Tecnico_Auditoria_Pruebas_Implementacion.docx` y una bitácora preliminar de la conversación. Las cifras que solo constan allí se conservan como transcripciones históricas. Esta revisión no cotejó los documentos originales ni sus logs o capturas.

- **A — Prueba en código:** existe un archivo de pruebas versionado que permite volver a ejecutar el caso; no confirma una ejecución reciente.
- **B — Resultado registrado:** un informe indica ejecución, entorno y resultado. Salvo si se enlaza un log conservado, no equivale a disponer del log bruto.
- **C — Evidencia operativa informada:** comprobación manual o funcionamiento comunicado por el usuario sin logs/capturas completas de infraestructura.
- **P — Pendiente:** no consta verificación suficiente para declarar que se probó.

Los recuentos **no se suman** entre versiones ni motores: varias ejecuciones repiten los mismos casos con distintos entornos o revisiones del código.

## 2. Cronología y resultados recuperados

| Etapa histórica | Ejecución y resultado informado | Soporte y alcance |
| --- | --- | --- |
| Auditoría inicial H01–H14 | Revisión estática, sin ejecución de pruebas durante esa primera etapa. | Informe histórico y [auditoría integral](AUDITORIA_INTEGRAL_CUTLESS.md); detectar un problema en el código no prueba su explotación. **B** |
| Caracterización previa a las correcciones H01–H07 | SQLite en archivo: 249 casos, 238 aprobados y 11 errores de cierre de conexión; repetición en SQLite en memoria: 249/249; 18 pruebas adicionales de usuarios aprobadas; 15/15 reproducciones temporales de H01–H07. | Bitácora previa recuperada de la conversación. Las 15 pruebas caracterizan **comportamientos defectuosos**, no su corrección. H13 se identificó por lectura de código, sin ejecutar su script en aquella etapa. No se incorporan como resultados de la versión final. **B**, logs brutos no comprobados en el repositorio. |
| Implementación integral v2: H01–H17 y segunda revisión H02 | PostgreSQL 16.2 local: 306/306; SQLite temporal: 305/306, una omitida por bloqueo de fila; JavaScript: 52/52; H02: 29 casos focalizados aprobados; smoke test: 16 páginas HTTP 200. | [Auditoría integral](AUDITORIA_INTEGRAL_CUTLESS.md), [PR #1](https://github.com/gy0kuroo/optimizador_materiales/pull/1) e informe histórico de 12 páginas. **A+B** |
| Repetición en Windows 11 de v2 | Django: 306 descubiertas, 305 aprobadas y una omitida. Node: 52 aprobadas. Las migraciones `cutless.0005` y `cutless.0006` figuraron aplicadas en SQLite local. | Salidas atribuidas al informe histórico, sin logs originales verificados en esta revisión. **B** |
| Rendimiento del optimizador v2 | Se compararon casos de 5, 50, 300, 1.000 y 2.000 piezas, además de 100 tableros; para 2.000 piezas el tiempo local cambió de 11,202 a 0,966 s y RSS máximo de 324,3 a 100,0 MiB. Cuatro cuentas simultáneas de 300 piezas respondieron HTTP 200; máximo 1,093 s y 106,1 MiB en ese ensayo. | [Auditoría integral](AUDITORIA_INTEGRAL_CUTLESS.md). Cada tamaño se midió una vez por versión: no es una garantía de rendimiento en Render. **B** |
| Compatibilidad y migraciones v2 | Se contrastaron 650 resultados completos del algoritmo con la base; las migraciones 0005 y 0006 fueron ensayadas en PostgreSQL local sobre una base sintética y aplicadas en SQLite local de pruebas. | [Auditoría integral](AUDITORIA_INTEGRAL_CUTLESS.md), [revisión de preparación PostgreSQL](CAMBIOS_PREPARACION_POSTGRESQL.md). **B**; ejecución de esas migraciones en Supabase no demostrada por este registro. |
| Formato visual CLP | 277 pruebas Django en PostgreSQL local y 56 de JavaScript. Para la aclaración de redondeo, 25 pruebas Django y comprobación de los cinco desgloses en Chromium con ambos temas. | [Formato CLP](ESTANDARIZACION_FORMATO_CLP.md). Las pruebas cubrieron la precisión de formularios y montos persistidos, además de los formatos existentes de PDF y Excel. **A+B** |
| Rendimiento de Estadísticas | HD bajo demanda: 28 pruebas Django en PostgreSQL local y 6 de JavaScript. Carga asíncrona de miniaturas: 284 aprobadas en SQLite y 2 omitidas, 65 de JavaScript aprobadas y recorridos locales en Chromium con reintentos y comprobación del período. | [Mediciones, alcance y resultados](OPTIMIZACION_RENDIMIENTO_ESTADISTICAS.md). Los tiempos registrados corresponden a Django, PostgreSQL y Chromium locales. **A+B** |
| Corrección SEC-01, Django 5.2.19, PR #14 | Etapa 3: 389 aprobadas en PostgreSQL local, 383 en SQLite y seis omitidas, 65 en JavaScript y 8 del Worker simulado. Etapa 4: tras añadir seis regresiones de Django, las suites repetidas dieron 395 aprobadas en PostgreSQL y 389 en SQLite, con seis omitidas. | [Informe SEC-01](SEC_01_ACTUALIZACION_DJANGO.md) · [PR #14](https://github.com/gy0kuroo/optimizador_materiales/pull/14). Las cifras de JavaScript y Worker corresponden a la etapa 3. **A+B** |
| Corrección de navegación de visores, PR #15 | Escenarios A–J con Chromium; foco/teclado, Atrás/Adelante, recarga y bfcache. PostgreSQL 395 aprobadas, SQLite 47 relacionadas, JS 65 y Worker 8 según la última revisión de esa rama. | [Informe de navegación](CAMBIOS_NAVEGACION_VISORES.md), [prueba de navegador](../cut/cutless/tests/browser/navegacion-visores.cjs), [PR #15](https://github.com/gy0kuroo/optimizador_materiales/pull/15). Las ejecuciones de bases de datos se registraron antes de la repetición final en Chromium. **A+B** |
| Tablas adaptadas a móvil, PR #19 | Chromium: 170 verificaciones móviles y 204 comparaciones en tablet y escritorio, en ambos temas. Pasaron los flujos de teclado y selección. Django: 395 aprobadas en PostgreSQL local y 389 en SQLite, con seis omitidas. Node: 73 aprobadas, incluidas 8 del Worker simulado. | [Revisión final de tablas](CAMBIOS_TABLAS_RESPONSIVE_MOVIL.md#revisión-final) · [PR #19](https://github.com/gy0kuroo/optimizador_materiales/pull/19). La confirmación del usuario se registra por separado como evidencia operativa. **A+B** |
| Alineación móvil de botones en Comparación | Chromium: 10 combinaciones móviles y 6 de tablet y escritorio. En móvil se verificó el foco y se abrieron los dos destinos a 320 y 390 px. Django: 12 pruebas de comparación y análisis aprobadas. | [Ajuste y resultados locales](CAMBIOS_COMPARACION_ALTERNATIVAS.md#alineación-móvil-de-los-enlaces-de-resultado) · [Commit `d40edf7`](https://github.com/JJBossa/optimizador_materiales/commit/d40edf7bfd4ed9383264c6b1f1658a1d6bfbf1cd). **B** |

### Incidencias de ejecución que no se deben ocultar

- **Cierres de conexión:** la bitácora histórica informó 11 errores durante la caracterización con SQLite en archivo. Por separado, el informe versionado documentó 11 errores de PostgreSQL reproducibles en la base anterior a la corrección. En ese segundo caso se ajustó el consumo de las respuestas de descarga de las pruebas. [Informe versionado](AUDITORIA_INTEGRAL_CUTLESS.md#c-resultados-de-pruebas)
- **Pruebas de caracterización:** aprobar la comprobación de un defecto demuestra que se reprodujo correctamente, no que el defecto ya estaba solucionado.
- **Omisiones en SQLite:** las pruebas de bloqueo de filas con `select_for_update` se ejecutaron en PostgreSQL. La omisión de v2 y las seis de SEC-01 pertenecen a versiones diferentes de la suite.
- **Rendimiento:** los porcentajes y tiempos corresponden al ambiente local y condiciones descritas, no a la carga sostenida del servicio publicado.

## 3. Matriz de funcionalidades, seguridad y demostración

### Trazabilidad de H01–H17

La [auditoría integral](AUDITORIA_INTEGRAL_CUTLESS.md#b-registro-de-hallazgos) documenta qué se verificó para cada hallazgo y en qué entorno. Estos enlaces apuntan a pruebas versionadas. Los casos resumidos en la cronología corresponden a aquella ejecución local.

| Hallazgo | Verificación registrada | Pruebas relacionadas |
| --- | --- | --- |
| H01 | Jerarquía de administración y validación de contraseñas. | [Seguridad de usuarios](../cut/usuarios/test_seguridad_auditoria.py) |
| H02 | Lectura de piezas históricas, conservación de datos ambiguos y operaciones de edición y exportación. | [Piezas](../cut/cutless/tests/test_pieces.py) · [Resultado y recarga](../cut/cutless/tests/test_resultado_recarga.py) |
| H03 | Borradores que reflejan cambios de planes e instantáneas de presupuestos emitidos. | [Presupuestos](../cut/cutless/tests/test_presupuestos.py) |
| H04 | Permisos de costos y relaciones al crear y editar optimizaciones. | [Resultado y recarga](../cut/cutless/tests/test_resultado_recarga.py) |
| H05 | Recuperación local para correos compartidos, ausentes o inactivos y rechazo de enlaces inválidos, vencidos o usados. | [Seguridad de usuarios](../cut/usuarios/test_seguridad_auditoria.py) |
| H06 | Cambios de estado por POST, CSRF y destinos permitidos en favoritos. | [Seguridad de usuarios](../cut/usuarios/test_seguridad_auditoria.py) · [Historial](../cut/cutless/tests/test_history_horizontal.py) |
| H07 | Exportación XLSX de texto de usuario y comprobación del tipo de celda. | [Exportaciones](../cut/cutless/tests/test_exportaciones_auditoria.py) |
| H08 | Área, giro, reserva de sierra y ausencia de solapamiento. | [Presentación del tablero](../cut/cutless/tests/test_board_presentation.py) |
| H09 | Validación de parámetros y cálculo de tiempos con tableros guardados o estimados. | [Cálculo de tiempos](../cut/cutless/tests/test_tiempo_auditoria.py) |
| H10 | Numeración de presupuestos, límites de sufijo y altas concurrentes en PostgreSQL. | [Presupuestos](../cut/cutless/tests/test_presupuestos.py) |
| H11 | Paginación, encabezados y total de presupuestos PDF extensos. | [Exportaciones](../cut/cutless/tests/test_exportaciones_auditoria.py) |
| H12 | Conservación del resultado del optimizador y casos de rotación y piezas imposibles. | [Precisión](../cut/cutless/tests/test_precision_rnf09.py) |
| H13 | Aislamiento del comprobador de pantallas y detección de fallos HTTP. | [Comprobador de auditoría](../cut/cutless/tests/test_smoke_auditoria.py) |
| H14 | Validación, persistencia y conversión de unidades, incluidos milímetros. | [Precisión](../cut/cutless/tests/test_precision_rnf09.py) |
| H15 | Continuación con Enter y omisión explícita del asistente inicial. | [Asistente en Node](../cut/usuarios/tests_js/configuracion-inicial.test.cjs) |
| H16 | Omisión según el perfil y conservación de las preferencias. | [Inicio y perfil](../cut/usuarios/test_inicio.py) |
| H17 | Recuperación del borrador del asistente tras un fallo y retiro tras confirmación. | [Inicio y perfil](../cut/usuarios/test_inicio.py) · [Asistente en Node](../cut/usuarios/tests_js/configuracion-inicial.test.cjs) |

### Controles transversales y evidencia posterior

| ID | Control / funcionalidad | Qué se probó o inspeccionó | Evidencia reproducible o informe | Límite para la evaluación |
| --- | --- | --- | --- | --- |
| QA-01 | Inicio de sesión, sesión y roles | Autenticación, vencimiento, logout, protección administrativa y rechazo de usuarios sin autorización. | [Pruebas de usuarios](../cut/usuarios/tests.py), [seguridad](CAMBIOS_SEGURIDAD.md), [SEC-01](SEC_01_ACTUALIZACION_DJANGO.md). **A+B** | La configuración y los logs de producción necesitan evidencia propia. |
| QA-02 | Aislamiento de datos | La etapa 3 de SEC-01 repitió 227 solicitudes y 198 comprobaciones de conservación de datos por motor, con cuentas sintéticas. | [Pruebas de permisos](../cut/cutless/tests/test_permissions.py) · [Validación SEC-01](SEC_01_ACTUALIZACION_DJANGO.md#validación-y-comparación). **A+B** | Cobertura de la matriz local registrada. Queda pendiente revisar las rutas y permisos efectivos de producción. |
| QA-03 | Protección CSRF y métodos seguros | Solicitudes POST con CSRF incorrecto, GET sin modificación de estado y restricciones de redirecciones. | [Pruebas de recuperación y CSRF](../cut/usuarios/test_csrf_recovery.py), [seguridad](CAMBIOS_SEGURIDAD.md), [auditoría v2](AUDITORIA_INTEGRAL_CUTLESS.md). **A+B** | No acredita el comportamiento real del proxy de Render. |
| QA-04 | Recuperación de contraseña | Tokens usados, vencidos, cuentas duplicadas/inactivas y flujos de Brevo/cola con pruebas locales y simuladas según informe. | [Guía de recuperación](RECUPERACION_PASSWORD_BREVO.md), [pruebas Brevo](../cut/usuarios/test_recuperacion_brevo.py). **A+B** | La activación pública y configuración efectiva de envío en Render no fueron demostradas. |
| QA-05 | Integridad de piezas | Casos de lectura y conservación de H02. | [Trazabilidad de H01–H17](#trazabilidad-de-h01h17). **A+B** | Una eventual reversión debe conservar la lectura del JSON versionado. |
| QA-06 | Seguridad de Excel | Verificación de tipo de celda de H07 con OpenPyXL. | [Trazabilidad de H01–H17](#trazabilidad-de-h01h17). **A+B** | La prueba comprueba el tipo de dato del XLSX generado localmente. |
| QA-07 | Algoritmo de optimización | Comparación con la base y pruebas de margen y rotación de H08 y H12. | [Auditoría v2](AUDITORIA_INTEGRAL_CUTLESS.md) · [Empaquetamiento](../cut/cutless/tests/test_packing.py). **A+B** | Ensayos locales con los datos descritos en el informe. |
| QA-08 | Presupuestos, correlativos y PDF | Ver las comprobaciones H03, H10 y H11. La migración de correlativos se ensayó por separado. | [Migración de correlativos](MIGRACION_CORRELATIVOS_OPTIMIZACIONES.md) · [Trazabilidad de H01–H17](#trazabilidad-de-h01h17). **A+B** | Las comprobaciones locales del esquema tienen su propio entorno de prueba. |
| QA-09 | Archivos privados | Pruebas locales de acceso autenticado y por propietario y confinamiento de rutas a `MEDIA_ROOT`. | [Pruebas de medios privados](../cut/cutless/tests/test_media_privada.py) · [Guía de producción](PREPARACION_RENDER_SUPABASE.md). **A+B** | Pendiente comprobar la configuración de almacenamiento del servicio desplegado. |
| QA-10 | Navegación y accesibilidad | Modal de Estadísticas/Historial, Atrás, Adelante, foco y uso de teclado en Chromium. | [Informe de navegación](CAMBIOS_NAVEGACION_VISORES.md), [prueba de Chromium](../cut/cutless/tests/browser/navegacion-visores.cjs). **A+B** | La última campaña automatizada de esa funcionalidad se realizó en Chromium; otros navegadores no quedaron cubiertos en ese informe. |
| QA-11 | Indicadores en Presupuestos | El usuario ejecutó Django local con SQLite en Windows 11, contra Findic.cl por HTTPS. La primera consulta obtuvo dólar y UF y la segunda reutilizó la caché. | [Prueba real de Findic.cl](INTEGRACION_API_INDICADORES.md). **B+C** | La comprobación fue desde el equipo de prueba. Queda fuera el servicio alojado. |
| QA-12 | Rendimiento | Varios tamaños de piezas, consumo máximo RSS y simultaneidad local de cuatro cuentas. | [Auditoría v2](AUDITORIA_INTEGRAL_CUTLESS.md), [prueba RNF-03](rendimiento/RNF-03_2026-10-25/INFORME.md). **B** | Mediciones históricas bajo condiciones diferentes; no combinar series ni convertirlas en SLA de Render. |
| QA-13 | Contraseña y protección de dependencias | Validadores de contraseñas, actualización Django a 5.2.19 y decisiones sobre sqlparse/Pillow. | [SEC-01](SEC_01_ACTUALIZACION_DJANGO.md), [dependencias aplazadas](DEPENDENCIAS_APLAZADAS_SQLPARSE_PILLOW.md). **A+B** | `sqlparse==0.5.1` y `Pillow==11.0.0` siguen pendientes de evaluación/actualización, por decisión documentada. |

### Confirmaciones operativas informadas

| Comprobación | Alcance de la confirmación | Fuente |
| --- | --- | --- |
| Tablas móviles del PR #19 | El usuario confirmó el funcionamiento. El estado del despliegue y el commit activo en Render quedaron sin comprobar. | [Registro del PR #19](REGISTRO_CAMBIOS_NOVIEMBRE_2026.md#cambios-registrados). **C** |
| Conexión a PostgreSQL de Supabase | Prueba histórica desde Django local contra una base limpia. El usuario confirmó migraciones iniciales, autenticación, guardado, recuperación de historial y descargas. | [Preparación PostgreSQL](CAMBIOS_PREPARACION_POSTGRESQL.md#validaciones-y-límites). **B+C** |
| Recuperación por correo | Prueba real con Brevo desde Windows y ensayo temporal del Worker en Cloudflare, informados por el equipo. La recuperación pública quedó desactivada según ese registro. | [Evidencia operativa](REGISTRO_CAMBIOS_NOVIEMBRE_2026.md#evidencia-operativa) · [Guía de recuperación](RECUPERACION_PASSWORD_BREVO.md). **B+C** |

## 4. Evidencias históricas con disponibilidad parcial

La matriz original atribuye las siguientes referencias al informe histórico de 12 páginas. La última columna indica si se dispuso del material en la revisión documental.

| Identificador | Fuente histórica | Qué acredita según el informe | Disponibilidad comprobada en esta revisión |
| --- | --- | --- | --- |
| EV-01 | `CutLess-revision-tecnica-v2.zip` | Paquete con 64 archivos y reportes. | Archivo identificado en informe histórico; no recuperado ni publicado aquí. |
| EV-02 | `SHA256SUMS.txt` | Huellas del ZIP y el parche. | Huellas transcritas en el informe; archivo bruto no comprobado aquí. |
| EV-03 | `docs/AUDITORIA_INTEGRAL_CUTLESS.md` | Hallazgos, correcciones, pruebas y rendimiento. | **Sí, disponible en GitHub.** |
| EV-04 | `REVISION-TECNICA.md` | Revisión de migraciones, compatibilidad y reversión. | Identificado en paquete histórico, no comprobado en la rama principal. |
| EV-05 | `pruebas-pg.txt`, `pruebas-sqlite.txt`, `pruebas-node.txt` | Logs originales de las suites del entorno aislado. | Identificados en paquete histórico; no comprobados como archivos rastreados en `main`. |
| EV-06 | Salidas de consola de Windows | Ejecuciones Django/Node y migraciones. | Resultados **transcritos** en el informe histórico; logs brutos no comprobados en GitHub. |
| EV-07 | [PR #1](https://github.com/gy0kuroo/optimizador_materiales/pull/1) y commits | Integración y trazabilidad del cambio. | **Sí, disponible en GitHub.** |
| EV-08 | Capturas de plano y tutorial móvil | Comportamiento visual de piezas y hallazgo UX. | Figuras incluidas en el informe histórico; no se comprobó su presencia como archivos de evidencia separados en `main`. |

**Huellas anotadas en el informe histórico** (no verificadas nuevamente contra archivos originales en esta etapa):

- `CutLess-revision-tecnica-v2.zip`: `2d84438285e4742e55393bf420fde222830c96aa9c8f60bbc627b9b98086c26f`.
- `cutless-completo.patch`: `8c7eeb64caddc69a5a0e92ec2f17d0ade122b49383147ac6290e90de99f81b5f`.

## 5. Pendientes de verificación

1. **SEC-07:** inspección de la configuración efectiva de seguridad de Render y Supabase (proxy, TLS, cabeceras, cookies, privilegios PostgreSQL, roles y permisos) sin divulgar secretos.
2. **Evidencia operativa reciente:** logs del despliegue, commit activo y estado de los servicios de producción. La confirmación de funcionamiento del PR #19 queda registrada por separado.
3. **Esquema administrado:** comprobar el estado de las migraciones posteriores y los respaldos del entorno objetivo. La prueba histórica contra una base limpia no acredita el esquema actual de Supabase.
4. **Cobertura de autorización:** extender la matriz local de SEC-01 a operaciones que queden fuera de los casos registrados y verificar por separado los permisos efectivos de producción.
5. **Seguridad pendiente:** evaluar los avisos de `sqlparse` y `Pillow` según la [decisión de mantenimiento](DEPENDENCIAS_APLAZADAS_SQLPARSE_PILLOW.md). La [guía de recuperación](RECUPERACION_PASSWORD_BREVO.md) conserva el riesgo de enumeración por tiempos y las verificaciones previas a la activación pública.
6. **Evidencia adjunta:** si se conservan el ZIP histórico, `SHA256SUMS`, logs de PostgreSQL/SQLite/Node y capturas, cotejar su integridad y adjuntar copias saneadas **solo con autorización**, sin credenciales, claves, tokens, correos reales ni datos de usuarios.
7. **Ejecución para la evaluación:** una nueva corrida reproducible de pruebas, capturas fechadas y demostración controlada de login, acceso ajeno rechazado, CSRF, generación de plan, persistencia y exportación, indicando entorno y commit.

## 6. Referencias y criterio de cierre

- [Auditoría integral v2](AUDITORIA_INTEGRAL_CUTLESS.md), [seguridad inicial](CAMBIOS_SEGURIDAD.md) y [SEC-01](SEC_01_ACTUALIZACION_DJANGO.md).
- [Navegación de visores](CAMBIOS_NAVEGACION_VISORES.md), [preparación PostgreSQL](CAMBIOS_PREPARACION_POSTGRESQL.md) y [registro de cambios de noviembre](REGISTRO_CAMBIOS_NOVIEMBRE_2026.md).
- [Tablas móviles](CAMBIOS_TABLAS_RESPONSIVE_MOVIL.md) y [alineación de los botones de Comparación](CAMBIOS_COMPARACION_ALTERNATIVAS.md#alineación-móvil-de-los-enlaces-de-resultado).

**Conclusión:** hay pruebas automatizadas e informes sustanciales, pero la trazabilidad de logs originales, capturas de algunas ejecuciones y validación operativa real todavía no es completa. Este documento no pretende certificar ausencia de vulnerabilidades ni reemplazar un reporte de pruebas sobre producción.
