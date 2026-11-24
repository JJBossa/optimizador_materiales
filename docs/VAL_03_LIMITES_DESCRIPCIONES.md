# VAL-03 · Límite de descripciones y notas

La rama parte de `826bf42a33e9116240cc6f241e83e26265a09d6c`, que incorpora UX-06. Antes de VAL-03, los formularios admitían descripciones y notas sin máximo. Las rutas de alta y edición ahora admiten hasta 150 unidades UTF-16 en estos cinco campos opcionales.

| Campo | Formularios y rutas |
| --- | --- |
| `Material.descripcion` | `MaterialBaseForm` en la biblioteca y Django Admin. |
| `Proyecto.descripcion` | Creación y edición de proyectos. |
| `Plantilla.descripcion` | Creación, edición propia y copia de plantilla predefinida, incluida la creación desde una optimización. |
| `Cliente.notas` | Creación y edición de fichas. |
| `Presupuesto.notas` | Creación y edición de borradores, incluida la emisión de un borrador. |

La auditoría de formularios, vistas y modelos encontró estos cinco campos editables de descripción o notas. Las descripciones fijas de materiales de catálogo proceden de un comando interno. Los rótulos calculados para comparar materiales proceden de los datos de la optimización. Ambos flujos quedan fuera del límite de entrada. También quedan fuera nombres y piezas, credenciales, correo y otros datos de contacto, direcciones y sus referencias, búsquedas, identificadores, datos técnicos y el contenido histórico de presupuestos emitidos.

## Longitud, saltos y datos históricos

- `DescripcionLimitadaField` reutiliza `LongitudHTMLValidator`. Un emoji como 🪵 ocupa dos unidades y 75 de esos emojis alcanzan el máximo. El criterio coincide con `maxlength` del navegador y la propiedad `length` de JavaScript.
- Antes de contar, CRLF y CR se representan como LF, igual que en el `textarea`. Se cuentan los espacios que el usuario introdujo. Para texto nuevo o modificado que cumple el límite, el guardado conserva el recorte exterior que ya aplicaba Django y persiste los saltos internos como LF.
- Para determinar si se conserva un texto se compara lo enviado con el valor de la instancia autorizada en la base de datos. Se aceptan diferencias de representación de saltos. Si el campo no llega en un POST de edición, se mantiene el valor. Una cadena vacía enviada explícitamente permite borrar el texto. Se guarda el original literal para un campo intacto, incluidos espacios y saltos. `changed_data` mantiene el campo fuera de las actualizaciones de Material si se conserva.
- Una copia de plantilla exige el límite vigente aunque muestre el texto completo del original. Usar una plantilla histórica técnicamente válida para una optimización sigue permitido. En presupuestos emitidos permanece el formulario específico de estado y las exportaciones siguen recibiendo las notas originales.

## Interfaz

Las altas y los valores visibles dentro del límite llevan `maxlength="150"`. Si un histórico, una copia o una entrada rechazada supera el límite, el widget omite ese atributo para mostrar todo el texto y permitir una reducción progresiva, también sin JavaScript. Django decide si puede guardarse. El aviso histórico explica la excepción, el servidor conserva lo escrito tras un error y el campo queda asociado a su ayuda y a sus errores.

El contador se carga desde el widget y se actualiza al recibir el evento `input`. Muestra el total y, si corresponde, una indicación textual de exceso. Los lectores de pantalla conservan la ayuda y los errores del servidor sin anuncios en cada pulsación.

## Archivos

- `forms/descripciones.py` define el campo, el widget y la conservación de ediciones.
- `forms/materials.py`, `projects.py`, `plantillas.py`, `clients.py` y `budgets.py` conectan las reglas a los formularios.
- Los diez HTML de alta y edición cargan el contador y reutilizan `includes/texto_limitado.html` para el campo, la ayuda y los errores. `static/cutless/js/contador-texto.js` implementa el conteo.
- `tests/test_limites_descripciones.py` comprueba reglas, rutas y datos históricos. `tests/browser/fixtures-limites-descripciones.py` y `limites-descripciones.cjs` preparan y verifican los recorridos en navegador. El recorrido existente `direcciones-clientes.cjs` espera el buscador visible de UX-06 antes de escribir.

## Verificación local

Desde `cut/`, con `CUTLESS_ENV=development` y las variables de una base local aislada, se ejecutaron `python manage.py test --noinput -v 2`, `python manage.py check` y `python manage.py makemigrations --check --dry-run`. Desde la raíz se ejecutaron `git ls-files '*.test.cjs' '*.test.mjs' -z | xargs -0 node --test` y `git diff --check`.

| Entorno | Resultado |
| --- | --- |
| Django 5.2.19 con PostgreSQL 16.16 | 545 aprobadas, 0 fallidas y 0 omitidas. |
| Django 5.2.19 con SQLite 3.50.4 | 537 aprobadas, 0 fallidas y 8 omitidas por requerir `SELECT FOR UPDATE`. |
| JavaScript con Node 24.22.1 | 79 aprobadas, 0 fallidas y 0 omitidas. |
| Chromium 156 con Playwright 1.62.1 | VAL-03 aprobado a 320, 390, 768 y 1440 px, con temas claro y oscuro y una ejecución sin JavaScript. Se editaron los cinco tipos de registros y se probó pegado, límite nativo, POST manipulado, error junto al campo y recuperación. |
| Comprobaciones de Django y diff | Sin incidencias, cambios de esquema ni errores de espacios. |

Las suites completas de Django se verificaron en los logs recuperados. Tras recuperar la rama se repitieron las seis pruebas específicas de VAL-03 en cada motor, todas aprobadas, además de las comprobaciones de Django, la suite de JavaScript y los recorridos de Chromium de VAL-03 y direcciones.

Para reproducir el navegador, migrar una SQLite local vacía, cargar `fixtures-limites-descripciones.py` en `python cut/manage.py shell` y servir en loopback con `runserver --noreload --nothreading`. Configurar `CUTLESS_TEST_FIXTURE`, `CUTLESS_TEST_ORIGIN`, `CUTLESS_TEST_BOOTSTRAP` y, si se usa Chromium del sistema, `CUTLESS_TEST_CHROMIUM`. Ejecutar `node cut/cutless/tests/browser/limites-descripciones.cjs`. Con `CUTLESS_TEST_EVIDENCE` se guardaron fuera de Git las capturas sintéticas `val03-movil.png` y `val03-escritorio.png`.

En dos ejecuciones preliminares de la regresión de direcciones, Playwright encontró el selector nativo justo antes de que el buscador mejorado lo ocultara tras un POST. La misma prueba aprobó en una SQLite independiente de `upstream/main`, donde el fallo no se reprodujo. Se cargó el contador con `defer` y se precisó el localizador de la prueba para esperar el combobox antes de escribir. En la ejecución de cierre aprobaron ambos recorridos, con ocho combinaciones de ancho y modo en direcciones. Los logs recuperados también registraron aprobadas las regresiones de nombres y contacto.

Firefox y WebKit quedaron sin ejecutar porque las descargas de Playwright devolvieron HTTP 403. Los tamaños móviles se verificaron en Chromium con viewport reducido. Safari en iPhone queda sin verificar.
