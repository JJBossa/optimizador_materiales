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

## Verificación local

| Comprobación | Resultado |
| --- | --- |
| Django 5.2.19 con SQLite 3.50.4 | 517 casos, 509 aprobados y 8 omitidos porque SQLite carece de `select_for_update`. |
| Django 5.2.19 con PostgreSQL 16.16 aislado | 517 casos aprobados. |
| JavaScript con Node 24.22.1 | 75 casos aprobados, incluidos 8 del Worker de recuperación con dobles locales. |
| Chromium 156 con Playwright | Los seis escenarios VAL-01B pasaron a 320, 390 y 1280 px en ambos temas. Se comprobó el máximo nativo, conservación del usuario al cambiar su correo, un POST excesivo, el error accesible, la corrección y el campo de alta rápida en Presupuestos. |
| Plantillas y esquema | 16 vistas del smoke test devolvieron HTTP 200. `makemigrations --check --dry-run` informó que no había cambios en ambos motores. `git diff --check` pasó. |

Las pruebas Django incluyen el límite exacto y el exceso en POST, Unicode y NFKC, cambios de nombre frente a ediciones de otros campos, permisos y pertenencia, copias y selección de clientes históricos. También comprueban que un nombre inválido en el alta rápida deja intactos el cliente y el presupuesto. [Pruebas de negocio](../cut/cutless/tests/test_limites_nombres.py) · [Pruebas de usuarios](../cut/usuarios/test_limite_username.py)

### Regresión de navegador y limitaciones

Completaron 17 de los 20 recorridos de Chromium, incluido VAL-01B. El recorrido de tablas verificó 17 pantallas a ocho anchos entre 320 y 1280 px en ambos temas, comparó el escritorio con `upstream/main` y completó los flujos interactivos. Los demás recorridos aprobados cubren contacto y direcciones, proyectos, materiales, importes, validación numérica, visores, estadísticas, Findic y descargas.

`fecha-presupuestos.cjs`, `fecha-edicion-presupuestos.cjs` e `historial-acciones.cjs` pasaron los escenarios con JavaScript alcanzados y agotaron el tiempo al interactuar con la interfaz sin JavaScript. Los tres tiempos de espera se reprodujeron con el mismo Chromium y datos sintéticos sobre `upstream/main` en `55df10e`. La ejecución se hizo en Chromium para Linux. Firefox, Safari y dispositivos físicos quedaron fuera de la verificación.

Se usaron bases desechables y datos sintéticos. PostgreSQL 16.16 se ejecutó en un contenedor con almacenamiento temporal y un puerto accesible por loopback.

### Reproducción

Ejecutar `python manage.py test --noinput -v 2` y `python manage.py makemigrations --check --dry-run` desde `cut/` con `CUTLESS_ENV=development` y los parámetros de cada motor apuntando a bases desechables. Desde la raíz, `git ls-files '*.test.cjs' '*.test.mjs' -z | xargs -0 node --test` ejecuta las suites JavaScript.

Para repetir VAL-01B en Chromium, migrar una SQLite local vacía y apuntar `CUTLESS_TEST_FIXTURE` a un archivo temporal nuevo. Cargar el fixture con `python cut/manage.py shell < cut/cutless/tests/browser/fixtures-limites-nombres.py` y servir esa base en loopback. Con Playwright disponible, ejecutar `node cut/cutless/tests/browser/limites-nombres.cjs`. Configurar `CUTLESS_TEST_ORIGIN`, `CUTLESS_TEST_CHROMIUM` y las rutas a Bootstrap 5.3.0 local en `CUTLESS_TEST_BOOTSTRAP` y `CUTLESS_TEST_BOOTSTRAP_JS`. El recorrido bloquea las solicitudes externas. [Fixture local](../cut/cutless/tests/browser/fixtures-limites-nombres.py) · [Recorrido de navegador](../cut/cutless/tests/browser/limites-nombres.cjs)
