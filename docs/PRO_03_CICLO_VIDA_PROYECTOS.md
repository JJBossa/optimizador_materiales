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
