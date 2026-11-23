# VIS-06 · Uniformidad en los campos de costos

En un formulario nuevo, «Precio por tablero» y «Mano de obra» empiezan vacíos y muestran `0` como placeholder. El precio se completa al seleccionar un material del catálogo. Al editar se muestran los importes guardados, incluido un cero real. Si se guarda con Mano de obra vacía, la regla existente usa `0` en el cálculo y al guardar.

El estilo general de `.form-control::placeholder` mostraba el cero de Precio por tablero en cursiva y `initial=0` hacía que el de Mano de obra fuera un valor real al abrir el alta. La hoja compartida por creación y edición hace que los placeholders de estos dos campos hereden la tipografía del valor. El color atenuado indica qué campos están vacíos. [Hoja compartida](../cut/cutless/static/cutless/css/index.css) · [Definición de los campos](../cut/cutless/forms/optimization.py)

## Comparación en Chromium 156

| Entorno | Antes | Después |
| --- | --- | --- |
| 390 px · claro | [Cero en cursiva](evidencia/vis06/antes-390.png) | [Tipografía uniforme](evidencia/vis06/despues-390.png) |
| 1280 px · oscuro | [Cero en cursiva](evidencia/vis06/antes-1280.png) | [Tipografía uniforme](evidencia/vis06/despues-1280.png) |

Se verificaron ambos anchos en temas claro y oscuro, tanto en alta como en edición de un plan sin precio y con mano de obra guardada en `0`. El placeholder y el valor coinciden en familia, tamaño, peso, estilo y alineación. El color del placeholder conserva una relación de contraste de 5,50:1 en claro y 5,12:1 en oscuro frente al fondo del campo. La selección de materiales sigue cargando `10000`, `0` o un valor vacío según el precio del catálogo. El recorrido de importes comprueba también la edición con importes guardados y la conservación del texto escrito tras un error de validación. [Recorrido de importes](../cut/cutless/tests/browser/importes-formularios.cjs)

Pasaron 48 regresiones dirigidas de importes, materiales, optimización y permisos en SQLite. En alta y edición, guardar una optimización de un tablero con precio `12500.50` y Mano de obra vacía dio un total de `12500.50`. `makemigrations --check --dry-run` y `git diff --check` pasaron. [Pruebas de cálculo y guardado](../cut/cutless/tests/test_importes_formularios.py)
