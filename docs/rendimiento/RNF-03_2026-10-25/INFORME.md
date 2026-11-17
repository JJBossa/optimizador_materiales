# RNF-03 — Prueba de rendimiento local

**Resultado: APROBADO en el entorno local evaluado.** Las 20 de 20 ejecuciones terminaron dentro de 10 segundos; se exigían al menos 19.

Fecha: 25/10/2026 (America/Santiago). Revisión del software: `f094d55609699596b576872e4bf8c1cd37a1550f`.

## Resumen

| Medición | Promedio | Máximo | Mínimo | Mediana |
| --- | ---: | ---: | ---: | ---: |
| Respuesta percibida | 1,0505 s | 3,0325 s | 0,7905 s | 0,8176 s |
| Solicitud completa en Django | 0,5255 s | 0,6276 s | 0,4965 s | 0,5140 s |
| Algoritmo de distribución | 1,3280 ms | 2,3081 ms | 1,1366 ms | 1,2145 ms |

La aprobación se calcula con el tiempo percibido sin redondear. No se descarta la primera ejecución ni las dos muestras más lentas. El porcentaje de cumplimiento observado es **100 %**. Esto describe esta muestra; no es un intervalo estadístico de confianza ni una garantía para otro equipo.

## Configuración

| Parámetro | Valor |
| --- | --- |
| Tablero | OSB, 122 × 244 cm |
| Pieza A | 30 × 40 cm; 20 unidades |
| Pieza B | 40 × 50 cm; 20 unidades |
| Pieza C | 20 × 30 cm; 10 unidades |
| Total | 50 unidades de 3 tipos de pieza |
| Sierra | 3 mm (0,3 cm internos) |
| Rotación | Activada |
| Repeticiones | 20 consecutivas, un usuario, sin concurrencia simulada |
| Datos opcionales | Sin nombre de trabajo, costos, cliente ni proyecto |
| Botón utilizado | Generar plan de corte (acción equivalente a Optimizar) |

## Entorno

- Procesador: AMD Ryzen 7 9700X, 8 núcleos y 16 hilos.
- RAM reportada por Windows: 15,1143 GiB.
- Sistema: Windows-10-10.0.19045-SP0.
- Python: 3.13.12.
- Dependencias instaladas: Django 5.2.8, matplotlib 3.9.2, reportlab 4.2.5, Pillow 11.0.0.
- Django local con DEBUG activado y SQLite. Servidor de desarrollo, un proceso, sin reinicio automático durante la serie.
- Navegador integrado basado en Chromium 156; viewport 1280 × 720, escala de píxel 1. El documento informó estado visible en las 20 muestras.
- SQLite, cuenta y archivos de prueba independientes. La base de datos y las optimizaciones personales de la instalación habitual no se usaron.

## Método y límites de medición

1. Se inició el servidor aislado y se abrió una sesión normal de prueba.
2. En cada repetición se eligió OSB y se completaron los mismos tres tipos y cantidades. La preparación del formulario queda fuera del cronómetro.
3. Una escucha en captura del clic real del botón registra `performance.timeOrigin + performance.now()` antes de enviar el formulario.
4. La nueva página registra el final tras completar la carga, las fuentes y la decodificación de imágenes visibles, finalizar la animación inicial del panel y esperar dos `requestAnimationFrame`. Es un punto final conservador de disponibilidad visual, no solo el primer texto que aparece.
5. En paralelo, `time.perf_counter()` mide la solicitud completa de Django y cada llamada al algoritmo de empaquetado. No se sustituyó el flujo por una petición de cliente de pruebas ni por una llamada aislada al algoritmo.
6. El tiempo de Django incluye validación, cálculo, gráficos, PDF, escritura de resultados y renderizado HTML. El percibido incluye además navegación y disponibilidad visual en el navegador. El tiempo del algoritmo es un subconjunto y no se suma de nuevo.
7. Se volvió al inicio con Preparar otro corte y se repitió 20 veces. No hubo optimización previa de calentamiento; la primera está incluida. Los recursos del navegador ya podían estar en caché tras el login y formulario, y no se vació la caché entre repeticiones.
8. El arranque de Django, el login, la escritura de parámetros y las pausas del operador entre repeticiones quedan fuera. Los intervalos entre repeticiones no son constantes porque existe automatización de interfaz.

El equipo podía ejecutar otros procesos. Esta es una prueba de respuesta local, no una prueba de carga, arranque en frío, concurrencia o rendimiento en Render. La interfaz utiliza sus recursos CSS/JS y fuentes habituales, incluidos los externos. No se desactivaron esos recursos para acelerar el resultado.

## Registro de las 20 ejecuciones

| Ejecución | Algoritmo (ms) | Django (s) | Hasta resultado visible (s) | Cumple ≤ 10 s |
| ---: | ---: | ---: | ---: | :---: |
| 1 | 1,1965 | 0,6275 | 1,0043 | Sí |
| 2 | 1,2239 | 0,5139 | 0,8168 | Sí |
| 3 | 1,1624 | 0,5212 | 0,8184 | Sí |
| 4 | 1,1567 | 0,5094 | 0,7986 | Sí |
| 5 | 1,6763 | 0,5095 | 0,7988 | Sí |
| 6 | 1,2964 | 0,5163 | 0,8323 | Sí |
| 7 | 1,5347 | 0,5047 | 0,8036 | Sí |
| 8 | 1,2862 | 0,5170 | 0,8055 | Sí |
| 9 | 1,1646 | 0,5058 | 0,8043 | Sí |
| 10 | 1,2064 | 0,5124 | 0,7990 | Sí |
| 11 | 1,2093 | 0,6276 | 0,9360 | Sí |
| 12 | 1,1594 | 0,5501 | 0,8610 | Sí |
| 13 | 1,6858 | 0,5339 | 0,8305 | Sí |
| 14 | 1,2197 | 0,5339 | 0,8307 | Sí |
| 15 | 1,2435 | 0,5141 | 0,8198 | Sí |
| 16 | 1,1887 | 0,5149 | 0,7990 | Sí |
| 17 | 2,3081 | 0,5047 | 0,7977 | Sí |
| 18 | 1,3081 | 0,4994 | 0,7905 | Sí |
| 19 | 1,1366 | 0,4975 | 3,0310 | Sí |
| 20 | 1,1959 | 0,4965 | 3,0325 | Sí |

## Integridad de la prueba e incidencias

- Las 20 respuestas fueron HTTP 200 y coincidieron con las dimensiones, las 50 unidades, la sierra de 3 mm y la rotación solicitadas.
- En cada ejecución se colocaron las 50 piezas, sin omisiones, en 3 tableros. Aprovechamiento global: 78,38 %. Se verificó una llamada al algoritmo por ejecución.
- Auditoría de la base aislada: 20 optimizaciones y 60 tableros. Archivos generados: 20 PDF y 80 PNG (incluidas vistas previas).
- Las muestras 19 y 20 registraron 3,0310 s y 3,0325 s en el navegador, frente a aproximadamente 0,5 s en Django. No se atribuye una causa concreta a la variación del navegador sin un perfil adicional.
- El controlador de automatización agotó su espera del marcador en esas dos muestras; la instrumentación de la página registró sus tiempos de forma independiente. Se recuperaron los registros existentes sin reenviar formularios, excluir muestras ni sustituir tiempos.

## Evidencias y reproducción

- [Tiempos completos en CSV](tiempos.csv).
- [Registros originales y metadatos en JSON](resultados.json).
- [Estadísticas en JSON](resumen.json).
- [Captura de la ejecución 20](evidencia_resultado.png).
- Instrumentación: [tools/performance_rnf03.py](../../../tools/performance_rnf03.py).
- SHA-256 del script ejecutado en esta campaña: `2cae535c4a34669110c63f4e132934b387967091955e7793920f8c50fc1c3af5`.
- La versión publicada solicita la contraseña del usuario desechable en la terminal y no incluye credenciales. Su SHA-256 es `481D5D51D50824CA88F21CE80FB3ED0FFC561E84EF484A317F69D1EDEC0A1860`.

Desde la raíz del repositorio, usar una carpeta de trabajo nueva para cada campaña:

```powershell
python tools/performance_rnf03.py --work-dir "$env:TEMP\CutLess-RNF03-nueva" --output "docs\rendimiento\RNF-03_nueva" --port 8106
```

Abrir `http://127.0.0.1:8106/cutless/`, entrar con el usuario desechable `rnf03` y proporcionar la contraseña cuando el script la solicite en la terminal. Repetir los parámetros y clics del procedimiento. La instrumentación escribe automáticamente JSON y CSV después de cada muestra. Se rechaza reutilizar una carpeta que ya contiene la SQLite de otra campaña. Cerrar ese servidor al terminar.

## Conclusión

El RNF-03 queda aprobado en este equipo local: **20/20 ejecuciones ≤ 10 s**, con una media percibida de **1,0505 s** y un máximo de **3,0325 s**. No se requirieron cambios al algoritmo para cumplir este caso. La evaluación en producción será una campaña separada cuando exista el despliegue.

La campaña se ejecutó localmente; este informe no representa una medición en producción. La instrumentación es una utilidad separada y no se carga al ejecutar normalmente CutLess.
