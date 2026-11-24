# UX-06 · Buscadores de países y prefijos

La rama parte de `476967c175675fa6ff9021c1924a318b44daf5fb`, que incorpora CLI-03. Los formularios de alta y edición de Clientes son los únicos que incluyen los dos selectores. Antes, escribir en el buscador telefónico filtraba un control aparte y obligaba a navegar hasta él. El país postal se elegía en un selector nativo sin búsqueda integrada.

## Búsqueda y selección

Ambos campos muestran las coincidencias debajo del texto introducido y permiten elegirlas mediante clic, toque o teclado. El botón junto al campo y las flechas abren el catálogo completo. La búsqueda ignora mayúsculas y tildes, y prioriza el código exacto de país sobre coincidencias parciales de nombre. El buscador telefónico también admite prefijos exactos con o sin `+`. Un prefijo compartido como `+1` lista todas sus coincidencias y deja la elección al usuario. Los países postales se obtienen de su propio catálogo y la opción vacía permite dejar una ficha sin dirección.

`selector-pais.js` toma cada etiqueta y código de las opciones renderizadas por Django y construye una lista con nodos de texto. Cada instancia conserva su propia búsqueda y toma el valor confirmado del `select`. Solo ese selector tiene `name` y participa en el envío. Se oculta al terminar la inicialización y queda disponible si JavaScript está deshabilitado o la estructura necesaria no existe. El evento `change` del selector nativo se propaga una vez si el valor confirmado cambia.

## Accesibilidad e integración con CLI-03

La etiqueta y los atributos de descripción y error se aplican al combobox visible. El listado usa `listbox` y `option` con estado de selección, conteo accesible y anuncio sin coincidencias. Las flechas desplazan la opción activa dentro de la lista. Enter confirma esa opción sin enviar el formulario. Escape cierra y restaura el valor confirmado. Tab hace lo mismo y mantiene el orden natural del foco. El listado tiene altura limitada, admite nombres largos y ocupa espacio debajo del campo sin superponer los controles vecinos.

`cliente-direccion.js` sigue siendo responsable de `ubicacion_pais` y de los controles de región y comuna. Buscar, cancelar y volver a elegir el país que ya estaba confirmado preserva la ubicación. Un cambio confirmado activa la lógica existente. El aviso de dirección histórica devuelve el foco al control visible y, sin JavaScript, el enlace original y el botón «Actualizar opciones de ubicación» siguen disponibles.

Django conserva los catálogos, los códigos y todas las reglas de CLI-03. Permite editar el contacto de una ficha con una dirección estructurada histórica intacta. Una etiqueta histórica fuera de catálogo puede mostrarse en esa ficha y Django sigue rechazando su uso en una dirección nueva o modificada. Las reglas telefónicas, los datos archivados de Presupuestos y el esquema de la base de datos siguen vigentes.

## Archivos

| Archivo o grupo | Cambio |
| --- | --- |
| `selector-pais.js` y `cliente-telefono.js` | Componente común que sustituye al filtro separado. |
| `cliente-direccion.js` | Destino del foco en el aviso de direcciones históricas. |
| `crear_cliente.html`, `editar_cliente.html` e inclusiones `cliente-telefono.html` y `cliente-direccion.html` | Carga del componente y marcado de los dos controles nativos. |
| `management-refinement.css` | Estilos del botón, los resultados y el estado vacío. |
| `selector-pais.test.cjs` y `test_contacto_clientes.py` | Búsqueda, integración de catálogos, valores tras errores y POST manipulados. |
| `contacto-clientes.cjs` y `direcciones-clientes.cjs` | Cobertura interactiva y regresiones de contacto y CLI-03. |

## Verificación local

| Comando o entorno | Resultado |
| --- | --- |
| `python manage.py test --noinput -v 2` con PostgreSQL 16.16 | 539 aprobadas, 0 fallidas, 0 omitidas. |
| `python manage.py test --noinput -v 2` con SQLite 3.50.4 | 531 aprobadas, 0 fallidas, 8 omitidas por falta de `SELECT FOR UPDATE`. |
| `git ls-files '*.test.cjs' '*.test.mjs' -z \| xargs -0 node --test` con Node 24.22.1 | 79 aprobadas, 0 fallidas, 0 omitidas. |
| Chromium 156.0.8078.79 y Playwright 1.62.1 | Ambos recorridos aprobados, 0 fallidos. Contacto y disposición de los dos selectores a 320, 390, 768 y 1440 px en temas claro y oscuro. Direcciones verificadas con y sin JavaScript en ocho combinaciones, más los flujos históricos de CLI-03. |
| `python manage.py check` y `python manage.py makemigrations --check --dry-run` | Sin incidencias ni cambios detectados en ambas bases. |
| `git diff --check` | Sin errores. |

Para reproducir los recorridos, iniciar dos SQLite desechables con los fixtures `fixtures-contacto-clientes.py` y `fixtures-direcciones-clientes.py` y servir cada una en loopback. Ejecutar `node cut/cutless/tests/browser/contacto-clientes.cjs` y `node cut/cutless/tests/browser/direcciones-clientes.cjs` con Playwright, el origen y la ruta del fixture local, y copias locales de Bootstrap. Usar `runserver --noreload --nothreading` para evitar el bloqueo de SQLite observado en CLI-03. `CUTLESS_TEST_EVIDENCE` permite guardar capturas fuera del repositorio con datos sintéticos. [Entorno y variables de navegador](CLI_03_VALIDACION_DIRECCIONES_CLIENTES.md)

Firefox y WebKit quedaron sin ejecutar porque el entorno rechazó con HTTP 403 las descargas de sus binarios. Los tamaños de pantalla móviles corresponden a Chromium de escritorio con viewport reducido. Safari en iPhone queda sin verificar.

Las evidencias de esta ejecución se guardaron fuera de Git. `ux06-telefono-movil.png` muestra la búsqueda por nombre a 390 px en tema claro y `ux06-postal-escritorio.png` muestra el país postal a 1440 px en tema oscuro.
