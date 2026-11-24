# VIS-07 · Uniformidad de los badges de aprovechamiento

En «Optimizaciones del Proyecto», los porcentajes tenían un ancho que variaba según el texto. La clase `badge-aprovechamiento` les da un ancho de `5em`, limitado por el espacio de la celda, y centra el porcentaje en ambos ejes. La altura sale del interlineado, el relleno y el borde del badge existente. Los colores semánticos y la tipografía provienen de las mismas reglas que antes. [Estilos de gestión](../cut/cutless/static/cutless/css/management-refinement.css)

La clase se aplica a las cuatro tablas de gestión con el mismo badge de un decimal. [Detalle del proyecto](../cut/cutless/templates/cutless/detalle_proyecto.html) · [Selección de optimizaciones](../cut/cutless/templates/cutless/agregar_optimizaciones_proyecto.html) · [Historial del cliente](../cut/cutless/templates/cutless/historial_cliente.html) · [Detalle del presupuesto](../cut/cutless/templates/cutless/detalle_presupuesto.html)

El Historial general, el Historial de costos, Estadísticas y Resultado presentan el aprovechamiento con estilos propios. La clase se limita a los badges de consulta de las cuatro tablas de gestión mencionadas.

## Verificación en Chromium 156

| Entorno | Valores sintéticos | Medida final |
| --- | --- | --- |
| 320 y 390 px, claro y oscuro | `10,6%`, `53,6%`, `70,0%`, `100,0%` | 80 × 42 px |
| 1280 px, claro y oscuro | `10,6%`, `53,6%`, `70,0%`, `100,0%` | 80 × 42 px |

Se comprobaron 24 combinaciones de vista, ancho y tema. La prueba verifica que el texto quepa en una línea y quede centrado. Las cuatro tablas y el documento tuvieron cero desbordes horizontales. En el detalle de Proyectos, los badges antes medían entre 66,8 y 76,0 px de ancho. La comparación con la base verificó colores, borde, familia tipográfica, tamaño, peso e interlineado. «Ver resultado» abrió el plan de su fila con HTTP `200` en los seis escenarios de Proyectos. [Recorrido Chromium](../cut/cutless/tests/browser/aprovechamiento-tablas.cjs)

La suite Django con SQLite aprobó 497 casos y omitió los ocho que requieren `select_for_update`. Pasaron las 67 pruebas JavaScript de CutLess, `makemigrations --check --dry-run` y `git diff --check`.

## Repetir el recorrido

Preparar una SQLite vacía con `CUTLESS_ENV=development`, `CUTLESS_DB_ENGINE=sqlite`, `CUTLESS_DB_PATH` y `CUTLESS_TEST_FIXTURE` apuntando a archivos locales desechables. Desde la raíz del repositorio, aplicar el esquema y cargar los datos sintéticos. [Fixture](../cut/cutless/tests/browser/fixtures-aprovechamiento-tablas.py)

```bash
python cut/manage.py migrate --noinput
python cut/manage.py shell < cut/cutless/tests/browser/fixtures-aprovechamiento-tablas.py
python cut/manage.py runserver 127.0.0.1:8861 --noreload
```

Con Playwright disponible, ejecutar `node cut/cutless/tests/browser/aprovechamiento-tablas.cjs` con `CUTLESS_TEST_ORIGIN=http://127.0.0.1:8861`, la misma ruta de fixture y `CUTLESS_TEST_BOOTSTRAP` apuntando al CSS local de Bootstrap 5.3.0. `CUTLESS_TEST_CHROMIUM` permite indicar un binario local. Para comparar con la revisión anterior, servirla en otro puerto con la misma base y clave sintética e indicar su URL en `CUTLESS_TEST_BASE`. `CUTLESS_TEST_EVIDENCE` permite guardar capturas en un directorio existente.
