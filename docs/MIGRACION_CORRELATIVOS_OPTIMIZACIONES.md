# Migración del correlativo de optimizaciones por usuario

## Identidad y referencias históricas

El código visible se obtiene del `correlativo` de cada propietario. La clave primaria `id` sigue identificando la optimización en las URLs, el visor, las selecciones y las relaciones con tableros, presupuestos, clientes y proyectos. Dos propietarios pueden tener `OPT-0001`. Las búsquedas de la aplicación consultan el correlativo dentro de las optimizaciones del usuario autenticado.

| Referencia previa | Efecto después de migrar |
| --- | --- |
| URLs e identificadores internos | Conservan el `id` y las reglas de acceso. |
| Código copiado en un correo, aviso, documento o sistema externo | El texto histórico permanece. Consulta el CSV por propietario y código anterior para obtener el código nuevo y confirmar el `id`. Un código antiguo puede coincidir con el código nuevo de otro trabajo del mismo propietario. |
| Presupuesto emitido con `detalle_emitido` | Conserva el código y los importes congelados. Los nuevos presupuestos emitidos guardan el correlativo vigente al momento de la emisión. |
| Borrador o presupuesto histórico anterior a `detalle_emitido` | Las líneas que consultan optimizaciones actuales mostrarán el código nuevo. La migración conserva importes, estados, cliente, proyecto y asociaciones. |
| PDF, Excel o PNG guardados o entregados | Los archivos ya existentes se conservan. Una nueva descarga usa el correlativo en su nombre y en el contenido que se genera. El PNG histórico que carece de geometría conserva el contenido de su imagen original. |
| Trabajos borrados antes de esta migración | Quedan fuera de la asignación inicial. El CSV solo incluye registros existentes al momento de migrar. |

## Migraciones preparadas

- `0007_correlativo_optimizaciones` agrega el campo, recorre cada usuario por fecha ascendente e `id` ascendente para resolver empates, asigna `1…N` y guarda `N+1` en `ContadorOptimizacion`. Los usuarios sin historial obtienen `1` en su primera alta. El recorrido se escribe por lotes y solo toca el campo nuevo de las optimizaciones.
- `0008_restricciones_correlativo_optimizacion` exige un valor positivo y único por `(usuario, correlativo)` y hace el campo obligatorio. Mantener el relleno y la validación en dos migraciones separa las escrituras históricas de las restricciones finales.
- Las altas individuales y por lotes reservan números dentro de la transacción de inserción. PostgreSQL bloquea una fila del contador por propietario en cada reserva. Un fallo de inserción revierte también la reserva. El contador sobrevive a borrar el último plan o todo el historial del usuario. Si se elimina la cuenta, se aplica la relación en cascada existente para sus datos y el contador.

## Respaldo, ensayo e informe de correspondencia

Antes de migrar cualquier entorno compartido, ensaya con una copia sanitizada y confirma espacio y tiempo de bloqueo. Estas instrucciones requieren autorización separada para producción.

1. Detén las altas, ediciones y eliminaciones durante toda la ventana, desde la generación del CSV previo hasta la validación posterior. Impide escrituras de instancias anteriores. Comprueba que el destino es el entorno autorizado y que el respaldo cubre tanto PostgreSQL como los archivos persistidos fuera de la base. Verifica restaurando en un destino aislado y guarda el respaldo y su suma SHA-256 en almacenamiento privado.
2. Con el nuevo código instalado en el entorno de mantenimiento y antes de ejecutar `migrate`, genera el CSV de solo lectura. Usa identificadores internos y códigos. Guárdalo de forma privada y compártelo solo con responsables autorizados.

   ```bash
   python cut/manage.py informe_correlativos_optimizaciones > correlativos-previstos.csv
   ```

3. Tras revisar la correspondencia, aplica `python cut/manage.py migrate cutless 0008` en el entorno autorizado. Mantén detenidas las escrituras y genera el informe con la asignación persistida.

   ```bash
   python cut/manage.py informe_correlativos_optimizaciones --aplicado > correlativos-aplicados.csv
   diff -u correlativos-previstos.csv correlativos-aplicados.csv
   ```

   El informe tiene una fila por optimización. Una fila de ejemplo con datos ficticios sería `7,24,OPT-0024,OPT-0002` bajo las columnas `usuario_id,optimizacion_id,codigo_anterior,codigo_nuevo`.

4. Confirma que ambos informes coincidan fila por fila y que los conteos de optimizaciones, tableros, presupuestos y relaciones sean iguales a los previos. Revisa cuentas con fechas empatadas, presupuestos emitidos y descargas existentes. Resguarda el CSV de la ventana de mantenimiento como referencia histórica. Un CSV proyectado desde el historial de un día posterior puede diferir debido a altas o bajas.
5. Verifica las altas nuevas con dos cuentas en la copia de ensayo. Si la validación del entorno compartido pasa, reanuda las escrituras con la versión nueva. Evita importaciones directas de filas que omitan el contador. Una restauración completa debe conservar la tabla del contador además de las optimizaciones.

## Recuperación

Si falla el ensayo o la validación inicial con las escrituras aún detenidas, usa el respaldo previo y la versión anterior, y comprueba que los conteos y las referencias coincidan con el punto de corte. Las dos migraciones usan las transacciones normales de Django y cada migración tiene su propio punto de confirmación.

Si ya se emitieron códigos nuevos, conserva el esquema y los contadores, detén las escrituras si hay una incidencia y corrige hacia adelante. Volver al esquema `0006` elimina los correlativos y los contadores. Restaurar directamente un respaldo anterior también excluiría las optimizaciones creadas después del corte. Si la restauración resulta imprescindible, conserva primero una copia actual de la base y los archivos, reconcilia las altas, ediciones, eliminaciones y los contadores en un entorno aislado, y valida que ningún código publicado se reutilice antes de reabrir el servicio.
