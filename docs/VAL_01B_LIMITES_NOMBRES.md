# VAL-01B · Límites para nombres

Base `gy0kuroo/optimizador_materiales:main`, commit `55df10e766b90098d1e50244b5371d8f729747e1`. Referencia [auditoría VAL-01A](https://github.com/JJBossa/optimizador_materiales/blob/03b038992e695c2cb9420f4f4190d7083eef4192/docs/VAL_01_AUDITORIA_LIMITES_TEXTO.md).

## Rutas revisadas y decisiones de compatibilidad

| Campo | Máximo | Rutas |
| --- | ---: | --- |
| Nombre del trabajo | 50 | Inicio, edición completa, renombrado, duplicación y altas/ediciones de optimización en Django Admin. |
| Proyecto | 80 | Alta y edición, con o sin optimizaciones asociadas. |
| Cliente o razón social | 120 | Alta, edición y actualización de ubicación en Clientes. Alta rápida al crear o editar un presupuesto en borrador. |
| Material | 80 | Alta y edición en el catálogo y en Django Admin, incluidos materiales predefinidos cuando el actor tiene permiso. |
| Plantilla | 80 | Alta desde cero o desde una optimización, edición propia, carga y copia de plantillas predefinidas. |
| Usuario | 30 | Registro, perfil, gestión de usuarios de CutLess y alta/edición en Django Admin. |
| Pieza | 50 | Formularios de piezas del optimizador y editor dinámico/CSV de las plantillas. Se conserva el contrato existente. |

- La excepción histórica se basa en el valor guardado del objeto que ya se autorizó cargar. Reenviar ese nombre al editar otros campos lo conserva literalmente. Un nombre distinto debe cumplir el máximo. El ancho de las columnas, los datos y el esquema se conservan.
- Duplicar un trabajo o copiar una plantilla predefinida crea un registro nuevo. El formulario muestra el nombre original para que se pueda acortar si excede el límite. Se puede dejar el nombre de trabajo vacío. Una plantilla con nombre histórico largo puede seguir cargándose si sus datos técnicos son válidos.
- En Presupuestos se puede seleccionar por ID a un cliente propio con nombre histórico largo. El campo de alta rápida admite hasta 120 caracteres, incluso si el nombre escrito coincide con un cliente antiguo. El alta rápida usa el permiso existente de Presupuestos y sigue dentro de su transacción. Los presupuestos emitidos conservan su flujo de edición de estado y sus datos históricos.
- Los nuevos nombres de usuario aceptan las letras y números Unicode y los símbolos `@ . + - _` que ya admite el registro de Django. El perfil amplía su regla de solo letras y usa la misma normalización NFKC. Las cuentas existentes conservan su nombre y el acceso sigue usando la capacidad de 150 caracteres de Django. Login, recuperación y el comando de aprovisionamiento `createsuperuser` conservan sus contratos operativos.
- Los campos nuevos cuentan unidades UTF-16, igual que `maxlength`. Por ejemplo, `ñ` cuenta como una y `🪵` como dos. Django conserva el recorte de espacios exteriores al validar y el nombre de trabajo mantiene la compactación de espacios internos que ya aplicaba al guardarse. Los nombres de usuario también se validan después de la normalización. Los nombres de piezas mantienen sus validaciones existentes, incluido el conteo de puntos de código en Django al recibir POST o CSV.
- Los filtros, las selecciones por ID y el comando de catálogo con nombres fijos se revisaron como consumidores o datos operativos. El campo técnico de piezas serializadas de Django Admin, los imports de datos, notas, descripciones, direcciones y contactos conservan su contrato.
