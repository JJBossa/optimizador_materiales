# SEC-01. Actualización de Django 5.2 LTS

## Objetivo y alcance

La auditoría SEC-01 identificó avisos de seguridad aplicables a Django 5.2.8, incluidos problemas de disponibilidad en el procesamiento de solicitudes. El objetivo es incorporar los parches de la misma serie LTS y conservar el comportamiento de la aplicación. CutLess actualiza el pin de Django **5.2.8 → 5.2.19** en la rama `fix/sec-01-django-5.2-lts`, sobre `6087aa322653793606d08f520653d374d1caf7e8`. Django 5.2.19 era el último parche publicado de la serie 5.2 LTS al 22 de noviembre de 2026. Se mantuvieron Python 3.13.12 y las otras versiones de la línea base. Los avisos aplicables a dependencias distintas de Django se gestionan por separado. [Serie 5.2 LTS](https://www.djangoproject.com/download/#supported-versions) · [Django 5.2.19 en PyPI](https://pypi.org/project/Django/5.2.19/)

La verificación se realizó en Linux con un entorno virtual aislado, SQLite y PostgreSQL **16.2** local. Se usaron bases de prueba desechables, cuentas sintéticas y directorios temporales para archivos. Antes de crear la base PostgreSQL se comprobaron por socket Unix privado la versión, el directorio de datos temporal y la ausencia de escucha TCP. Las suites Python se ejecutaron sin credenciales heredadas y con bloqueo de DNS y conexiones IP en el arnés. La recuperación de contraseña se probó con dobles locales. La seguridad efectiva de producción y **SEC-07** permanecen pendientes.

## Estado de publicación

| Entorno | Estado |
| --- | --- |
| Local | La actualización, las pruebas y el informe se validaron en `fix/sec-01-django-5.2-lts`. El commit inicial publicado es `b379be71e4e6dc2b3c76be6a1c30717e67469d7e`. |
| GitHub | Rama publicada en el fork y [PR #14](https://github.com/gy0kuroo/optimizador_materiales/pull/14) abierto para revisión, sin fusionar. Su título contiene `[skip preview]` para evitar vistas previas automáticas; eso no desactiva Auto Deploy de la rama monitorizada. |
| Producción | Según lo informado por el usuario, Render tiene Auto Deploy habilitado. No se consultó la configuración del servicio ni la rama conectada; no se ha verificado el despliegue de SEC-01 ni la versión de Django en producción. Supabase quedó fuera de la revisión. |

## Compatibilidad de dependencias

[requirements.txt](../requirements.txt) delega en [cut/requirements.txt](../cut/requirements.txt). La instalación se hizo con restricciones temporales de la línea base para aislar el cambio de Django.

| Componente | Versión verificada | Requisito de Django 5.2.19 |
| --- | --- | --- |
| Python | 3.13.12 | Compatible en la serie 5.2. |
| asgiref | 3.13.0 | Mínimo 3.8.1. |
| sqlparse | 0.5.1 | Mínimo 0.3.1. La compatibilidad de instalación no cambia el estado de sus avisos. |
| tzdata | 2024.2 | Django lo requiere en Windows. CutLess lo fija también en el manifiesto. |

`pip check` pasó. La etapa 2 registró `manage.py check` sin incidencias y `makemigrations --check --dry-run` sin cambios. El chequeo de despliegue usó configuración sintética. [Metadatos de Django 5.2.19](https://pypi.org/pypi/Django/5.2.19/json)

## Avisos que cubre el parche

5.2.19 incluye los parches acumulados de las versiones intermedias. Los casos siguientes resumen el alcance relevante para CutLess. La aplicación de un parche de biblioteca y la exposición efectiva de un servicio son comprobaciones distintas.

| Área | Avisos y primera versión con el parche | Relevancia |
| --- | --- | --- |
| Cabeceras HTTP y localización | CVE-2026-84429 y CVE-2026-77050, **5.2.18** | CutLess usa el procesamiento de solicitudes y `LocaleMiddleware`. Se comprobaron cabeceras de tamaño acotado en solicitudes normales. [Django 5.2.18](https://docs.djangoproject.com/en/5.2/releases/5.2.18/) |
| Procesamiento multipart | CVE-2026-33033, **5.2.13**, y CVE-2026-108147, **5.2.19** | CutLess procesa formularios. La regresión cubre un formulario válido y el rechazo controlado de un cuerpo pequeño sin delimitador. [Django 5.2.13](https://docs.djangoproject.com/en/5.2/releases/5.2.13/) · [Django 5.2.19](https://docs.djangoproject.com/en/5.2/releases/5.2.19/) |
| Permisos de archivos | CVE-2026-25674, **5.2.12** | Aplica al componente `FileSystemStorage` usado por CutLess. La etapa 3 comprobó permisos y contenido en almacenamiento temporal. [Django 5.2.12](https://docs.djangoproject.com/en/5.2/releases/5.2.12/) |
| ORM y PostgreSQL | CVE-2025-13372, **5.2.9**, y CVE-2026-1287 y CVE-2026-1312, **5.2.11** | Son avisos de inyección SQL en condiciones específicas del ORM. En la revisión previa no se identificó el uso requerido de `FilteredRelation` con alias derivados de solicitudes. [Django 5.2.9](https://docs.djangoproject.com/en/5.2/releases/5.2.9/) · [Django 5.2.11](https://docs.djangoproject.com/en/5.2/releases/5.2.11/) |
| Otros componentes de Django | Parches acumulados hasta **5.2.19** | Los avisos de GeoDjango y caché de páginas requieren componentes que no se identificaron en los recorridos de CutLess revisados. [Archivo oficial de seguridad](https://docs.djangoproject.com/en/5.2/releases/security/) |

El cambio de **Django 5.2.10** para `bulk_create()` es una corrección funcional pertinente para la integridad. Django documenta que en PostgreSQL podían truncarse silenciosamente los valores que excedían `max_length`. El rechazo observado con 5.2.19 se contrastó con esa nota oficial. Los nuevos casos no se ejecutaron sobre 5.2.8. [Django 5.2.10](https://docs.djangoproject.com/en/5.2/releases/5.2.10/)

## Archivos

- [cut/requirements.txt](../cut/requirements.txt) cambia solo el pin de Django.
- [test_django_lts_regresion.py](../cut/cutless/tests/test_django_lts_regresion.py) añade seis regresiones de lote, HTTP y sesión.
- [README.md](../README.md#documentación-de-cambios) enlaza este informe desde el índice y explicita la regla de documentación técnica.
- Este documento registra el cambio, la evidencia local y los requisitos de publicación.

## Pruebas complementarias

| Casos nuevos | Resultado en PostgreSQL | Resultado en SQLite |
| --- | --- | --- |
| Lote al límite de 100 caracteres | Nombres íntegros y secuencias independientes para dos propietarios, incluso con lotes de una fila. | Mismo resultado. |
| Lote con un nombre de 101 caracteres después de una fila válida | `DataError`. Se revierte la fila previa del lote y la reserva de correlativos. Se conserva el registro preexistente y la próxima alta usa el correlativo que correspondía a cada propietario. | SQLite conserva los 101 caracteres porque su tipo VARCHAR no impone esa longitud. Se revierte explícitamente el ensayo y se comprueba el mismo estado final y la continuidad de los correlativos. |
| Login multipart válido | GET de login con cabeceras acotadas devuelve 200. Login multipart con CSRF válido autentica y permite acceder al historial. | Mismo resultado. |
| Multipart sin delimitador | El cuerpo pequeño devuelve 400, conserva la tabla de sesiones y el historial continúa protegido. | Mismo resultado. |
| Actividad y expiración | Con reloj simulado y plazo de un minuto, la actividad con CSRF válido renueva la sesión. Una lectura pasiva en estado estable y un POST AJAX rechazado por CSRF conservan el plazo. Tras el vencimiento se deniega el historial y el endpoint de actividad devuelve 401. | Mismo resultado. |
| Logout antes del vencimiento | Se elimina la sesión y la cookie anterior deja de autorizar el historial. | Mismo resultado. |

En el primer ensayo, la primera plantilla autenticada consumió la marca de bienvenida y guardó la sesión. Eso desplazó el vencimiento y provocó una aserción incorrecta en ambos motores. La prueba final renderiza esa plantilla al iniciar el reloj simulado y luego verifica lecturas pasivas en estado estable. La renovación puede ocurrir cuando el servidor modifica la sesión por otros motivos. El temporizador y la detección de actividad de un navegador real quedaron fuera de esta prueba.

## Reproducción

Con Python 3.13.12 y las dependencias instaladas, ejecutar los siguientes comandos desde `cut/`, pasando a cada proceso un entorno aislado con `CUTLESS_ENV=development`, clave sintética y `CUTLESS_MEDIA_ROOT` en un directorio temporal.

```bash
../.venv/bin/python manage.py test cutless.tests.test_django_lts_regresion --noinput -v 2
../.venv/bin/python manage.py test cutless usuarios --noinput -v 2
```

Repetir con SQLite temporal mediante `CUTLESS_DB_ENGINE=sqlite` y `CUTLESS_DB_PATH` local. Para PostgreSQL, iniciar un clúster temporal 16.2 con `listen_addresses` vacío y configurar explícitamente el directorio del socket, el puerto y los parámetros de una base sintética. Antes de usar `createdb` o el runner de Django, comprobar con `psql` sobre la base administrativa `postgres` que `SHOW data_directory` devuelve el directorio temporal, que `inet_server_addr() IS NULL` y que `SHOW server_version` devuelve `16.2`. No usar una conexión heredada. El runner aplica únicamente las migraciones existentes a la base de pruebas que crea y destruye.

## Validación y comparación

En la etapa 3, Django 5.2.19 igualó las **389 aprobadas** de PostgreSQL de la línea base 5.2.8. SQLite obtuvo **383 aprobadas y seis omitidas** por requerir `select_for_update`. La matriz registró **227 solicitudes por motor** y **198 verificaciones de conservación de datos por motor** sin diferencias frente a la auditoría. También pasaron **65 pruebas JavaScript**, **8 del Worker simulado** y **2 comprobaciones de WhiteNoise y FileSystemStorage**. Esas ejecuciones de interfaz, matriz y almacenamiento corresponden a la etapa 3.

La matriz cubrió visitante, propietario, otro usuario, usuario sin permisos, administrador y superusuario. Los resultados coincidieron fila por fila con la auditoría, incluidas las comprobaciones de respuestas, redirecciones y acceso a recursos ajenos. Los 198 casos que debían conservar los datos quedaron conformes por motor. Los 29 restantes comprobaron escrituras autorizadas.

En PostgreSQL pasaron los seis casos que SQLite omite: correlativos por lote, numeración simultánea de presupuestos, reclamo único de trabajos, rechazo del reclamo sustituido, cuota compartida y escritura de una sesión independiente del bloqueo del contador. La etapa 4 volvió a ejecutarlos al repetir la suite Django.

En la etapa 4 se repitieron las suites Django completas con las seis pruebas añadidas. Se comparó por nombre y estado cada prueba preexistente con los registros de la etapa 3 y todos coincidieron.

| Ejecución | Aprobadas | Fallidas / errores | Omitidas | Duración |
| --- | ---: | ---: | ---: | ---: |
| Complementarias · SQLite | 6 | 0 | 0 | 1,551 s |
| Complementarias · PostgreSQL | 6 | 0 | 0 | 1,554 s |
| Suite completa · SQLite | 389 = 383 anteriores + 6 nuevas | 0 | 6 anteriores | 45,220 s |
| Suite completa · PostgreSQL | 395 = 389 anteriores + 6 nuevas | 0 | 0 | 50,375 s |

## Riesgos residuales y requisitos de despliegue

- **sqlparse 0.5.1 y Pillow 11.0.0** conservan avisos propios. Revisar su alcance y sus actualizaciones por separado. [Avisos de sqlparse](https://github.com/andialbrecht/sqlparse/security/advisories) · [Avisos de Pillow](https://github.com/python-pillow/Pillow/security/advisories)
- Las solicitudes acotadas cubren regresiones funcionales. Quedan fuera la medición de capacidad, las pruebas de agotamiento de recursos y el temporizador de sesión en un navegador real.
- **SEC-07 sigue pendiente.** Los avisos de HSTS sobre subdominios y preload ya existían en la comprobación sintética de la etapa 2. La configuración efectiva de proxy, cookies, cabeceras, TLS y privilegios de PostgreSQL requiere evidencia de producción por separado.
- **Auto Deploy de Render:** el usuario confirmó que está habilitado. Fusionar el PR puede iniciar un despliegue si la rama de destino coincide con la rama configurada en Render. `[skip preview]` evita vistas previas automáticas del PR, pero no impide ese despliegue. Antes de fusionar, el administrador debe confirmar la rama conectada, contar con respaldo y reversión, y planificar la validación posterior. La configuración real no fue consultada.
- Antes de un eventual despliegue, revisar y aprobar el diff, confirmar el parche 5.2 vigente y los avisos relevantes, registrar el conjunto resuelto de dependencias, validar el artefacto en un entorno aislado y acordar la comprobación operativa y el procedimiento de reversión. La rama y el PR están publicados, pero el PR no se ha fusionado y la actualización en producción no se ha verificado.

## Reversión

En una copia aislada, restaurar únicamente el pin anterior desde el commit base y reconstruir el entorno virtual con las versiones de referencia. Verificar con `python -m django --version` y `python -m pip check`. Las pruebas y el informe pueden conservarse como evidencia. Volver a 5.2.8 reintroduce la exposición a los avisos enumerados. Cualquier reversión operativa requeriría autorización y evaluación de ese riesgo.

## Conclusión técnica

El parche y las nuevas regresiones están publicados para revisión en el [PR #14](https://github.com/gy0kuroo/optimizador_materiales/pull/14), aún sin fusionar. No se observaron regresiones en las suites repetidas y el único cambio de dependencia es Django. Dado que Render tiene Auto Deploy habilitado según lo informado, la fusión requiere coordinación con quien administra el servicio. El despliegue efectivo y el estado operativo de SEC-01 siguen sin verificar.
