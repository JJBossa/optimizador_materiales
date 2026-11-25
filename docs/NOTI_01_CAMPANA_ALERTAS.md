# NOTI-01 · Campana y centro de alertas de gestión

La base `e1b1b5e3fa7c0a74cef339bf50866584207f7984` incluye PRE-03 y PRO-03. Antes se podían consultar vencimientos y atrasos en cada módulo y se recibían avisos puntuales al crear registros. La campana reúne las situaciones vigentes del espacio propio. El centro renderizado por Django también permite consultarlas sin JavaScript.

## Condiciones y prioridad

| Orden por registro | Aviso | Prioridad | Condición |
| --- | --- | --- | --- |
| Presupuesto 1 | Vencido | Alta | Vencido efectivo o persistido, con validez entre ayer y siete días atrás inclusive. La fecha mostrada corresponde al fin de la validez. |
| Presupuesto 2 | Vence hoy | Alta | Emitido o Enviado, con fecha de validez igual a hoy. |
| Presupuesto 3 | Próximo a vencer | Media | Emitido o Enviado, con validez entre mañana y tres días más. |
| Presupuesto 4 | Pendiente de envío | Baja | Emitido vigente que no tiene un aviso de vigencia de mayor prioridad. |
| Proyecto 1 | Atrasado | Alta | Activo, con término estimado anterior a hoy. |
| Proyecto 2 | Finaliza hoy | Alta | Activo, con término estimado hoy. |
| Proyecto 3 | Inicio pendiente | Alta | En Planificación, con inicio previsto anterior a hoy. |
| Proyecto 4 | Inicia hoy | Media | En Planificación, con inicio previsto hoy. |
| Proyecto 5 | Próximo a finalizar | Media | Activo, con término estimado entre mañana y tres días más. |

Se toma un solo día comercial de `America/Santiago` por evaluación. Las reglas reutilizan los selectores de PRE-03 y PRO-03. Los borradores, aceptados y rechazados quedan fuera de los avisos de presupuestos. Los proyectos cancelados y completados quedan fuera de los avisos de fechas. Cada fecha es opcional y solo se evalúan las reglas que la necesitan.

Cada entidad aporta solo la primera alerta aplicable de su grupo. La identidad combina categoría y clave primaria, así dos registros con el mismo nombre siguen siendo distintos. El orden global es prioridad alta, media y baja, luego fecha relevante ascendente, categoría y clave. Los atrasos más antiguos aparecen antes dentro de una misma prioridad.

## Lectura, permisos y actualización

El contador mide alertas activas de todos los módulos autorizados y no cambia por filtrar, abrir o paginar. A partir de 100 muestra `99+`, con la cifra real en el nombre accesible. Se muestran diez avisos por página. Si se resuelve una situación o se sale de su intervalo, se actualiza la clasificación en la consulta siguiente.

Solo se consultan registros del usuario autenticado, incluidos administradores y superusuarios. La autorización usa los permisos funcionales de los módulos y la preferencia `notificaciones_pantalla`. Ocultar un módulo mediante preferencias del menú no revoca su permiso. Los filtros están disponibles conforme a los permisos. Las preferencias de correo y eventos de creación siguen gestionadas por `enviar_notificacion()`.

El encabezado pide un resumen al cargar y el panel vuelve a consultar al abrir. También consulta al filtrar, paginar o reintentar. Las solicitudes previas se cancelan y se descartan sus respuestas fuera de orden. Las consultas GET no renuevan la sesión. Al recibir una respuesta 401 o al expirar el temporizador de sesión se limpia el contenido privado. Al salir de la página también se limpia el panel. La página alternativa permite navegar y filtrar con enlaces.

El servicio ejecuta una consulta de conteo por módulo permitido. Cuando se pide la lista añade una consulta paginada con la unión de las categorías seleccionadas. Proyecta únicamente la referencia, la fecha, el tipo y la clave. La clasificación se evalúa en SQL y no requiere consultas por aviso. Se conserva el costo de conteo de los registros elegibles de un propietario, con un tamaño de respuesta acotado. Las consultas de negocio son de solo lectura y sus respuestas se sirven con caché privada deshabilitada. Los enlaces se construyen con `reverse()` y el panel los verifica antes de insertarlos. Los textos se insertan como texto plano o se escapan en Django.

La apertura mediante Enter o Space, el cierre con Escape y la recuperación del foco funcionan desde el encabezado. El panel usa controles ordinarios y texto de prioridad. NOTI-01 no requiere migraciones ni dependencias externas.

## Archivos modificados

| Área | Archivos |
| --- | --- |
| Servicio, rutas y permisos | `cut/cutless/services/alertas.py`, `cut/cutless/views/alerts.py`, `cut/cutless/urls.py`, `cut/cutless/templatetags/alertas.py` |
| Encabezado y centro sin JavaScript | `cut/cutless/templates/cutless/base.html`, `cut/cutless/templates/cutless/includes/campana_alertas.html`, `cut/cutless/templates/cutless/centro_alertas.html` |
| Recursos y expiración de sesión | `cut/cutless/static/cutless/button-icons.svg`, `cut/cutless/static/cutless/css/alertas.css`, `cut/cutless/static/cutless/js/alertas.js`, `cut/cutless/static/cutless/js/session-timeout.js` |
| Preferencias | `cut/usuarios/templates/usuarios/configuracion_sistema.html` |
| Pruebas | `cut/cutless/tests/test_alertas.py`, `cut/cutless/tests/js/alertas.test.cjs`, `cut/cutless/tests/browser/fixtures-centro-alertas.py`, `cut/cutless/tests/browser/centro-alertas.cjs` |
| Documentación | `docs/NOTI_01_CAMPANA_ALERTAS.md` |

## Verificación local

Las suites se ejecutaron en desarrollo con SQLite 3.50.4 y PostgreSQL 16.16 en un contenedor aislado con puerto en loopback. Se usaron bases desechables y datos sintéticos. Se verificaron las consultas del servicio con 107 alertas propias y 110 registros ajenos. El resumen usó 2 consultas y la lista paginada 3. Se comprobó el contador y la ausencia de duplicados al recorrer las páginas filtradas. Las mediciones excluyen la autenticación y la lectura inicial del perfil.

Desde `cut/`, con `CUTLESS_ENV=development`, una clave local y las variables `CUTLESS_DB_*` apuntando a cada base desechable, se ejecutaron estos comandos.

```sh
python manage.py test --noinput -v 2
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py migrate --plan
```

Desde la raíz se ejecutaron las pruebas de Node y se verificó el diff completo de la rama.

```sh
git ls-files -z '*.test.cjs' '*.test.mjs' | xargs -0 node --test
git diff --check upstream/main HEAD
```

Para repetir el recorrido de la campana, usar una base SQLite nueva y asignar a `CUTLESS_TEST_FIXTURE` la ruta absoluta de un archivo aún inexistente. El recorrido importa Playwright 1.62.1. `CUTLESS_TEST_BOOTSTRAP` y `CUTLESS_TEST_BOOTSTRAP_JS` apuntan a las copias locales de Bootstrap 5.3.0, y `CUTLESS_TEST_INTRO_DIR` al directorio `minified` de Intro.js 7.2.0. Son recursos de la interfaz existente. `CUTLESS_TEST_CHROMIUM` permite indicar un ejecutable local y `CUTLESS_TEST_EVIDENCE` un directorio para las capturas. Desde `cut/`, con esas variables exportadas y `CUTLESS_TEST_ORIGIN=http://127.0.0.1:9332`, se ejecutaron los siguientes comandos en dos terminales.

```sh
python manage.py migrate --noinput
python manage.py shell < cutless/tests/browser/fixtures-centro-alertas.py
python manage.py runserver 127.0.0.1:9332 --noreload --nothreading
```

```sh
node cutless/tests/browser/centro-alertas.cjs
```

| Verificación | Aprobadas | Fallidas | Omitidas |
| --- | ---: | ---: | ---: |
| Django 5.2.19, PostgreSQL | 575 | 0 | 0 |
| Django 5.2.19, SQLite | 563 | 0 | 12 |
| JavaScript, Node 24.22.1 | 82 | 0 | 0 |
| Playwright, Chromium 156.0.8078.79 | 4 recorridos | 0 | 0 |

Las doce omisiones de SQLite requieren `SELECT FOR UPDATE` y pasaron en PostgreSQL. `check` y `makemigrations --check --dry-run` pasaron en ambos motores. El plan quedó vacío después de aplicar las migraciones existentes. `git diff --check` pasó.

Los cuatro recorridos de Chromium fueron `centro-alertas`, `acciones-gestion`, `ciclo-proyectos` y `ciclo-presupuestos`. El primero cubrió 320, 390, 768 y 1440 px, tema claro, oscuro y automático, fuente configurable, menú móvil, grupos del lateral, perfil, Ayuda, teclado, avisos de sesión, peticiones concurrentes y alternativa sin JavaScript. También verificó la desaparición de avisos tras iniciar, completar o reprogramar un proyecto y registrar el envío de un presupuesto. Dos ejecuciones preliminares del recorrido nuevo fallaron por expectativas de la prueba. Se ajustó la primera para consultar un aviso que corresponde a la primera página según el orden de prioridad. La segunda ahora espera a que la Ayuda termine de cerrar y devuelva el foco al botón.

## Evidencias y límites

Capturas generadas fuera de Git con registros sintéticos.

- `noti01-campana-cerrada.png`
- `noti01-panel-escritorio-oscuro.png`
- `noti01-panel-movil-claro.png`
- `noti01-filtro-presupuestos.png`
- `noti01-filtro-proyectos.png`
- `noti01-estado-vacio.png`

Las descargas de Firefox y WebKit para Playwright devolvieron HTTP 403. Esos motores y Safari en dispositivos iOS quedaron sin verificar. Los anchos móviles se comprobaron en Chromium.

El panel se actualiza por navegación o interacción. Si la sesión se invalida en otra pestaña, el siguiente GET o el temporizador local limpia el panel. Los cambios entre páginas pueden mover registros en la paginación por desplazamiento y el panel descarta identificadores duplicados. El contador y la lista representan condiciones vigentes. Un historial o estado de lectura requeriría persistencia en un trabajo independiente.
