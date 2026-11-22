# Diagnóstico de rendimiento de Estadísticas

Medición del panel `/cutless/estadisticas/` en `perf/estadisticas-carga`, desde `upstream/main` en `baf9a5e`, que incluye el PR #11. La línea base corresponde a ese commit. La comparación posterior aplica solo la generación de gráficos HD bajo demanda. Ambas mediciones usaron datos sintéticos en PostgreSQL local.

## Cómo se midió

- PostgreSQL 16.2 desechable por socket local, Django 5.2.8 y Matplotlib 3.9.2 con backend Agg. El entorno tenía una cuota de dos CPU. Se sembraron cuentas independientes con 40, 800 y 6.000 optimizaciones sintéticas, con doce líneas de piezas por plan. La distribución por antigüedad genera series diferentes en los cuatro períodos.
- Para cada combinación de historial y período se ejecutaron tres solicitudes Django autenticadas. La primera se hizo en un proceso Python nuevo. La recarga fue inmediata y la visita posterior reutilizó el mismo proceso después de 750 ms. PostgreSQL y el caché de fuentes de Matplotlib se reutilizaron durante el experimento. La primera visita mide el primer uso de la vista en el proceso, sin incluir el arranque de Python ni el despertar de Render.
- Se midieron el tiempo completo del cliente de pruebas Django, las llamadas SQL mediante `connection.execute_wrapper`, cada función de gráfico, el tiempo dentro de `render`, el análisis y la conversión de piezas y dimensiones del Top 10 y el tamaño del cuerpo HTML. Los tiempos SQL incluyen la llamada al controlador. El tiempo de cada gráfico incluye sus consultas. Las columnas no son sumables entre sí.
- Una pasada adicional alrededor de `Figure.savefig` y `QuerySet._fetch_all` separó el guardado PNG y la materialización de filas para 6.000 planes. Esa pasada es independiente de la matriz principal.

## Línea base del servidor

Los tiempos están en milisegundos salvo el tamaño, en KiB. SQL, plantilla y HD son medianas de la recarga y la visita posterior. HTML es el cuerpo sin comprimir. La columna HD muestra tiempo dentro de sus dos generadores y el porcentaje del HTML que ocupan sus cadenas Base64.

| Historial | Período | Planes en el período | Primera / recarga / posterior (ms) | SQL (ms / consultas) | Plantilla (ms) | HTML (KiB) | HD (ms / % HTML) |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 40 | Semanal | 2 | 1.357 / 1.053 / 1.125 | 6,7 / 17 | 8,6 | 578 | 708 / 63,4 % |
| 40 | Mensual | 8 | 1.246 / 1.103 / 1.120 | 10,5 / 17 | 11,2 | 648 | 776 / 63,4 % |
| 40 | Anual | 22 | 1.322 / 1.105 / 1.147 | 8,0 / 17 | 18,3 | 712 | 749 / 63,6 % |
| 40 | Todo | 40 | 1.259 / 1.093 / 1.169 | 7,6 / 17 | 11,9 | 679 | 754 / 62,9 % |
| 800 | Semanal | 40 | 1.178 / 1.027 / 1.134 | 10,9 / 17 | 12,6 | 726 | 752 / 64,0 % |
| 800 | Mensual | 160 | 1.303 / 1.152 / 1.170 | 11,4 / 17 | 16,9 | 1.103 | 804 / 68,6 % |
| 800 | Anual | 440 | 1.353 / 1.200 / 1.139 | 13,9 / 17 | 15,0 | 970 | 814 / 67,5 % |
| 800 | Todo | 800 | 1.435 / 1.353 / 1.253 | 19,3 / 17 | 15,4 | 1.136 | 881 / 68,7 % |
| 6.000 | Semanal | 300 | 1.306 / 1.080 / 1.121 | 24,0 / 17 | 13,6 | 880 | 732 / 66,3 % |
| 6.000 | Mensual | 1.200 | 1.406 / 1.312 / 1.367 | 37,6 / 17 | 14,9 | 932 | 925 / 65,0 % |
| 6.000 | Anual | 3.300 | 1.986 / 1.690 / 2.735 | 74,6 / 17 | 16,1 | 817 | 1.446 / 65,0 % |
| 6.000 | Todo | 6.000 | 3.383 / 3.064 / 3.050 | 99,5 / 17 | 14,6 | 664 | 2.048 / 62,8 % |

### Costo de cada gráfico

Mediana caliente en «Todo el historial», en milisegundos.

| Historial | Aprovechamiento normal | Aprovechamiento HD | Desperdicio normal | Desperdicio HD |
| ---: | ---: | ---: | ---: | ---: |
| 40 | 163 | 395 | 189 | 358 |
| 800 | 201 | 454 | 190 | 427 |
| 6.000 | 399 | 1.133 | 555 | 915 |

En las 24 visitas con el proceso caliente, los cuatro gráficos concentraron entre **96,8 % y 98,4 %** del tiempo de respuesta. Solo las dos versiones HD representaron entre **63,0 % y 71,9 %**, con mediana de **68,1 %**. Las cuatro cadenas Base64 ocuparon entre **83,3 % y 90,2 %** del HTML. El tamaño PNG depende de la serie, el ancho de línea y la compresibilidad, por lo que no crece necesariamente con el número de planes.

Las 17 consultas por visita caliente incluyen cuatro pares `EXISTS` y `SELECT` de los gráficos. Cada gráfico vuelve a cargar el período completo como objetos `Optimizacion`. Para 6.000 planes son 24.000 filas materializadas entre las cuatro consultas, además del Top 10 y consultas auxiliares. La pasada adicional de 6.000 planes midió, en el mismo orden de la tabla, **106 / 112 / 288 / 126 ms** de materialización por gráfico y **186 / 830 / 198 / 941 ms** dentro de `savefig`. La materialización incluye la consulta, la recuperación de filas y la creación de objetos. Analizar las piezas y convertir las dimensiones del Top 10 tardó menos de 1 ms en las muestras calientes. La plantilla tardó entre 7,9 y 21,8 ms en esas muestras.

## Línea base en Chromium

Chromium 156 a 1440 × 960 con un servidor Django local de un solo hilo. Se usó un contexto de navegador nuevo para cada combinación. La recarga se hizo en la misma página y la visita posterior tras navegar fuera y esperar 750 ms. El servidor se reutilizó entre combinaciones. Bootstrap se sirvió desde una copia local de la versión del sitio y se bloquearon los demás recursos externos. TTFB es el tiempo al primer byte y FCP es el primer pintado de contenido, ambos desde el inicio de la navegación. La columna de carga es la mediana de `loadEventEnd` para recarga y visita posterior.

| Historial | Período | TTFB primera / recarga / posterior (ms) | FCP primera / recarga / posterior (ms) | Carga caliente (ms) |
| ---: | --- | ---: | ---: | ---: |
| 40 | Semanal | 1.756 / 1.184 / 1.425 | 2.356 / 1.588 / 1.788 | 1.687 |
| 40 | Mensual | 1.526 / 1.236 / 1.069 | 1.872 / 1.568 / 1.456 | 1.496 |
| 40 | Anual | 1.731 / 1.129 / 1.089 | 2.160 / 1.456 / 1.456 | 1.421 |
| 40 | Todo | 1.504 / 1.184 / 1.134 | 1.924 / 1.468 / 1.480 | 1.475 |
| 800 | Semanal | 1.526 / 1.083 / 1.205 | 1.860 / 1.440 / 1.508 | 1.465 |
| 800 | Mensual | 1.470 / 1.204 / 1.391 | 1.968 / 1.484 / 1.680 | 1.575 |
| 800 | Anual | 1.456 / 1.306 / 1.214 | 1.768 / 1.588 / 1.508 | 1.551 |
| 800 | Todo | 1.574 / 1.401 / 1.488 | 1.904 / 1.696 / 1.868 | 1.783 |
| 6.000 | Semanal | 1.525 / 1.326 / 1.610 | 2.012 / 1.692 / 1.956 | 1.813 |
| 6.000 | Mensual | 1.761 / 1.217 / 1.260 | 2.048 / 1.484 / 1.544 | 1.513 |
| 6.000 | Anual | 2.072 / 1.822 / 1.742 | 2.408 / 2.108 / 2.040 | 2.056 |
| 6.000 | Todo | 2.742 / 2.405 / 2.472 | 3.028 / 2.684 / 2.804 | 2.734 |

En caliente, las medianas globales fueron **1.248 ms** de TTFB, **1.525 ms** de DOM listo, **1.578 ms** de FCP y **1.567 ms** al finalizar el evento de carga. Las miniaturas ya estaban decodificadas cuando se comprobó `img.decode()`, a **1.627 ms** de mediana desde la navegación. Entre el primer byte y el primer pintado pasaron **332 ms** de mediana en las 36 visitas. Ese intervalo incluye recepción de HTML, procesamiento de recursos y renderizado. La mayor espera ocurrió antes del primer byte. El navegador recibió el cuerpo HTML íntegro en cada visita local, incluidas las dos cadenas HD para el modal.

## Causas y plan priorizado

1. **Diferir las imágenes HD hasta abrir la ampliación (A y E).** Es el primer cambio recomendado. Mantener las dos miniaturas actuales y pedir por una ruta autenticada solo el PNG HD seleccionado. El costo medido que saldría de la visita inicial fue de **708 ms a 2,05 s** según la combinación, calculado a partir de las dos medianas HD por celda. El HTML inicial perdería entre **62,8 % y 68,7 %** de sus bytes. Son estimaciones por sustracción de la línea base. La latencia del primer zoom y el tiempo de la nueva ruta deberán medirse tras implementar. Conservar tamaño del gráfico ampliado, controles, enfoque y aviso de error.
2. **Cargar una vez la serie necesaria para las miniaturas (D).** Recuperar las fechas y porcentajes ordenados y reutilizar esa proyección para ambos gráficos iniciales. Mantener separado el Top 10, que necesita otros campos. La pasada de 6.000 filas demuestra el costo de materializar objetos completos cuatro veces. La cantidad de lecturas y el tiempo de materialización después del cambio deben verificarse junto a la identidad de la serie y su orden.
3. **Medir las miniaturas restantes y, si aún retrasan las tarjetas, servirlas por separado (E y F).** Separar resumen y PNG permite pintar antes los datos básicos. Dos solicitudes adicionales también pueden competir por el mismo worker. En un servicio pequeño conviene medir cuándo se muestran las tarjetas y cuándo quedan listos ambos gráficos antes de adoptar esta opción. Mantener las dimensiones, el tema y la distribución.
4. **Evaluar caché interna acotada tras diferir HD (B).** Puede compensar accesos repetidos al mismo gráfico. Una caché por proceso se puede vaciar al reiniciar o suspender Render y cada worker tiene su propio límite de memoria. Medir tasa de aciertos, memoria y concurrencia antes de decidir. La primera etapa puede funcionar sin ella.
5. **Dejar la consolidación de agregados en segundo plano (C).** Se pueden agrupar conteo, media, máximos y mínimos en una consulta, manteniendo las reglas de conjunto vacío, el orden del Top 10 y los filtros de fecha. SQL completo consumió 6,5–104,1 ms en visitas calientes, muy por debajo de los gráficos. No se justifica cambiar índices, modelos ni migraciones con esta evidencia.

### Si se introduce caché

Autorizar cada solicitud de gráfico antes de leer la caché. Derivar el propietario de la sesión y filtrar por ese usuario. Construir la clave con el usuario, período, tipo, resolución, versión del renderizador y una huella de la serie ordenada que se va a dibujar tras aplicar la ventana de fechas. Una creación, edición, eliminación o salida de una fila del período que altere esa serie cambiará la huella. Si la serie y la presentación coinciden, el instante de la solicitud no necesita entrar en la clave. Evitar una clave basada solo en el conteo, la última fecha o un TTL.

Usar memoria local acotada por proceso. Mantener las respuestas privadas y fuera de cachés públicas. Si cambia la serie entre cargar el resumen y abrir el gráfico, pedir una actualización o identificar de forma explícita la nueva serie para evitar mezclar cifras de dos momentos. Definir límites de memoria y generación simultánea para los fallos de caché. La suspensión de un servicio de Render puede descartar esa caché, por lo que el caso sin aciertos también debe cumplir los criterios de carga.

## Verificación funcional de la línea base

- Se comprobó la respuesta con 0, 1, 40 y 6.000 planes en los cuatro períodos. Conteo, promedio, extremos, desperdicio y valores del Top 10 coincidieron con un cálculo independiente sobre las filas sintéticas de cada propietario. Se comprobó que un usuario sin permiso no accediera al panel ni exportara.
- Se modificó el aprovechamiento de un plan y se verificó el cambio de cifra y de gráfico. Al crear y eliminar otro plan se verificó el cambio de conteo. Las exportaciones PDF y Excel devolvieron sus formatos esperados en el período semanal.
- En Chromium se abrieron ambos gráficos HD, se decodificaron las imágenes, se probó el zoom al 150 %, se restableció al 100 %, se cerró el modal y se cambió el período. Las comprobaciones pasaron a 390 y 1440 px, en claro y oscuro.
- Pasaron 22 pruebas Django de análisis, permisos y exportaciones en PostgreSQL local y 6 pruebas JavaScript de interacción con diálogos. Esta etapa deja la línea base funcional. La comparación antes y después se ejecutará cuando haya una implementación para evaluar.

## Criterios para una implementación posterior

Comparar antes y después en la misma base sintética, con las mismas ventanas. Comprobar los valores de conteo, promedio, extremos, desperdicio y Top 10. Mantener los cuatro períodos, exportaciones, permiso y aislamiento por propietario. Casos mínimos incluyen vacío, una fila, historial grande, dos usuarios, creación, edición, eliminación, cambio de período y apertura de ambos gráficos con zoom. Repetir las mediciones de servidor y Chromium con las versiones nuevas y registrar por separado el primer gráfico visible y el primer zoom.

Las cifras son locales, de una sola secuencia por combinación. No estiman colas de Gunicorn, latencia de Supabase, tráfico real, compresión del proxy ni arranque en frío de Render. La visita anual de 6.000 planes tuvo dispersión visible y merece más repeticiones si ese escenario guía la decisión.

## Implementación de la primera mejora

La carga inicial conserva el resumen, el Top 10, los períodos y las dos miniaturas Base64 del panel. Antes generaba dos gráficos HD adicionales e incluía sus cadenas Base64 en un bloque JavaScript, aunque nadie abriera el modal. Ahora, el modal solicita un PNG mediante `GET /cutless/estadisticas/grafico-hd/?tipo=…&periodo=…`. El endpoint reutiliza el renderizador HD de 200 DPI y devuelve sus bytes PNG. Conserva la autenticación y el permiso de Estadísticas, valida ambos parámetros y deriva el propietario de la sesión. Las respuestas de la ruta de imágenes usan `Cache-Control: private, no-store`. Los cálculos y consultas de las miniaturas, el resumen y las exportaciones siguen usando su lógica previa.

El modal se abre con un estado de carga en texto y puede cerrarse mientras espera. El navegador retiene como máximo una solicitud y una imagen por tipo en la página actual. Una reapertura reutiliza la solicitud pendiente o la imagen ya decodificada. Una respuesta tardía de otra apertura no reemplaza el contenido activo. Si falla el transporte, la generación o la decodificación, el modal ofrece «Reintentar». El período está asociado al documento actual y su cambio recarga la página. No hay caché persistente ni almacenamiento externo.

| Archivo | Cambio |
| --- | --- |
| `cut/cutless/views/analytics.py` | Se extrae el filtro de propietario y período para que página y PNG lo compartan. La página genera solo miniaturas. La ruta HD sirve un PNG o devuelve un error controlado. |
| `cut/cutless/urls.py` | Se registra la ruta HD con la misma autorización de Estadísticas. |
| `cut/cutless/templates/cutless/estadisticas.html` | Se retiran las cadenas HD del HTML. El modal existente solicita, reutiliza y presenta la imagen seleccionada. |
| `cut/cutless/tests/test_estadisticas_hd.py` | Se comprueban miniaturas, datos del resumen, calidad PNG, autorización, aislamiento, validación y errores. |

### Servidor después del cambio

Se repitieron las 36 solicitudes de la línea base sobre la misma base sintética. Los tiempos están en ms. «Total posterior» muestra la primera visita, recarga y visita posterior de la implementación. «Gráficos calientes» y «Total caliente» son medianas de recarga y visita posterior. Cada tiempo HD corresponde a una solicitud aislada después de medir la página, en orden aprovechamiento y desperdicio.

| Historial | Período | Total posterior (ms) | Total caliente antes → después (ms) | Gráficos calientes antes → después (ms) | HTML antes → después (KiB) | HD solicitado A / D (ms) |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 40 | Semanal | 557 / 408 / 368 | 1.089 → 388 | 1.070 → 370 | 578 → 214 | 564 / 498 |
| 40 | Mensual | 425 / 316 / 324 | 1.111 → 320 | 1.089 → 298 | 648 → 239 | 459 / 457 |
| 40 | Anual | 423 / 314 / 327 | 1.126 → 321 | 1.096 → 299 | 712 → 261 | 388 / 378 |
| 40 | Todo | 517 / 399 / 389 | 1.131 → 394 | 1.106 → 367 | 679 → 254 | 475 / 430 |
| 800 | Semanal | 467 / 343 / 333 | 1.081 → 338 | 1.054 → 317 | 726 → 263 | 408 / 413 |
| 800 | Mensual | 431 / 327 / 352 | 1.161 → 340 | 1.131 → 315 | 1.103 → 349 | 488 / 421 |
| 800 | Anual | 478 / 387 / 400 | 1.170 → 394 | 1.138 → 367 | 970 → 317 | 499 / 485 |
| 800 | Todo | 500 / 435 / 465 | 1.303 → 450 | 1.272 → 427 | 1.136 → 358 | 452 / 431 |
| 6.000 | Semanal | 495 / 376 / 378 | 1.100 → 377 | 1.068 → 347 | 880 → 298 | 465 / 468 |
| 6.000 | Mensual | 485 / 464 / 397 | 1.339 → 430 | 1.304 → 400 | 932 → 328 | 489 / 451 |
| 6.000 | Anual | 726 / 672 / 580 | 2.212 → 626 | 2.161 → 590 | 817 → 288 | 812 / 581 |
| 6.000 | Todo | 877 / 838 / 776 | 3.057 → 807 | 3.001 → 768 | 664 → 249 | 975 / 861 |

En las 24 visitas con proceso caliente, el tiempo total mediano pasó de **1.149 a 388 ms**. La mediana de reducción por visita emparejada fue **67,8 %**. Las consultas en caliente pasaron de **17 a 13** porque la página deja de ejecutar el par de consultas de cada HD. El tiempo SQL mediano pasó de **12,7 a 9,8 ms**. Cada solicitud HD aislada hizo **5 consultas**, incluidas autenticación y perfil. Los cambios se deben a cuándo se ejecutan los generadores. En esta etapa todavía se materializa la serie por separado para cada miniatura.

### Chromium después del cambio

Se repitió la misma matriz de 36 navegaciones. TTFB y FCP son los tiempos de la primera visita, recarga y visita posterior. La última columna compara la mediana de las dos vistas calientes.

| Historial | Período | TTFB después (ms) | FCP después (ms) | FCP caliente antes → después (ms) |
| ---: | --- | ---: | ---: | ---: |
| 40 | Semanal | 851 / 350 / 350 | 1.344 / 684 / 716 | 1.688 → 700 |
| 40 | Mensual | 645 / 334 / 342 | 972 / 668 / 664 | 1.512 → 666 |
| 40 | Anual | 778 / 357 / 370 | 1.072 / 640 / 704 | 1.456 → 672 |
| 40 | Todo | 757 / 363 / 366 | 1.072 / 760 / 692 | 1.474 → 726 |
| 800 | Semanal | 644 / 337 / 331 | 972 / 604 / 624 | 1.474 → 614 |
| 800 | Mensual | 572 / 370 / 401 | 1.000 / 616 / 736 | 1.582 → 676 |
| 800 | Anual | 619 / 383 / 386 | 920 / 636 / 676 | 1.548 → 656 |
| 800 | Todo | 745 / 525 / 559 | 1.044 / 800 / 864 | 1.782 → 832 |
| 6.000 | Semanal | 663 / 408 / 385 | 1.008 / 716 / 688 | 1.824 → 702 |
| 6.000 | Mensual | 777 / 459 / 498 | 1.112 / 752 / 948 | 1.514 → 850 |
| 6.000 | Anual | 827 / 712 / 576 | 1.180 / 1.012 / 908 | 2.074 → 960 |
| 6.000 | Todo | 1.210 / 965 / 820 | 1.508 / 1.252 / 1.152 | 2.744 → 1.202 |

Las medianas globales en caliente pasaron de **1.248 a 384 ms** para TTFB, de **1.578 a 710 ms** para FCP y de **1.567 a 710 ms** para el evento de carga. Las 36 navegaciones cargaron las dos miniaturas y emitieron **cero solicitudes HD** antes de pulsar «Ampliar gráfico».

### Tiempo de ampliación

Una pasada adicional con cada versión midió desde el clic hasta que el modal estaba visible y el PNG decodificado. Se usaron eventos del navegador y `img.decode()`, sin incluir la espera de la automatización para localizar el botón. Hay una primera apertura por tipo y combinación. A es aprovechamiento y D es desperdicio.

| Historial | Período | Primera apertura antes A / D (ms) | Primera apertura después A / D (ms) |
| ---: | --- | ---: | ---: |
| 40 | Semanal | 473 / 376 | 555 / 510 |
| 40 | Mensual | 476 / 404 | 474 / 527 |
| 40 | Anual | 476 / 401 | 478 / 473 |
| 40 | Todo | 479 / 401 | 512 / 500 |
| 800 | Semanal | 482 / 383 | 557 / 505 |
| 800 | Mensual | 474 / 379 | 558 / 534 |
| 800 | Anual | 475 / 458 | 579 / 510 |
| 800 | Todo | 473 / 357 | 642 / 559 |
| 6.000 | Semanal | 472 / 338 | 554 / 532 |
| 6.000 | Mensual | 472 / 376 | 610 / 527 |
| 6.000 | Anual | 474 / 372 | 804 / 743 |
| 6.000 | Todo | 473 / 358 | 1.063 / 956 |

La mediana de la primera apertura pasó de **465 a 544 ms**. Para 6.000 planes en «Todo el historial», el gráfico quedó listo entre **0,96 y 1,06 s** después del clic. Al reabrir el gráfico ya solicitado no hubo tráfico de imagen. La imagen estuvo lista en **3 ms** de mediana y el modal terminó de abrir en **466 ms**, incluida su transición.

### Regresiones y límites de esta etapa

- Pasaron **28 pruebas Django** en PostgreSQL local y **6 pruebas JavaScript** de interacción con diálogos. La nueva suite comprueba que la vista inicial invoque solo los renderizadores normales, PNG HD equivalentes, autenticación, permiso, ámbito por propietario, método HTTP, parámetros inválidos, ausencia de datos, error y encabezados privados.
- En la misma base de datos se compararon seis combinaciones anteriores y posteriores, incluidos los tres tamaños de historial y los cuatro períodos. Coincidieron el resumen, los valores y el orden del Top 10 y los bytes de ambos PNG de miniatura y ambos PNG HD para cada combinación. Coincidieron también el texto extraído del PDF y los valores, tipos y formatos de las celdas del Excel semanal de prueba. Se volvió a comprobar historial vacío, un plan, dos propietarios, edición, creación, eliminación y restricciones de acceso.
- Chromium verificó apertura, cierre durante una petición pendiente, reapertura usando esa misma petición, zoom al 250 %, desplazamiento, restablecimiento, un fallo HTTP 503 simulado y recuperación con «Reintentar». Las cuatro combinaciones de 390 y 1440 px con temas claro y oscuro pasaron. Se comprobó que, después de cargar el PNG, volver a abrirlo no genere una solicitud adicional.
- El primer HD de cada tipo añade trabajo al servidor en el momento del clic. Si el historial cambia mientras la página permanece abierta, una primera ampliación refleja la serie disponible al solicitarla. Las reaperturas conservan el PNG de esa visita y una recarga vuelve a consultar los datos. Las pruebas locales no estiman concurrencia, latencia de red real ni arranque del servicio desplegado.
- La proyección compartida de la serie, la entrega diferida de miniaturas, la consolidación de agregados y la caché interna del servidor quedan como mejoras futuras.
