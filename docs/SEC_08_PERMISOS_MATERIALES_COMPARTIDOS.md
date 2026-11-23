# SEC-08 · Permisos del catálogo de materiales

La base es `b34b6a4a2f6fde3661dda9341b8e5cbece08f900`, que incorpora VIS-06. [PR #34](https://github.com/gy0kuroo/optimizador_materiales/pull/34)

## Modelo de amenazas y evidencia

El límite es el propietario del material y, para un material predefinido, el rol autorizado sobre el catálogo. El atributo `is_staff` solo habilita la entrada a Django Admin. Allí también se exigen los permisos de modelo de la operación.

- El queryset anterior incluía materiales predefinidos para cuentas staff. Los permisos heredados de Django Admin no añadían una comprobación de rol para editar o borrar esos objetos. Una prueba existente incluso esperaba que staff con `change_material` pudiera editar un predefinido. El formulario exponía `usuario` y `es_predefinido` y el guardado incluía los campos cambiados. La evidencia de la versión anterior se obtuvo del código y de esa expectativa registrada. Las pruebas HTTP nuevas comprueban los controles sobre la versión corregida. [Admin](../cut/cutless/admin.py) · [Regresiones existentes](../cut/cutless/tests/test_num02_materiales.py)
- El queryset de Django Admin ya excluía los materiales personales de otros propietarios para cuentas no superusuarias. La vista pública de edición consultaba primero por ID, y su respuesta distinguía un ID ajeno existente de uno inexistente. Edición y borrado públicos ahora buscan en el mismo conjunto visible y responden 404 para materiales personales ajenos. [Vistas](../cut/cutless/views/materials.py)
- La edición pública anterior quitaba el propietario al guardar cualquier material predefinido, incluidos los registros antiguos que conservaban uno. La corrección preserva esa combinación. También se evita presentar estos materiales como personales en la lista. [Vistas y agrupación del catálogo](../cut/cutless/views/materials.py)

## Política efectiva

| Actor | Vistas de CutLess | Django Admin |
| --- | --- | --- |
| Usuario normal sin permiso de gestión | Puede usar los materiales disponibles para su cuenta en Optimización si tiene acceso a sus costos. | Sin acceso con `is_staff=False`. |
| Usuario con gestión de materiales | Puede crear, editar y borrar personales propios, y consultar el catálogo. | Requiere `is_staff` y los permisos de Django. |
| Staff sin rol de catálogo | Se aplican los permisos públicos de su cuenta. | Con los permisos de modelo correspondientes, administra sus personales y consulta predefinidos. Las altas quedan como personales propias. |
| Delegado con `rol='admin'` | Como permite la política vigente, puede editar y borrar predefinidos. Los personales ajenos quedan fuera de las rutas públicas. | Con `is_staff` y el permiso del modelo correspondiente, puede editar y borrar predefinidos y personales propios. |
| Superusuario | Puede gestionar el catálogo y sus materiales personales por las rutas públicas existentes. | Puede gestionar todo el catálogo y modificar explícitamente propietario y clasificación. |

Solo el superusuario puede cambiar `usuario` y `es_predefinido` en Django Admin. Las otras cuentas tampoco tienen acceso a la columna ni al filtro de propietario. Una selección masiva que incluya un material visible sin permiso de eliminación queda bloqueada por los permisos por objeto. Los materiales ajenos que quedan fuera del queryset tampoco entran en la selección.

Las confirmaciones de borrado individual y masivo en Django Admin protegen los materiales vinculados a optimizaciones, al igual que la vista pública. Así se conserva la relación que el modelo podría poner a nulo al borrar el material. El catálogo válido sigue disponible en Optimización y el formulario conserva las reglas de precisión, unidades y precios. [Pruebas de permisos](../cut/cutless/tests/test_permisos_catalogo.py)

## Límites y verificación

El alcance cubre las rutas de Materiales de CutLess y Django Admin. Los borrados ejecutados por código externo a esas rutas, las cascadas al eliminar cuentas y la coordinación concurrente entre un borrado y una nueva asociación requieren una política aparte. La protección de referencias comprueba las asociaciones existentes al confirmar el borrado y no cambia la restricción de base de datos. La intervención no aplica cambios masivos sobre registros históricos.

Pasaron 63 pruebas dirigidas en SQLite y 63 en PostgreSQL local con cuentas y materiales sintéticos. Las dos ejecuciones produjeron los mismos resultados. Cubren lectura y escritura por rol, altas, cambios de propietario, edición histórica, borrados individual y masivo, materiales asociados, uso del catálogo y reglas numéricas. `makemigrations --check --dry-run` no detectó cambios de esquema y `git diff --check` pasó.
