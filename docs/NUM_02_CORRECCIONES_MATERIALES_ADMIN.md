# NUM-02 · Validaciones de Materiales y Django Admin

## Objetivo y base

Alinear las validaciones de alta y edición de Materiales y proteger el consumo del catálogo en nuevas optimizaciones. El trabajo parte de `9378d38f556748f200c7407598dc1adbb620a7f2` en `fix/num02-validaciones-materiales-admin`. La referencia se contrastó con `upstream/main`, que incluye [NUM-01 (PR #22)](https://github.com/gy0kuroo/optimizador_materiales/pull/22).

## Contrato de datos y validación

- Las dimensiones se guardan en centímetros. El formulario público recibe la unidad elegida y convierte los lados nuevos o modificados. Django Admin recibe centímetros y el selector controla la unidad de presentación. Ambos aplican la conversión canónica a seis decimales y comprueban que los lados sean finitos y queden entre 10 y 300 cm, inclusive.
- Los campos numéricos de Materiales usan el formato de NUM-01. La coma y el punto representan decimales. Se rechazan los separadores de miles, las formas ambiguas como `1.000` y `1,000`, la notación científica, el texto y los valores no finitos. Una medida como `122.1250` desambigua tres decimales. El precio sigue siendo opcional, admite cero y tiene hasta ocho dígitos enteros y dos decimales.
- En una edición, si la dimensión ingresada equivale a la inicial en la misma unidad de entrada, el formulario conserva el valor original en centímetros. Cambiar la unidad pública requiere validar ambas dimensiones en la nueva unidad. Cambiar la unidad de presentación en Admin conserva la lectura en cm. Las vistas de edición guardan solo los campos que cambian y la fecha, además de aplicar la regla preexistente de propietario para predefinidos. Así se conserva incluso un precio histórico que SQLite almacena con más decimales que los que muestra Django.
- Las medidas históricas fuera de rango que se pueden representar y los precios negativos históricos se señalan en la ayuda del campo. Pueden conservarse en una edición si el valor numérico no cambia. Un valor nuevo debe cumplir todas las reglas. Las medidas no finitas y las que desbordan la conversión de presentación deben corregirse explícitamente antes de guardar. Una unidad histórica desconocida exige selección explícita. El formulario presenta sus medidas en cm hasta que el usuario elige una unidad. Los rechazos conservan el formulario enlazado y la base intacta.
- La optimización admite un precio explícito válido, incluido cero. Si el precio está vacío y el material tiene un importe, se verifica su validez antes de usarlo. Un valor histórico incompatible produce un error en el formulario. Los datos inválidos de catálogo no precargan dimensiones ni precios en el navegador. Se mantienen las asociaciones y los costos ya guardados.
- El Admin de Django conserva sus campos de propietario y predefinido, su queryset y sus permisos. CutLess conserva sus reglas de perfil, propiedad y acceso a predefinidos. Usar un material predefinido sigue autorizado en ambas rutas pertinentes.

## Auditoría y resultado

La auditoría previa comparó alta y edición pública y Django Admin con SQLite y PostgreSQL. Reprodujo el ingreso por teclado en Chromium. El informe original y sus evidencias se conservaron fuera del repositorio en el entorno de trabajo (`/workspace/shared/cutless-num02/AUDITORIA_NUM_02_MATERIALES.md`).

| Evidencia de auditoría | Antes y causa | Después de NUM-02 |
| --- | --- | --- |
| B01–B08, N17, N33. Coma decimal | El formulario generado por Django Admin usaba `type="number"`. Chromium `es-CL` convirtió `12,5` en `125` antes del POST en los ensayos. | Los dos formularios usan texto con teclado decimal. En Chromium enviaron `12,5` literalmente y SQLite guardó `12.50` en alta y edición, con JS habilitado y deshabilitado. `12.5` tuvo el mismo resultado. |
| N19–N24, N35. Sintaxis | Django Admin aceptaba algunas expresiones que el formulario público rechazaba, entre ellas `1.000` para medidas, notación científica y un guion bajo entre dígitos. | Los dos formularios aplican un analizador estricto en Django. Los errores conservan el texto y los datos de los demás campos. El formulario público además rechaza el formato ambiguo por `pattern` en Chromium. Django Admin envía el valor y muestra el rechazo del servidor. |
| N04–N08, N13–N16, N40. Rango y escala | Los `FloatField` generados por Admin no aplicaban el rango de catálogo. La etiqueta del selector podía sugerir que los números estaban en la unidad seleccionada. | Los dos validan 10–300 cm inclusive. Admin etiqueta «Ancho (cm)», «Alto (cm)» y «Unidad de presentación». El formulario público convierte desde la unidad seleccionada. |
| H01–H03. Edición histórica | El formulario público convertía y redondeaba de ida y de vuelta. Podía variar las dimensiones en pulgadas o pies y bloquear un lado histórico de 300 cm en pies. | Si el usuario conserva el valor presentado y la unidad de entrada, se mantiene el valor en cm tal como se leyó del registro. Cada lado se evalúa por separado. Se verificó conservar `122.1234567` y `300.0` cm mediante una edición de metadatos en Chromium. |
| N27–N32, H02, I01. Precio | Admin admitía negativos. La optimización reutilizaba el precio del catálogo después de validar el formulario. | Un precio nuevo negativo o con escala o precisión incompatible se rechaza. El valor vacío se guarda como nulo y cero sigue siendo un precio válido. La optimización valida el precio del catálogo durante `clean()` y muestra cómo corregirlo. Una prueba de alta completa verificó que un precio explícito válido guarda el plan, preserva la asociación y conserva el valor histórico del material. |
| M01–M07. Escrituras directas y catálogo | El ORM puede omitir validaciones de negocio. Una medida infinita podía llegar al diccionario serializado para la aplicación. Los efectos de guardar un precio fuera de escala varían entre motores. | El catálogo para autocompletado omite ambos lados si alguno es inválido y omite importes inválidos. Se conserva la capacidad de seleccionar el material autorizado con medidas y precio válidos ingresados explícitamente. Estos controles corresponden a las interfaces y a los consumidores de catálogo, con escrituras directas del ORM fuera de su cobertura. |
| I02, P01–P05. Asociaciones, autorización y propiedad | CutLess y Django Admin aplicaban reglas de acceso distintas, y los planes guardaban su propio precio y medidas. | Los formularios mantienen las políticas de propietario y predefinidos. Las pruebas conservaron los planes y presupuestos asociados y comprobaron que una entrada inválida no causa escrituras parciales. |

Los cambios se aplican al guardar mediante los formularios. Para un valor histórico fuera del rango, la edición de otros campos permite conservarlo con un mensaje junto al control. El cambio deliberado de ese valor exige uno válido. Una medida no finita requiere corrección antes de guardar. Los registros pueden corregirse individualmente y conservan sus asociaciones. Omitir el precio siempre que el material tenga un precio inválido devuelve un error y permite suministrar un valor válido como alternativa.

## Autorización verificada

| Actor | Edición pública | Django Admin |
| --- | --- | --- |
| Propietario ordinario con permiso de Materiales | Edita su material. Un predefinido devuelve 403 y un personal ajeno queda fuera de su edición. | Requiere acceso de staff, con redirección al inicio de sesión de Admin para quien carece de él. |
| Administrador CutLess sin permisos Django de Material | Edita los propios y predefinidos. Las ediciones de personales ajenos no escriben. | Las operaciones de Material se deniegan. |
| Staff con permiso de lectura | Según los permisos públicos de su perfil. | Puede consultar los propios y predefinidos. El POST de edición devuelve 403. |
| Staff con permiso de alta y cambio | Según los permisos públicos de su perfil. | Puede crear y editar dentro del queryset de propios y predefinidos. Se verificó redirección sin escritura al intentar editar un personal ajeno. |
| Superusuario | La regla pública sigue exigiendo propiedad en materiales personales. | Mantiene gestión global y puede crear predefinidos. |

El panel propio de administración de cuentas permanece separado de Django Admin. Al asociar un material a una optimización, se verificó que el filtro acepte materiales propios y predefinidos, y rechace personales ajenos. Cargar una plantilla usa la misma autorización de costos que `TableroForm` para preparar el catálogo y conserva su proyección de nombre y precio, de modo que elegir material no sustituye las medidas de la plantilla.

Quedan por decidir las invariantes de propiedad de Django Admin para un predefinido con propietario o un personal sin propietario. El permiso explícito de cambio de Django sigue incluyendo predefinidos para staff. La auditoría documentó esa diferencia y no estableció una regla que obligue a cambiarla. El borrado de Materiales permanece fuera del cambio.

## Archivos

| Archivo | Cambio |
| --- | --- |
| [cut/cutless/admin.py](../cut/cutless/admin.py) | Conecta el formulario de Materiales con Django Admin y limita la escritura a los campos modificados al editar. |
| [cut/cutless/forms/materials.py](../cut/cutless/forms/materials.py) | Comparte los controles decimales, distingue cm de unidad elegida y conserva los valores originales de una edición. |
| [cut/cutless/materiales.py](../cut/cutless/materiales.py) | Define las reglas compartidas de rango y precio y reutiliza los validadores de precisión del campo del modelo. |
| [cut/cutless/forms/optimization.py](../cut/cutless/forms/optimization.py) | Valida el precio que proviene del catálogo antes de entrar en la generación del plan. |
| [cut/cutless/views/materials.py](../cut/cutless/views/materials.py) | Guarda solo los campos modificados durante la edición pública y mantiene la regla aplicable de propietario. |
| [cut/cutless/views/common.py](../cut/cutless/views/common.py) y [cut/cutless/views/plantillas.py](../cut/cutless/views/plantillas.py) | Preparan un catálogo autorizado sin autocompletar valores inválidos. |
| [cut/cutless/tests/test_num02_materiales.py](../cut/cutless/tests/test_num02_materiales.py) | Añade 17 pruebas de regresión con subcasos de alta, edición, datos históricos, relaciones, costos y permisos. |
| [README.md](../README.md) y [registro de noviembre](REGISTRO_CAMBIOS_NOVIEMBRE_2026.md) | Enlazan el informe y registran la corrección. |

## Ejecución

Python 3.13.12 y Django 5.2.19. SQLite 3.50.4 desechable y PostgreSQL 16.2 en un clúster descartable con socket Unix privado y sin puerto TCP. Para Chromium 156.0.8078.79 se usó Playwright 1.62.1 con sesión sintética, servidor Django de bucle local y bloqueo de solicitudes fuera de ese origen. Node.js 24.22.1 ejecutó las pruebas de la aplicación y el Worker simulado.

| Ejecución final | Aprobadas | Fallidas | Omitidas | Errores |
| --- | ---: | ---: | ---: | ---: |
| Django dirigido, SQLite, incluidos NUM-01 y el catálogo JSON | 37 | 0 | 0 | 0 |
| Django completo, SQLite | 436 | 0 | 6 | 0 |
| Django completo, PostgreSQL 16.2 | 442 | 0 | 0 | 0 |
| Node.js, incluido el Worker simulado | 73 | 0 | 0 | 0 |
| Chromium en `es-CL`, alta y edición, con y sin JavaScript | 48 | 0 | 0 | 0 |
| Comprobaciones de persistencia tras Chromium en SQLite | 48 | 0 | 0 | 0 |

Las seis omisiones de SQLite corresponden a pruebas que requieren `select_for_update`. Se ejecutaron con PostgreSQL y aprobaron. `makemigrations --check --dry-run` devolvió `No changes detected` y `git diff --check` pasó.

El primer intento de las suites completas detectó un error de tipo en una prueba preexistente de edición en metros. El cambio inicial devolvía texto también para valores decimales ordinarios. Se conservó el tipo inicial para esos casos, con conversión a texto solo al desambiguar tres decimales o representar un valor inicial que aparezca en notación exponencial. Las pruebas finales se repitieron con ese ajuste.

Para reproducir, usar las dependencias ya fijadas en el proyecto y ejecutar desde la raíz del repositorio. Configurar `CUTLESS_ENV=development`, una `CUTLESS_SECRET_KEY` aleatoria local y un `CUTLESS_MEDIA_ROOT` temporal. Para SQLite, usar `CUTLESS_DB_ENGINE=sqlite` y `CUTLESS_DB_PATH` temporal. Para PostgreSQL, iniciar un clúster local descartable sin escucha TCP y configurar `CUTLESS_DB_ENGINE=postgresql`, `CUTLESS_DB_HOST` con el directorio privado del socket, `CUTLESS_DB_PORT`, usuario y base sintéticos. Utilizar un entorno limpio sin conexiones externas configuradas.

```sh
python -B cut/manage.py test --noinput -v 2 cutless.tests.test_num02_materiales cutless.tests.test_num01_validacion cutless.tests.test_materiales_json
python -B cut/manage.py test --noinput -v 2
python -B cut/manage.py makemigrations --check --dry-run
node --test $(git ls-files 'cut/*.test.cjs' 'cloudflare/*.test.mjs')
git diff --check
```

El arnés de Chromium y los registros de esta ejecución se conservan por separado en el entorno de trabajo, en `/workspace/shared/cutless-num02-correccion`. Su lanzador se ejecuta con `bash ejecutar.sh sqlite navegador` y verifica las filas en SQLite después de los POST. Se probaron altas y ediciones, teclado decimal, las dos agrupaciones ambiguas, rechazo de rango y conservación exacta de una edición histórica. La verificación de teclado en navegador se limitó a Chromium en `es-CL`.

Para reproducir los recorridos desde un clon, preparar una SQLite desechable con `python -B cut/manage.py migrate`, crear un superusuario local con `python -B cut/manage.py createsuperuser` y arrancar `python -B cut/manage.py runserver 127.0.0.1:8000`. En Chromium configurado en `es-CL`, iniciar sesión y repetir con JavaScript habilitado y deshabilitado:

1. Abrir `/cutless/materiales/crear/` y `/admin/cutless/material/add/`. Usar nombres distintos, ancho 122 cm, alto 244 cm y escribir por teclado `12,5` como precio. Repetir en edición con `12.5`. Ambos valores deben guardar `12.50`.
2. Repetir con `1.000` y `1,000` como precio, y con un lado de 301 cm. Confirmar el rechazo, la conservación de campos y la ausencia de escrituras.
3. Para comprobar persistencia, abrir `python -B cut/manage.py shell` y consultar `Material.objects.values_list('nombre', 'ancho', 'alto', 'precio')` desde `cutless.models`. Usar solo datos de prueba.

## Migraciones y límites

La estructura de datos permite conservar las medidas históricas con la precisión existente, y el campo de precio mantiene su definición. La corrección usa formularios y lecturas de catálogo, por lo que no requiere migración ni dependencias nuevas. Una futura restricción de esquema o la validación de importadores requiere analizar los datos históricos y todos los escritores directos del ORM. La frecuencia y el estado de datos históricos en producción quedan sin verificar. Se ensayó la generación de un plan sintético con precio explícito tras rechazar la recuperación de un precio inválido del catálogo. Los resultados publicados o los presupuestos de producción quedan fuera de estas pruebas.
