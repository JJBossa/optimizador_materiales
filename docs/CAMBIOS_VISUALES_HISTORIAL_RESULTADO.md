# Revisión visual de historial y resultado

Estado: bloque autorizado por el usuario para publicación en GitHub. Cabecera del historial revisada y aprobada visualmente.

## Historial

Tras la revisión de la cabecera, se elimina su línea inferior, se agrupan las acciones a la derecha y se da al botón de ayuda fondo neutro y borde visible. En móvil las acciones se colocan debajo del título y descripción. El ajuste se limita al historial; se actualiza la versión de caché de su hoja de estilos.

Conserva su nombre, filtros, orden, favoritos y acciones existentes. Las tarjetas incorporan Ver resultado como acceso visible al plan, por encima de editar y duplicar. Se aclaran fechas, selección, filtros y acciones. El estado vacío considera también el filtro de favoritos para no sugerir que no existen registros cuando no hay coincidencias.

Filtros y tarjetas usan superficies de la paleta actual, texto general de 1.125rem y controles principales de mínimo 48 px. Los checkboxes usan 24 px para evitar deformaciones. Los selects cambian de fondo al pasar el cursor. Las acciones permiten envolver en pantallas estrechas.

## Resultado

El resumen usa tarjetas neutras y cifras destacadas, reservando colores de estado para los indicadores por tablero. Los encabezados, botones, tablas y descargas siguen la tipografía del inicio. Se reparan los colores de las barras que dependían de variables antiguas. La tabla permite desplazamiento horizontal en móvil.

Distribución de las piezas explica cómo ampliar y descargar imágenes; las descargas se agrupan bajo Guardar o imprimir el resultado. Imprimir avisa que abre otra pestaña. Las imágenes, datos, cálculos y rutas se conservan.

## Archivos y alcance

Se modifican historial.html y resultado.html y se añade history-result-refinement.css. Las reglas se limitan a review-page, history-page y result-page para no cambiar otras listas que comparten historial.css. No se modifican modelos, algoritmo, persistencia ni permisos.

## Validación

Las dos plantillas compilan. Pasaron las 86 pruebas de cutless.tests y usuarios.tests con base de pruebas y archivos temporales; Django check no informó problemas. El ajuste posterior de cabecera se revisó con el usuario y pasó git diff --check. La revisión exhaustiva de móvil, oscuro, menús y gráficos ampliados sigue pendiente. No se ha realizado una auditoría completa de accesibilidad.

Los cambios locales previos de la base de datos, PDFs y CAMBIOS_AREAS.md quedan fuera de este bloque.

## Redondeo del fondo al pasar el cursor en el historial

El filtro «Solo favoritos» y el selector junto al nombre y al código de cada optimización conservaban un fondo rectangular al pasar el cursor. Ambos contenedores usan `.form-check.history-selection` dentro de `body.history-page`.

La regla `body.history-page .form-check.history-selection:hover` aplica `border-radius: 12px` dentro de `@media (hover: hover)`. El radio aproxima el estilo de la navegación lateral. El fondo conserva `var(--cl-bg-surface)` en claro y oscuro y vuelve a ser transparente al retirar el cursor. El foco visible permanece en la casilla mediante `body.history-page .history-selection .form-check-input:focus-visible`. El ajuste deja intactos el marcado y las reglas de los demás formularios.

### Archivos modificados

- `cut/cutless/static/cutless/css/history-result-refinement.css` aplica el radio solo al hover de los dos tipos de contenedores de selección del historial.
- `cut/cutless/templates/cutless/historial.html` cambia el parámetro de caché de la hoja a `history-selection-3`.
- Este documento registra el ajuste. El [registro de noviembre](REGISTRO_CAMBIOS_NOVIEMBRE_2026.md) y el [índice del README](../README.md#documentación-de-cambios) lo vinculan con los cambios recientes.

### Refinamiento del espaciado interior

Tras revisar la versión redondeada en el historial, se detectó que el nombre y el código del trabajo quedaban demasiado cerca del borde del fondo resaltado, especialmente con nombres largos. Se mantiene el radio de 12 px y la paleta actual, pero se incorpora `padding: 8px 14px` de manera permanente en `body.history-page .form-check.history-selection`, de forma que no cambie el tamaño del selector al entrar o salir del hover. Se limita la anchura al contenedor y se permite envolver nombres largos sin invadir las acciones contiguas. El ajuste también aporta separación al filtro «Solo favoritos».

Se actualiza la versión del CSS en `historial.html` a `history-selection-4` para evitar que el navegador conserve el estilo anterior. No se cambian la lógica de selección, los datos, los modelos ni las migraciones. La verificación visual en dispositivos y temas debe completarse antes de fusionar este refinamiento.

### Validación del redondeo

- Chromium, con el HTML renderizado por Django en una base SQLite temporal, en temas claro y oscuro. Se revisaron un escritorio a 1440 px, una ventana de 360 px con ratón y un móvil táctil emulado de 360 px. En los dos controles se comprobó el radio de 12 px, la desaparición del fondo al salir con el cursor, la ausencia de resaltado táctil persistente y el foco visible con teclado. También se comprobaron el marcado, el filtro de favoritos, la selección múltiple y el fondo de los controles fuera del historial.
- Pasaron 39 pruebas Django relacionadas con historial, identificadores, nombres y resultado en PostgreSQL aislado, y las 67 pruebas JavaScript de la suite. `git diff --check` se completó sin errores.
