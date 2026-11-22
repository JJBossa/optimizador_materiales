# Matriz consolidada de evidencias de pruebas — CutLess

**Fecha de consolidación:** 22 de noviembre de 2026.  
**Referencia inicial:** `gy0kuroo/optimizador_materiales:main` en `589aebd674aca29e2e4dfcaed02e81abd9889e56` (PR #17 fusionado).  
**Alcance:** organización documental de ejecuciones históricas y pruebas existentes. No se ejecutaron nuevamente las suites en esta consolidación; no se modifican aplicación, dependencias, migraciones, datos ni producción.

## 1. Cómo leer la evidencia

Este inventario consolida el informe local **`CutLess_v2_Informe_Tecnico_Auditoria_Pruebas_Implementacion.docx`** (12 páginas, preparado en noviembre de 2026 a partir de la conversación de auditoría), la revisión preliminar conservada en la conversación y los informes/archivos presentes en GitHub. El documento Word histórico fue recuperado del archivo de la conversación, **pero no se ha comprobado que sus bytes, capturas o transcripciones de consola estén dentro de este repositorio**.

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
| Repetición independiente en Windows 11 de v2 | Django: 306 descubiertas, 305 aprobadas y una omitida; Node: 52 aprobadas. Las migraciones `cutless.0005` y `cutless.0006` figuraron aplicadas en SQLite local. | Salidas de consola transcritas en el informe histórico; no equivalen a logs originales cargados al repositorio. La salida inicial «Found 0 test(s)» se resolvió indicando las apps `cutless usuarios`. **B** |
| Rendimiento del optimizador v2 | Se compararon casos de 5, 50, 300, 1.000 y 2.000 piezas, además de 100 tableros; para 2.000 piezas el tiempo local cambió de 11,202 a 0,966 s y RSS máximo de 324,3 a 100,0 MiB. Cuatro cuentas simultáneas de 300 piezas respondieron HTTP 200; máximo 1,093 s y 106,1 MiB en ese ensayo. | [Auditoría integral](AUDITORIA_INTEGRAL_CUTLESS.md). Cada tamaño se midió una vez por versión: no es una garantía de rendimiento en Render. **B** |
| Compatibilidad y migraciones v2 | Se contrastaron 650 resultados completos del algoritmo con la base; las migraciones 0005 y 0006 fueron ensayadas en PostgreSQL local sobre una base sintética y aplicadas en SQLite local de pruebas. | [Auditoría integral](AUDITORIA_INTEGRAL_CUTLESS.md), [revisión de preparación PostgreSQL](CAMBIOS_PREPARACION_POSTGRESQL.md). **B**; ejecución de esas migraciones en Supabase no demostrada por este registro. |
| Corrección SEC-01, Django 5.2.19 | PostgreSQL local: 395 aprobadas, ninguna omitida; SQLite: 389 aprobadas y seis omitidas; JavaScript: 65; Worker simulado: 8. Se documentaron seis nuevas pruebas de regresión de Django. | [Informe SEC-01](SEC_01_ACTUALIZACION_DJANGO.md), [PR #14](https://github.com/gy0kuroo/optimizador_materiales/pull/14). Cifras correspondientes a una ejecución posterior, no a v2 original. **A+B** |
| Corrección de navegación de visores, PR #15 | Escenarios A–J con Chromium; foco/teclado, Atrás/Adelante, recarga y bfcache. PostgreSQL 395 aprobadas, SQLite 47 relacionadas, JS 65 y Worker 8 según la última revisión de esa rama. | [Informe de navegación](CAMBIOS_NAVEGACION_VISORES.md), [prueba de navegador](../cut/cutless/tests/browser/navegacion-visores.cjs), [PR #15](https://github.com/gy0kuroo/optimizador_materiales/pull/15). Las ejecuciones de bases de datos se registraron antes de la repetición final en Chromium. **A+B** |

### Incidencias de ejecución que no se deben ocultar

- **SQLite inicial:** los 11 errores «Cannot operate on a closed database» surgieron al cerrar respuestas de descarga dentro de transacciones de pruebas. No representan 11 defectos de negocio corregidos; la caracterización inicial se completó con SQLite en memoria y, en la revisión posterior, se ajustó el consumo de respuestas para preservar las pruebas.
- **Pruebas de caracterización:** aprobar la comprobación de un defecto demuestra que se reprodujo correctamente, no que el defecto ya estaba solucionado.
- **Omision(es) SQLite:** las pruebas de bloqueo de filas con `select_for_update` requieren PostgreSQL. Las cifras 1 omitida en v2 y 6 omitidas en SEC-01 pertenecen a versiones diferentes de la suite.
- **Rendimiento:** los porcentajes y tiempos corresponden al ambiente local y condiciones descritas, no a la carga sostenida del servicio publicado.

## 3. Matriz de funcionalidades, seguridad y demostración

| ID | Control / funcionalidad | Qué se probó o inspeccionó | Evidencia reproducible o informe | Límite para la evaluación |
| --- | --- | --- | --- | --- |
| QA-01 | Inicio de sesión, sesión y roles | Autenticación, vencimiento, logout, protección administrativa y rechazo de usuarios sin autorización. | [Pruebas de usuarios](../cut/usuarios/tests.py), [seguridad](CAMBIOS_SEGURIDAD.md), [SEC-01](SEC_01_ACTUALIZACION_DJANGO.md). **A+B** | La configuración y los logs de producción necesitan evidencia propia. |
| QA-02 | Aislamiento de datos | Intentos de consultar o modificar recursos de otros propietarios y permisos de materiales compartidos. | [Pruebas de permisos](../cut/cutless/tests/test_permissions.py), [auditoría v2](AUDITORIA_INTEGRAL_CUTLESS.md). **A+B** | Una revisión inicial de seguridad identificó operaciones de clientes, proyectos y presupuestos que merecían ampliar su matriz. No afirmar una auditoría exhaustiva de todas las rutas. |
| QA-03 | Protección CSRF y métodos seguros | Solicitudes POST con CSRF incorrecto, GET sin modificación de estado y restricciones de redirecciones. | [Pruebas de recuperación y CSRF](../cut/usuarios/test_csrf_recovery.py), [seguridad](CAMBIOS_SEGURIDAD.md), [auditoría v2](AUDITORIA_INTEGRAL_CUTLESS.md). **A+B** | No acredita el comportamiento real del proxy de Render. |
| QA-04 | Recuperación de contraseña | Tokens usados, vencidos, cuentas duplicadas/inactivas y flujos de Brevo/cola con pruebas locales y simuladas según informe. | [Guía de recuperación](RECUPERACION_PASSWORD_BREVO.md), [pruebas Brevo](../cut/usuarios/test_recuperacion_brevo.py). **A+B** | La activación pública y configuración efectiva de envío en Render no fueron demostradas. |
| QA-05 | Integridad de piezas (H02) | Comas, Unicode, prefijo literal `piezas:v1:`, creación, edición, duplicación, plantillas y exportaciones; bloqueo de ambiguos. | [Pruebas de piezas](../cut/cutless/tests/test_pieces.py), [auditoría v2](AUDITORIA_INTEGRAL_CUTLESS.md). **A+B** | Evitar una reversión de código que no lea el JSON versionado. |
| QA-06 | Seguridad de Excel (H07) | Celdas de texto del usuario no se interpretan como fórmulas; revisión de exportaciones. | [Auditoría v2](AUDITORIA_INTEGRAL_CUTLESS.md), [pruebas de exportaciones](../cut/cutless/tests/test_exportaciones_auditoria.py). **A+B** | Evitar presentar la observación como ejecución real de una fórmula maliciosa. |
| QA-07 | Algoritmo de optimización | Conservación del resultado frente a la base en 650 comparaciones y casos de margen/rotación. | [Auditoría v2](AUDITORIA_INTEGRAL_CUTLESS.md), [pruebas de empaquetamiento](../cut/cutless/tests/test_packing.py). **A+B** | Ensayos deterministas y locales; no son una prueba de carga pública. |
| QA-08 | Presupuestos, correlativos y PDF | Instantánea de cotización emitida, numeración concurrente y paginación de PDF extenso. | [Auditoría v2](AUDITORIA_INTEGRAL_CUTLESS.md), [migración correlativos](MIGRACION_CORRELATIVOS_OPTIMIZACIONES.md). **A+B** | Las comprobaciones de migración local no sustituyen la verificación del esquema de Supabase. |
| QA-09 | Archivos privados | Acceso según autenticación/propietario, rutas confinadas a `MEDIA_ROOT` y no exposición de archivos ajenos. | [Pruebas de medios privados](../cut/cutless/tests/test_media_privada.py), [producción](PREPARACION_RENDER_SUPABASE.md). **A+B** | Verificar el servicio web y su configuración real de archivos en producción. |
| QA-10 | Navegación y accesibilidad | Modal de Estadísticas/Historial, Atrás, Adelante, foco y uso de teclado en Chromium. | [Informe de navegación](CAMBIOS_NAVEGACION_VISORES.md), [prueba de Chromium](../cut/cutless/tests/browser/navegacion-visores.cjs). **A+B** | La última campaña automatizada de esa funcionalidad se realizó en Chromium; otros navegadores no quedaron cubiertos en ese informe. |
| QA-11 | Calidad de API y base remota | Conexión real local a Supabase PostgreSQL, autenticación, persistencia de optimización/historial y descargas según prueba manual histórica. | [Preparación PostgreSQL](CAMBIOS_PREPARACION_POSTGRESQL.md), [guía Render/Supabase](PREPARACION_RENDER_SUPABASE.md). **B+C** | Esa prueba no acredita por sí sola la configuración ni el despliegue del servicio remoto actual. |
| QA-12 | Rendimiento | Varios tamaños de piezas, consumo máximo RSS y simultaneidad local de cuatro cuentas. | [Auditoría v2](AUDITORIA_INTEGRAL_CUTLESS.md), [prueba RNF-03](rendimiento/RNF-03_2026-10-25/INFORME.md). **B** | Mediciones históricas bajo condiciones diferentes; no combinar series ni convertirlas en SLA de Render. |
| QA-13 | Contraseña y protección de dependencias | Validadores de contraseñas, actualización Django a 5.2.19 y decisiones sobre sqlparse/Pillow. | [SEC-01](SEC_01_ACTUALIZACION_DJANGO.md), [dependencias aplazadas](DEPENDENCIAS_APLAZADAS_SQLPARSE_PILLOW.md). **A+B** | `sqlparse==0.5.1` y `Pillow==11.0.0` siguen pendientes de evaluación/actualización, por decisión documentada. |

## 4. Evidencias históricas fuera de la trazabilidad comprobada de GitHub

El informe de 12 páginas recuperado de la conversación anterior enumera las siguientes fuentes. **Su mención es un inventario, no una afirmación de que se encuentren actualmente adjuntas al repositorio:**

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

## 5. Pendientes reales que no deben figurar como «aprobados»

1. **SEC-07:** inspección de la configuración efectiva de seguridad de Render y Supabase (proxy, TLS, cabeceras, cookies, privilegios PostgreSQL, roles y permisos) sin divulgar secretos.
2. **Prueba operativa reciente:** logs del despliegue, commit activo y estado efectivo de servicios, obtenidos de quien administra Render; la confirmación de que la aplicación funciona es evidencia operativa comunicada, no un log técnico.
3. **Migraciones sobre la instancia administrada:** respaldo y salida de estado de migraciones de Supabase que permitan verificar el esquema realmente instalado.
4. **Prueba de acceso transversal completa:** ampliar y repetir la matriz de propietarios, permisos y operaciones de clientes, proyectos y presupuestos; incluir lectura y escritura.
5. **Seguridad pendiente:** evaluar exposición de `sqlparse` y `Pillow` sin cambiar versiones por ahora; revisar controles frente a intentos repetidos de acceso, fugas de errores y demás hallazgos no cerrados de la auditoría de seguridad.
6. **Evidencia adjunta:** si se conservan el ZIP histórico, `SHA256SUMS`, logs de PostgreSQL/SQLite/Node y capturas, cotejar su integridad y adjuntar copias saneadas **solo con autorización**, sin credenciales, claves, tokens, correos reales ni datos de usuarios.
7. **Ejecución para la evaluación:** una nueva corrida reproducible de pruebas, capturas fechadas y demostración controlada de login, acceso ajeno rechazado, CSRF, generación de plan, persistencia y exportación, indicando entorno y commit.

## 6. Referencias y criterio de cierre

- [Auditoría integral v2](AUDITORIA_INTEGRAL_CUTLESS.md), [seguridad inicial](CAMBIOS_SEGURIDAD.md) y [SEC-01](SEC_01_ACTUALIZACION_DJANGO.md).
- [Navegación de visores](CAMBIOS_NAVEGACION_VISORES.md), [preparación PostgreSQL](CAMBIOS_PREPARACION_POSTGRESQL.md) y [registro de cambios de noviembre](REGISTRO_CAMBIOS_NOVIEMBRE_2026.md).
- Informe de trabajo histórico de 12 páginas: `CutLess_v2_Informe_Tecnico_Auditoria_Pruebas_Implementacion.docx`, elaborado con evidencia y capturas de la conversación «Auditar CutLess paso a paso». El informe original se conserva como material histórico aparte; **no se incluye automáticamente en este PR**.

**Conclusión:** hay pruebas automatizadas e informes sustanciales, pero la trazabilidad de logs originales, capturas de algunas ejecuciones y validación operativa real todavía no es completa. Este documento no pretende certificar ausencia de vulnerabilidades ni reemplazar un reporte de pruebas sobre producción.
