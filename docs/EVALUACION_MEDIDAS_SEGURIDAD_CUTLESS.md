# Medidas de seguridad implementadas en CutLess — evidencia para evaluación

**Corte documental:** 24 de noviembre de 2026. **Base revisada:** `gy0kuroo/optimizador_materiales:main`, commit `dc86f008c6489bc4912c440e06331b287e1c5483` (PR #39 VIS-07).  
**Alcance:** describe controles presentes en el código y sus pruebas documentadas. No constituye auditoría de penetración, certificación OWASP ni comprobación directa de Render/Supabase. No se ejecutaron pruebas nuevas para preparar este texto.

## 1. Arquitectura y tratamiento de datos

CutLess es una aplicación web Django que utiliza PostgreSQL mediante Supabase como base de datos remota del proyecto, y Render como plataforma del servidor, según la implementación y el funcionamiento informado. En desarrollo y pruebas aisladas también se utiliza SQLite. La conexión remota, las migraciones y la persistencia se describen en [Preparación PostgreSQL](CAMBIOS_PREPARACION_POSTGRESQL.md) y [Render/Supabase](PREPARACION_RENDER_SUPABASE.md).

La base conserva cuentas, optimizaciones, materiales, proyectos, clientes, presupuestos y sus relaciones. Los datos se comprueban en el servidor; no basta con ocultar botones en el navegador para autorizar una operación. Las exportaciones PDF, PNG y XLSX se generan bajo demanda cuando corresponde. Los documentos históricos almacenados siguen requiriendo controles de acceso.

> **Diferencia importante:** que el sistema esté implementado para Render/Supabase y que el usuario informe que funciona no equivale a haber inspeccionado la configuración activa, las cabeceras HTTPS, el esquema remoto ni los permisos de la base en producción.

## 2. Matriz de controles implementados

| Medida | Implementación observada/documentada | Cómo fue comprobada | Estado y límite |
| --- | --- | --- | --- |
| **Autenticación** | Inicio y cierre de sesión con Django; las vistas privadas exigen usuario autenticado. Las contraseñas se procesan con los mecanismos de hash y validadores del framework. | Pruebas de usuarios y auditoría de [H01 y H06](AUDITORIA_INTEGRAL_CUTLESS.md), [seguridad inicial](CAMBIOS_SEGURIDAD.md). | **Implementado y probado localmente**; no se realizó aquí una prueba de ataque sobre producción. |
| **Roles y autorización** | Se distingue entre usuario, administrador delegado y superusuario. Un administrador corriente no puede gestionar privilegios reservados al superusuario. | H01: respuestas HTTP 403 y preservación de los datos de cuentas; pruebas Django registradas. [Auditoría](AUDITORIA_INTEGRAL_CUTLESS.md). | **Implementado con pruebas de regresión**. El alcance depende de cada ruta. |
| **Aislamiento de registros** | Las operaciones sensibles consultan registros vinculados al propietario. Se impide asociar optimizaciones y recursos personales ajenos a solicitudes manipuladas. | H04 y otras pruebas de permisos; comprobaciones de recursos ajenos en el [informe de auditoría](AUDITORIA_INTEGRAL_CUTLESS.md). | **Probado en rutas cubiertas**; no afirmar que se verificaron absolutamente todas las combinaciones de objeto/rol. |
| **Materiales compartidos y Django Admin** | Las operaciones de materiales personales y predefinidos aplican permisos por objeto. El acceso a Django Admin exige además `is_staff` y permisos de modelo. Solo el superusuario modifica clasificación/propietario de un material en Admin. | SEC-08: 63 pruebas dirigidas por motor (SQLite y PostgreSQL locales) y escenarios por rol, incluidos borrados individuales y masivos. [SEC-08](SEC_08_PERMISOS_MATERIALES_COMPARTIDOS.md), [pruebas](../cut/cutless/tests/test_permisos_catalogo.py). | **Probado localmente**. Las cascadas externas y la concurrencia entre asociación/borrado quedan fuera del alcance documentado. |
| **Protección CSRF** | Middleware CSRF de Django para formularios y acciones de modificación. Las operaciones de cambio de estado requieren POST en las rutas corregidas. | H06: GET sin cambios y POST con token incorrecto rechazado; [auditoría](AUDITORIA_INTEGRAL_CUTLESS.md), [pruebas de recuperación/CSRF](../cut/usuarios/test_csrf_recovery.py). | **Probado localmente**. El consumidor remoto de cola, cuando corresponde, utiliza autenticación HMAC y no el flujo de formulario CSRF. |
| **Sesiones y cookies** | Duración predeterminada documentada de 30 minutos; cookie de sesión `HttpOnly`; opciones de cookies seguras en modo producción. | [Configuración Django](../cut/cutless_project/settings.py) y [entorno](../cut/cutless_project/environment.py), revisión documental de seguridad. | **Configuración prevista por código**. Los atributos realmente emitidos, expiración y proxy de Render requieren SEC-07. |
| **HTTPS y configuración de producción** | `CUTLESS_ENV=production` desactiva `DEBUG`, exige hosts explícitos y clave de aplicación válida, habilita cookies seguras, redirección HTTPS y HSTS. | [Guía de Render/Supabase](PREPARACION_RENDER_SUPABASE.md) y configuración de [entorno](../cut/cutless_project/environment.py). | **Implementado como configuración condicional**; no se puede afirmar que esté habilitado correctamente en Render sin leer la configuración efectiva y las respuestas HTTPS. |
| **Claves y credenciales** | Claves de Django, credenciales PostgreSQL y de proveedores se suministran mediante variables privadas del entorno; no forman parte de formularios ni ejemplos con valores reales. | [Guía de Render/Supabase](PREPARACION_RENDER_SUPABASE.md), [guía de recuperación](RECUPERACION_PASSWORD_BREVO.md). | **Diseño documentado**. Falta revisar el historial de secretos, la rotación y los permisos efectivos sin revelar sus valores. |
| **Protección de archivos privados** | Las rutas de medios históricos comprueban autenticación, propiedad y pertenencia a una ruta permitida antes de servir archivos. Las descargas no se habilitan por conocer un nombre de archivo. | [Pruebas de medios privados](../cut/cutless/tests/test_media_privada.py), [guía de despliegue](PREPARACION_RENDER_SUPABASE.md). | **Probado localmente**; verificar que no exista un alias público de `MEDIA_ROOT` en el alojamiento real. |
| **Integridad y validación de entradas** | Formularios Django validan datos; la serialización de piezas usa JSON versionado y rechaza operaciones sobre registros ambiguos para evitar pérdida de datos. | H02: 29 casos focalizados; comas, Unicode, prefijos literales, duplicación, PDF y XLSX; respuesta HTTP 422 documentada. [Auditoría](AUDITORIA_INTEGRAL_CUTLESS.md). | **Probado localmente**; la reversión a código sin lector compatible representa un riesgo de integridad. |
| **Exportaciones Excel** | Los valores de texto introducidos por el usuario se escriben como texto literal para evitar que una cadena se interprete como fórmula en XLSX. | H07, comprobación de exportaciones con OpenPyXL. [Auditoría](AUDITORIA_INTEGRAL_CUTLESS.md). | **Probado localmente**; no afirmar que se ejecutó una fórmula maliciosa. |
| **Recuperación de contraseña** | Respuestas genéricas; tokens con vencimiento; integración preparada con Brevo HTTPS y, en modalidad documentada, Cloudflare Queues, autenticación HMAC y cuotas del consumidor. | Pruebas aisladas y una prueba de envío HTTPS documentadas en [Recuperación Brevo](RECUPERACION_PASSWORD_BREVO.md). | **Implementación disponible, activación pública pendiente de comprobar**. El modo directo del fork no se considera integrado; no afirmar que los correos de recuperación pública estén activos. |
| **Actualización de dependencias** | Django se actualizó de 5.2.8 a 5.2.19, dentro de la serie LTS. | [SEC-01](SEC_01_ACTUALIZACION_DJANGO.md): suites de PostgreSQL, SQLite, JavaScript y Worker, y regresiones del framework. | **Corrección integrada**. `sqlparse==0.5.1` y `Pillow==11.0.0` siguen explícitamente aplazadas; ver [decisión](DEPENDENCIAS_APLAZADAS_SQLPARSE_PILLOW.md). |

## 3. Cómo presentar las pruebas de seguridad en la evaluación

La evidencia más directa consiste en **código de prueba versionado + resultado histórico + explicación del control**. Los siguientes ejemplos permiten describir entradas, resultado esperado y motivo del control sin presentar credenciales ni ejecutar solicitudes peligrosas:

1. **Permisos:** un usuario sin autorización intenta modificar un recurso privilegiado o perteneciente a otra cuenta; el servidor responde 403 o 404 según el contrato de la ruta y no modifica el registro.
2. **CSRF:** un POST de cambio de estado sin token válido se rechaza. No basta con que la interfaz oculte un botón.
3. **Archivos privados:** una cuenta intenta acceder al documento asociado a otra; la ruta comprueba propietario y evita entregar el archivo.
4. **Excel:** un valor que empieza por caracteres propios de una fórmula se conserva como texto al exportarlo.
5. **Integridad de piezas:** un registro histórico ambiguo no se reescribe ni se exporta omitiendo piezas; se informa del problema para evitar pérdida silenciosa.
6. **Materiales compartidos:** la política de SEC-08 se comprueba por rol tanto en CutLess como en Django Admin.

Estas son **clases de pruebas documentadas en informes y código**, no seis nuevas ejecuciones hechas para redactar este documento.

## 4. Riesgos y comprobaciones que permanecen abiertas

- **SEC-07 / infraestructura real:** comprobar versión y SHA activos en Render, HTTPS/TLS, cabeceras HSTS, atributos de cookies, tratamiento de `X-Forwarded-Proto`, acceso a medios y privilegios de la cuenta PostgreSQL.
- **Migraciones remotas:** cotejar en modo de solo lectura el historial de migraciones efectivamente aplicadas en Supabase con las versiones esperadas; no deducirlo de las migraciones locales.
- **Dependencias:** mantener visible la decisión de aplazar `sqlparse` y `Pillow`; actualizar el análisis de riesgos antes de cualquier cambio.
- **Cobertura de acceso:** completar el inventario de rutas de lectura/escritura por rol y propietario en clientes, proyectos y presupuestos y revisar límites de abuso de login y cálculos según la auditoría.
- **Recuperación pública:** no presentar Brevo como funcionalidad pública activada sin evidencia del despliegue y del comportamiento completo, incluidas cuotas y diferencias de tiempo.
- **No exponer secretos:** no subir contraseñas, cadenas de conexión, claves API, tokens, cookies de sesión, datos reales de clientes ni volcados de la base. Las capturas deben usar cuentas sintéticas o datos anonimizados.

## 5. Conclusión apta para presentar

CutLess incorpora controles de autenticación, separación de roles, autorización por propietario, protección CSRF, validación de entradas, gestión privada de archivos y seguridad de las exportaciones. Estas medidas se respaldan con regresiones automatizadas ejecutadas históricamente sobre SQLite y PostgreSQL locales, pruebas JavaScript y ensayos de navegador. La actualización de Django y la protección de los materiales compartidos añadieron verificaciones de seguridad específicas.

El alcance comprobado es **el código y los entornos locales documentados**. La evaluación de la configuración efectiva del despliegue, los permisos remotos y algunas decisiones de mantenimiento siguen pendientes; por tanto, **no se afirma seguridad absoluta ni validación exhaustiva de producción**.

## 6. Referencias auditables

- [Matriz consolidada de evidencias](MATRIZ_EVIDENCIAS_PRUEBAS_CUTLESS.md).
- [Auditoría integral H01–H17](AUDITORIA_INTEGRAL_CUTLESS.md), [VER-01](VER_01_AUDITORIA_CONSOLIDACION.md) y [SEC-08](SEC_08_PERMISOS_MATERIALES_COMPARTIDOS.md).
- [SEC-01 Django](SEC_01_ACTUALIZACION_DJANGO.md), [cambios de seguridad](CAMBIOS_SEGURIDAD.md), [preparación Render/Supabase](PREPARACION_RENDER_SUPABASE.md).
