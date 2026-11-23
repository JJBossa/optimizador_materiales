# VIS-06 · Uniformidad en los campos de costos

El cero de «Precio por tablero» es un placeholder. En un formulario nuevo, el valor del campo es vacío y el catálogo puede completarlo al seleccionar un material. «Mano de obra» empieza con un valor real de `0` gracias a `initial=0`.

El estilo general de `.form-control::placeholder` mostraba el primer cero en cursiva. La hoja compartida por creación y edición hace que solo los placeholders de estos dos campos hereden la tipografía del valor. El color atenuado sigue indicando qué campos están vacíos. [Hoja compartida](../cut/cutless/static/cutless/css/index.css) · [Definición de los campos](../cut/cutless/forms/optimization.py)

## Comparación en Chromium 156

| Entorno | Antes | Después |
| --- | --- | --- |
| 390 px · claro | [Cero en cursiva](evidencia/vis06/antes-390.png) | [Tipografía uniforme](evidencia/vis06/despues-390.png) |
| 1280 px · oscuro | [Cero en cursiva](evidencia/vis06/antes-1280.png) | [Tipografía uniforme](evidencia/vis06/despues-1280.png) |

Se verificaron ambos anchos en temas claro y oscuro, tanto en alta como en edición de un plan sin precio. El placeholder y el valor coinciden en familia, tamaño, peso, estilo y alineación. El color del placeholder conserva una relación de contraste de 5,50:1 en claro y 5,12:1 en oscuro frente al fondo del campo. El placeholder del nombre conserva su estilo. La selección de materiales sigue cargando `10000`, `0` o un valor vacío según el precio del catálogo, mientras Mano de obra conserva su valor inicial.

Pasaron 48 regresiones dirigidas de importes, materiales, optimización y permisos en SQLite. `makemigrations --check --dry-run` y `git diff --check` pasaron.
