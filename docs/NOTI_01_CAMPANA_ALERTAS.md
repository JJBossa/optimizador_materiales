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
