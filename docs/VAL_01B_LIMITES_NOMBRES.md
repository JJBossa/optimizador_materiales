# VAL-01B · Límites para nombres

Base `gy0kuroo/optimizador_materiales:main`, commit `55df10e766b90098d1e50244b5371d8f729747e1`. El ajuste continúa sobre `feat/val01b-limites-texto` a partir de `b7c4049`. [Auditoría VAL-01A](https://github.com/JJBossa/optimizador_materiales/blob/03b038992e695c2cb9420f4f4190d7083eef4192/docs/VAL_01_AUDITORIA_LIMITES_TEXTO.md)

## Rutas revisadas y decisiones de compatibilidad

Los nombres nuevos y los renombrados admiten un máximo de **30 unidades UTF-16**, el mismo conteo que `maxlength`. Por ejemplo, `ñ` cuenta como una y `🪵` como dos. Django conserva el recorte de espacios exteriores, la compactación de espacios internos del nombre de trabajo y la validación del nombre de usuario tras la normalización NFKC.

| Campo | Rutas |
| --- | --- |
| Trabajo | Inicio, edición completa, renombrado, duplicación y Django Admin. |
| Pieza | Optimizador, filas dinámicas, editor de plantillas, CSV y listado de piezas de Django Admin. |
| Proyecto | Alta y edición, con o sin optimizaciones asociadas. |
| Cliente o razón social | Alta, edición y actualización de ubicación en Clientes. Alta rápida al crear o editar un borrador de Presupuestos. |
| Material | Catálogo, Django Admin y catálogo predefinido. |
| Plantilla | Alta desde cero o desde una optimización, edición propia, carga y copia de predefinidas. |
| Usuario | Registro, perfil, panel de usuarios, Django Admin y `createsuperuser`. |

- La excepción histórica parte del valor guardado del objeto autorizado. Reenviar el nombre al editar otros campos lo conserva literalmente. Las columnas, el esquema y el acceso de usuarios históricos de hasta 150 caracteres conservan su capacidad. Los nuevos usuarios admiten las letras y números Unicode y los símbolos `@ . + - _` de Django. La recuperación de cuenta sigue usando su propia validación.
- En una optimización o plantilla existente se puede conservar cada aparición de un nombre histórico. Las filas carecen de identificadores persistentes, por lo que se comparan las apariciones del nombre en el registro original. Esto permite eliminar o mover filas y cambiar medidas o cantidades. Una aparición adicional de un nombre largo exige acortarlo.
- El parser y el serializador conservan el texto de cada nombre, incluidas comillas, comas, espacios y saltos de línea. Si el navegador convierte CRLF a LF, una coincidencia restaura el literal guardado. Si el listado de piezas sigue igual, se conserva también su representación anterior. Django valida cada nombre del CSV o del listado técnico del admin, que tienen un solo textarea para varias piezas. En el admin un listado antiguo ilegible puede conservarse tal cual al editar otros campos. Los flujos que necesitan interpretar ese listado, como recalcular o exportar, mantienen su validación de formato.
- Copiar una plantilla predefinida, duplicar un trabajo, crear una plantilla desde un trabajo o calcular a partir de una plantilla crea un registro nuevo. Los formularios conservan el texto de origen para que se pueda acortar antes de guardar. Una plantilla histórica con datos técnicos válidos se puede cargar aunque sus nombres sean largos. El nombre de trabajo sigue siendo opcional.
- Presupuestos permite seleccionar por ID a un cliente propio con razón social histórica. El alta rápida aplica 30 y se ejecuta dentro de la transacción del presupuesto, con el permiso existente de Presupuestos. Los presupuestos emitidos conservan los nombres y piezas de su detalle guardado al cambiar de estado.
- Correos, contraseñas, direcciones, descripciones, notas, RUT, identificadores técnicos y filtros conservan sus validaciones específicas. Los comandos con datos fijos y las escrituras directas de mantenimiento o migración se rigen por sus datos de origen y por el esquema.

## Verificación local

| Comprobación | Resultado |
| --- | --- |
| Django 5.2.19 con SQLite 3.50.4 | 522 casos, 514 aprobados, 0 fallidos y 8 omitidos porque SQLite carece de `select_for_update`. |
| Django 5.2.19 con PostgreSQL 16.16 aislado | 522 casos aprobados, 0 fallidos y 0 omitidos. |
| JavaScript con Node 24.22.1 | 75 casos aprobados, incluidos 8 del Worker de recuperación con dobles locales. 0 fallidos y 0 omitidos. |
| Chromium 156 con Playwright | 6 recorridos aprobados y 2 con tiempos de espera preexistentes de los 8 ejecutados. Los seis escenarios de VAL-01B pasaron a 320, 390 y 1280 px en temas claro y oscuro. |
| Plantillas y esquema | 16 vistas del smoke test devolvieron HTTP 200. `makemigrations --check --dry-run` informó que no había cambios en ambos motores. `git diff --check` pasó. |

Las pruebas Django incluyen el límite exacto y el exceso en POST, Unicode y NFKC, login con un usuario histórico de 150 caracteres, permisos, copias, edición de filas y compatibilidad del CSV. Comprueban la atomicidad del alta rápida y la conservación de piezas y nombres en un presupuesto emitido. La primera ejecución detectó tres casos con datos de alta que excedían el nuevo límite. Se adaptaron los datos de alta y se conservó el caso con un nombre largo en el recorrido histórico de edición y exportación. [Pruebas de negocio](../cut/cutless/tests/test_limites_nombres.py) · [Pruebas de usuarios](../cut/usuarios/test_limite_username.py)

### Regresión de navegador y limitaciones

Pasaron `limites-nombres.cjs`, `contacto-clientes.cjs`, `direcciones-clientes.cjs`, `num01-validacion.cjs`, `importes-formularios.cjs` y `num03-formatos-precision.cjs`. VAL-01B verificó el máximo nativo en trabajo, usuario, alta rápida y filas dinámicas, la respuesta accesible a un POST manipulado y el guardado de una plantilla con una pieza histórica intacta. NUM-03 aprobó sus 20 escenarios con y sin JavaScript.

`fecha-presupuestos.cjs` y `fecha-edicion-presupuestos.cjs` pasaron el escenario de 390 px con JavaScript y agotaron el tiempo al interactuar sin JavaScript. Ambos tiempos de espera se habían reproducido con el mismo Chromium y datos sintéticos sobre `upstream/main` en `55df10e`. Los demás recorridos de navegador, otros motores y dispositivos físicos quedaron fuera de esta ejecución.

Se usaron bases desechables y datos sintéticos. PostgreSQL 16.16 se ejecutó en un contenedor con almacenamiento temporal y un puerto accesible por loopback.

### Reproducción

Ejecutar `python manage.py test --noinput -v 2` y `python manage.py makemigrations --check --dry-run` desde `cut/` con `CUTLESS_ENV=development` y los parámetros de cada motor apuntando a bases desechables. Desde la raíz, `git ls-files '*.test.cjs' '*.test.mjs' -z | xargs -0 node --test` ejecuta las suites JavaScript.

Para repetir VAL-01B en Chromium, migrar una SQLite local vacía y apuntar `CUTLESS_TEST_FIXTURE` a un archivo temporal nuevo. Cargar el fixture con `python cut/manage.py shell < cut/cutless/tests/browser/fixtures-limites-nombres.py` y servir esa base en loopback. Con Playwright disponible, ejecutar `node cut/cutless/tests/browser/limites-nombres.cjs`. Configurar `CUTLESS_TEST_ORIGIN`, `CUTLESS_TEST_CHROMIUM` y las rutas a Bootstrap 5.3.0 local en `CUTLESS_TEST_BOOTSTRAP` y `CUTLESS_TEST_BOOTSTRAP_JS`. El recorrido bloquea las solicitudes externas. [Fixture local](../cut/cutless/tests/browser/fixtures-limites-nombres.py) · [Recorrido de navegador](../cut/cutless/tests/browser/limites-nombres.cjs)
