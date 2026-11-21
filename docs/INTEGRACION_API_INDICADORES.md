# Indicadores económicos en Presupuestos

CutLess incorpora el dólar observado y la Unidad de Fomento (UF) al listado y al detalle de Presupuestos. El detalle muestra el equivalente aproximado del total en USD para facilitar la consulta.

## Fuente y contrato

Django consulta Findic.cl con `GET https://findic.cl/api/` y acepta JSON. Se eligió Findic.cl porque el proveedor anterior no respondía oportunamente desde el equipo de prueba y Findic.cl sí respondió allí. El dominio y la ruta son fijos. La consulta externa no recibe el monto del presupuesto ni datos del usuario. El navegador solicita el JSON a una ruta de CutLess con el mismo permiso que Presupuestos. [Documentación de Findic.cl](https://findic.cl/docs/)

Ejemplo de estructura. Las fechas y cifras son **datos sintéticos de prueba**.

```json
{
  "fecha": "2026-01-10",
  "dolar": {
    "fecha": "2026-01-09",
    "valor": 800.75
  },
  "uf": {
    "fecha": "2026-01-10",
    "valor": 40000.25
  }
}
```

Se leen únicamente `dolar.valor`, `dolar.fecha`, `uf.valor` y `uf.fecha`. Se exige un número positivo y finito y una fecha de calendario válida en formato `AAAA-MM-DD`. La fecha de referencia se conserva sin conversión horaria y se compara con el día actual en `America/Santiago` para descartar fechas futuras. El panel muestra «Hoy, …» para la fecha vigente y «Dato del …» para una fecha anterior, incluso si el dato se recibió en una consulta nueva. La marca general del JSON queda fuera de la presentación. Si un indicador no es válido, el otro puede mostrarse por separado.

## Caché y errores

- El caché de Django guarda el resultado durante 15 minutos y conserva el último resultado de Findic.cl por hasta 24 horas como respaldo. Las claves son específicas de Findic.cl. El panel muestra «Valores en caché» en ambos casos. La etiqueta junto a cada fecha indica su antigüedad.
- Un marcador de 60 segundos evita intentos repetidos en paralelo y ante fallos. Las claves se comparten entre usuarios, presupuestos, listado y detalle. Con el caché local en memoria de Django, el alcance es un proceso y el contenido se pierde al reiniciarlo.
- Se usa HTTPS con validación TLS, timeout de socket de 2 segundos y límite de 64 KiB. Se descartan redirecciones, respuestas HTTP fallidas y JSON inválido. Cuando tampoco hay respaldo utilizable, el panel informa «Indicadores no disponibles por el momento».
- El panel se carga en una petición separada del listado y del detalle. Crear, listar, consultar y exportar presupuestos conserva sus rutas. La respuesta se muestra como texto en el navegador.

## Conversión referencial

Las tarjetas muestran el dólar observado y la UF redondeados al peso más cercano, con formato chileno y el símbolo de aproximación `≈`. El redondeo se aplica al formatear el texto. Django conserva los valores originales con sus decimales en el caché y en la respuesta JSON.

El navegador divide el total vigente del detalle por el valor original del dólar observado. El equivalente referencial en USD se presenta con dos decimales y depende de la fecha de referencia del dólar mostrada en el panel. Sin un dólar válido, se indica que no hay tipo de cambio. La operación es de lectura y no interviene en costos, precios, optimizaciones, totales guardados, historial ni exportaciones. No requiere dependencias nuevas ni migraciones.

## Archivos

- Consulta y caché en `cut/cutless/services/indicadores.py`. Ruta y vista JSON en `cut/cutless/urls.py` y `cut/cutless/views/budgets.py`.
- Panel compartido en `cut/cutless/templates/cutless/includes/indicadores-presupuesto.html`, integrado en `lista_presupuestos.html` y `detalle_presupuesto.html`.
- Presentación, carga y conversión en `cut/cutless/static/cutless/css/indicadores-presupuesto.css` y `cut/cutless/static/cutless/js/indicadores-presupuesto.js`.
- Pruebas en `cut/cutless/tests/test_indicadores.py` y `cut/cutless/tests/js/indicadores-presupuesto.test.cjs`. Índice actualizado en `README.md`.

## Verificación y evidencia académica

- Pasaron 43 pruebas Django sobre PostgreSQL local temporal, incluidas integración de indicadores, cálculos y creación de presupuestos, permisos y exportación. Las pruebas simulan la API, comprueban datos válidos e inválidos, ausencia de indicadores, fechas, caché, timeout, error HTTP, JSON inválido y el acceso a los presupuestos ante una caída.
- Pasaron 4 pruebas de JavaScript para el redondeo visual en CLP, el uso del dólar original en la conversión, el formato USD, las fechas y los datos indisponibles. La prueba Django del endpoint comprobó que tanto la primera respuesta como la respuesta en caché conservaran los decimales originales.
- En Chromium se comprobaron 12 combinaciones entre listado y detalle, temas claro y oscuro y anchos de 1440, 390 y 320 px con una respuesta simulada en el formato de Findic.cl. Se verificaron el nuevo enlace de fuente, los valores redondeados, la conversión con decimales y que la tarjeta se ajustara al ancho. Las capturas previas de escritorio y móvil también utilizan datos simulados.
- Al interrumpir la consulta de indicadores, el detalle conservó el total, la acción de edición y la exportación. El texto extraído del PDF coincidió antes y después de cargar la conversión, incluso al interrumpir la consulta. La prueba Django verificó también que el total persistido permaneciera intacto.

### Evidencia de la consulta real desde Django

El 21 de noviembre de 2026, el usuario comprobó primero el acceso directo a Findic.cl mediante `Invoke-RestMethod` en PowerShell. Luego, en la copia local de CutLess para Windows 11, ejecutó dos llamadas consecutivas a `obtener_indicadores()`, el servicio de Django que usa Presupuestos. La prueba usó Findic.cl por HTTPS, sin datos simulados, con SQLite local y sin conexión a Supabase.

| Llamada | `desde_cache` | Dólar observado | UF |
| --- | --- | --- | --- |
| Primera | `False` | 1008,79 CLP · 2026-11-20 | 41.377,93 CLP · 2026-11-21 |
| Segunda | `True` | 1008,79 CLP · 2026-11-20 | 41.377,93 CLP · 2026-11-21 |

La primera llamada obtuvo los indicadores de Findic.cl. La segunda recuperó del caché los mismos valores y fechas, con los decimales originales. [JSON público de Findic.cl](https://findic.cl/api/)

### Prueba real en Windows 11 con PowerShell

El ZIP contiene el código de la rama de prueba. Este procedimiento permite repetir la consulta real aprobada desde Django en Windows. Las pruebas automatizadas y las capturas anteriores usan datos simulados.

Con Python 3.13 instalado, abre una sesión nueva de PowerShell y ejecuta lo siguiente. Si el ZIP está en otra carpeta, ajusta la primera línea. La cuenta y la base SQLite se crean en el equipo de prueba.

```powershell
$zip = Join-Path $HOME 'Downloads\CutLess-Findic-Windows11.zip'
$destino = Join-Path $env:TEMP ("CutLess-Findic-" + [guid]::NewGuid().ToString('N'))
Expand-Archive -LiteralPath $zip -DestinationPath $destino
Set-Location (Join-Path $destino 'CutLess-Findic')

Get-ChildItem Env:CUTLESS_* | ForEach-Object { Remove-Item -LiteralPath "Env:$($_.Name)" }
$env:DJANGO_SETTINGS_MODULE = 'cutless_project.settings'
$env:CUTLESS_ENV = 'development'
$env:CUTLESS_DB_ENGINE = 'sqlite'
$env:CUTLESS_DB_PATH = Join-Path $PWD.Path 'cut\findic-prueba.sqlite3'
$env:CUTLESS_BREVO_RECOVERY_ENABLED = 'false'
$env:CUTLESS_RECOVERY_QUEUE_CONSUMER_ENABLED = 'false'

py -3.13 -m venv .venv
$python = Join-Path $PWD.Path '.venv\Scripts\python.exe'
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt
& $python -m pip check
& $python cut/manage.py migrate
& $python cut/manage.py check
& $python cut/manage.py createsuperuser --username findic_prueba --email findic-prueba@example.test
```

Escribe una contraseña local cuando Django la solicite. Si un comando falla, detente antes de ejecutar el siguiente. El servidor y el diagnóstico usan SQLite en este directorio temporal. Si Windows tiene una instalación funcional de Python 3.13 sin el lanzador `py`, usa `python -m venv .venv` después de confirmar la versión con `python --version`.

#### Diagnóstico del servicio Django

En la misma consola, antes de iniciar el servidor, ejecuta:

```powershell
& $python cut/manage.py shell -c "import sys; from cutless.services.indicadores import obtener_indicadores; from django.core.serializers.json import DjangoJSONEncoder; import json; sys.addaudithook(lambda evento, args: print('Conexion HTTPS:', args[1], args[2]) if evento == 'http.client.connect' else None); primera = obtener_indicadores(); segunda = obtener_indicadores(); print(json.dumps([primera, segunda], cls=DjangoJSONEncoder, indent=2)); sys.exit(0 if set(primera['indicadores']) == {'dolar', 'uf'} and primera['desde_cache'] is False and segunda == dict(primera, desde_cache=True) else 1)"
```

El diagnóstico usa `obtener_indicadores()`, el mismo servicio del endpoint de Presupuestos. Debe mostrar un intento de conexión HTTPS a `findic.cl` en el puerto 443, dos indicadores con `valor` y `fecha`, y el cambio de `desde_cache: false` a `true` sin una segunda conexión. La línea de conexión solo indica un intento. Un resultado vacío, parcial o un código de salida distinto de cero en `$LASTEXITCODE` deja la comprobación incompleta. El caché de este comando pertenece al proceso del diagnóstico.

#### Verificación en Presupuestos

```powershell
& $python cut/manage.py runserver 127.0.0.1:8000 --noreload
```

1. Inicia sesión como `findic_prueba` en [CutLess local](http://127.0.0.1:8000/usuarios/login/). Completa la configuración inicial si aparece. Abre la pestaña **Red** de las herramientas del navegador antes de entrar a [Presupuestos](http://127.0.0.1:8000/cutless/presupuestos/). El listado vacío de una base nueva también carga los indicadores.
2. Selecciona la primera solicitud a `/cutless/presupuestos/indicadores/`. En **Respuesta**, confirma HTTP 200, `desde_cache: false`, y `indicadores.dolar` e `indicadores.uf` con `valor` numérico positivo y `fecha` en formato `AAAA-MM-DD`. Compara ambos valores y fechas con el [JSON público de Findic.cl](https://findic.cl/api/). Los montos de las tarjetas se muestran redondeados al peso.
3. Recarga dentro de 15 minutos, con el servidor aún en ejecución. Confirma `desde_cache: true`, los mismos valores y fechas, y la leyenda «Valores en caché». Si ya habías abierto el listado, reinicia el servidor con `Ctrl+C` y vuelve a ejecutar el comando para repetir con el caché vacío.
4. Si tienes un presupuesto de prueba, comprueba que el equivalente del detalle corresponda al total CLP dividido por el valor original del dólar en el JSON. Para simular una caída de la interfaz, bloquea solo la ruta interna de indicadores desde las herramientas del navegador. El aviso de indisponibilidad debe dejar accesibles el presupuesto y la exportación. Este paso es independiente de la comprobación HTTPS real.
