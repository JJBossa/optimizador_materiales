"""Servidor aislado para medir RNF-03 usando el formulario real del navegador.

Ejemplo (desde la raíz):
python tools/performance_rnf03.py --work-dir <carpeta-nueva> --output <evidencias>
No cambia el código de producción ni usa su SQLite o MEDIA_ROOT.
"""
import argparse
import contextvars
import csv
import getpass
import io
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

CURRENT = contextvars.ContextVar('rnf03_request', default=None)
LOCK = threading.Lock()
RECORDS = []
OUTPUT = None
METADATA = {}
EXPECTED = [(30., 40., 20), (40., 50., 20), (20., 30., 10)]

BROWSER_SCRIPT = r"""
<script>
(() => {
  const key = 'cutless:rnf03:start';
  document.addEventListener('click', event => {
    const button = event.target.closest('button[type="submit"]');
    if (button?.form?.id === 'optimizacion-form') {
      sessionStorage.setItem(key, String(performance.timeOrigin + performance.now()));
    }
  }, true);
  const run = __RUN__;
  if (!run) return;
  async function complete() {
    const start = Number(sessionStorage.getItem(key));
    sessionStorage.removeItem(key);
    if (!start) return;
    await document.fonts.ready;
    const images = Array.from(document.images).filter(img => img.getClientRects().length);
    await Promise.allSettled(images.map(img => img.decode()));
    const page = document.querySelector('.board-page:not([hidden])');
    if (page) await Promise.allSettled(page.getAnimations({subtree:true})
      .filter(animation => animation.effect.getTiming().iterations !== Infinity)
      .map(animation => animation.finished));
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const stop = performance.timeOrigin + performance.now();
    const drawing = document.querySelector('.board-page:not([hidden]) svg.board-drawing');
    const box = drawing?.getBoundingClientRect();
    const navigation = performance.getEntriesByType('navigation')[0];
    const metric = {
      run, perceived_s:(stop-start)/1000,
      result_visible:Boolean(document.querySelector('.total-utilization') && box?.width && box?.height),
      navigation_s:navigation ? (performance.timeOrigin + navigation.loadEventEnd-start)/1000 : null,
      browser:navigator.userAgent,
      viewport:[innerWidth,innerHeight], device_pixel_ratio:devicePixelRatio,
      document_visibility:document.visibilityState
    };
    const response = await fetch('/__rnf03__/measurement/', {
      method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(metric)
    });
    const marker = document.createElement('output');
    marker.id = 'rnf03-measurement'; marker.dataset.metric = JSON.stringify(metric);
    marker.dataset.saved = String(response.ok);
    marker.textContent = `RNF-03 · ejecución ${run}: ${metric.perceived_s.toFixed(3)} s`;
    marker.style.cssText = 'position:fixed;left:250px;bottom:12px;padding:8px;background:white;color:black;z-index:9999;border:1px solid gray';
    document.body.append(marker);
  }
  if (document.readyState === 'complete') complete();
  else window.addEventListener('load', complete, {once:true});
})();
</script>
"""


def write_reports():
    """Conserva cada muestra sin descartar la primera ni las lentas."""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT/'resultados.json').write_text(json.dumps(
        {'metadata':METADATA, 'runs':RECORDS}, ensure_ascii=False, indent=2), encoding='utf-8')
    fields = ['run','algorithm_s','server_s','perceived_s','http_status','placed',
              'requested','boards','input_matches','result_visible','within_10s']
    with (OUTPUT/'tiempos.csv').open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for row in RECORDS:
            browser = row.get('browser_measurement', {})
            valid = row.get('http_status') == 200 and row.get('placed') == 50 and row.get('input_matches') and browser.get('result_visible')
            writer.writerow({**row, 'perceived_s':browser.get('perceived_s'),
                'result_visible':browser.get('result_visible'),
                'within_10s':bool(valid and browser.get('perceived_s', float('inf')) <= 10)})


class MeasurementMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.http import JsonResponse
        if request.path == '/__rnf03__/measurement/' and request.method == 'POST':
            metric = json.loads(request.body)
            with LOCK:
                row = next((row for row in RECORDS if row['run'] == metric['run']), None)
                if row is None or row.get('browser_measurement'):
                    return JsonResponse({'saved':False}, status=409)
                row['browser_measurement'] = metric
                write_reports()
                print(f"RNF-03 {row['run']:02d}: algoritmo={row['algorithm_s']:.6f}s servidor={row['server_s']:.3f}s visible={metric['perceived_s']:.3f}s", flush=True)
            return JsonResponse({'saved':True})
        measured = request.method == 'POST' and request.path == '/cutless/'
        row = {'run':len(RECORDS)+1, 'algorithm_s':0., 'algorithm_calls':0} if measured else None
        token = CURRENT.set(row)
        start = time.perf_counter()
        try:
            response = self.get_response(request)
        finally:
            duration = time.perf_counter()-start
            CURRENT.reset(token)
        if measured:
            row.update(server_s=duration, http_status=response.status_code)
            with LOCK:
                RECORDS.append(row)
                write_reports()
        if 'text/html' in response.get('Content-Type','') and not response.streaming:
            script = BROWSER_SCRIPT.replace('__RUN__', str(row['run']) if row else 'null')
            response.content = response.content.replace(b'</body>', script.encode()+b'</body>')
            response['Content-Length'] = len(response.content)
        return response


def main():
    global OUTPUT, METADATA
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--port', default=8106, type=int)
    args = parser.parse_args()
    work = args.work_dir.resolve()
    work.mkdir(parents=True, exist_ok=True)
    database = work/'benchmark.sqlite3'
    if database.exists():
        parser.error('La carpeta ya contiene benchmark.sqlite3. Usa otra carpeta para una campaña nueva.')
    OUTPUT = args.output.resolve()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE','cutless_project.settings')
    os.environ['MPLCONFIGDIR'] = str(work/'matplotlib')
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'cut'))
    from django.conf import settings
    settings.DATABASES['default']['NAME'] = str(database)
    settings.MEDIA_ROOT = str(work/'media')
    settings.ALLOWED_HOSTS = ['127.0.0.1','localhost','testserver']
    settings.MIDDLEWARE = [__name__+'.MeasurementMiddleware', *settings.MIDDLEWARE]
    import django
    django.setup()
    from django.core.management import call_command
    call_command('migrate', verbosity=0)
    from django.contrib.auth.models import User
    user = User.objects.create_user('rnf03', password=getpass.getpass('Contraseña para el usuario local rnf03: '))
    profile = user.perfil
    profile.tutorial_completado = True
    profile.preferencias_menu = {'_inicio_completado':True}
    profile.save()
    import cutless.render as rendering
    original = rendering.optimizar_corte
    def timed_algorithm(piezas, ancho_tablero, alto_tablero, *positional, **keywords):
        started = time.perf_counter()
        result = original(piezas, ancho_tablero, alto_tablero, *positional, **keywords)
        elapsed = time.perf_counter()-started
        row = CURRENT.get()
        if row is not None:
            info = result[2]
            row['algorithm_s'] += elapsed
            row['algorithm_calls'] += 1
            row.update(placed=info['num_piezas_colocadas'],requested=info['num_piezas_solicitadas'],
                boards=len(result[0]), usage=float(result[1]),
                input_matches=bool(list(piezas) == EXPECTED and ancho_tablero == 122 and alto_tablero == 244
                    and keywords.get('permitir_rotacion') is True and abs(keywords.get('margen_corte',0)-.3) < 1e-9))
        return result
    rendering.optimizar_corte = timed_algorithm
    import subprocess
    METADATA = {
        'started_at':datetime.now(ZoneInfo('America/Santiago')).isoformat(),
        'revision':subprocess.check_output(['git','rev-parse','HEAD'],cwd=Path(__file__).resolve().parents[1],text=True).strip(),
        'python':sys.version, 'django':django.get_version(), 'os':platform.platform(),
        'processor':platform.processor(), 'logical_cpus':os.cpu_count(), 'debug':settings.DEBUG,
        'database':'SQLite aislada', 'pieces':EXPECTED, 'board_cm':[122,244],
        'kerf_mm':3,'rotation':True,'expected_repetitions':20,'limit_s':10,
        'method':'Clic real + load + fuentes/imágenes visibles + fin de animación inicial + dos requestAnimationFrame',
        'algorithm_clock':'time.perf_counter', 'server_clock':'time.perf_counter',
        'browser_clock':'performance.timeOrigin + performance.now',
    }
    write_reports()
    print(f'RNF-03 listo: http://127.0.0.1:{args.port}/cutless/ (usuario desechable rnf03)', flush=True)
    call_command('runserver',f'127.0.0.1:{args.port}',use_reloader=False)


if __name__ == '__main__':
    main()
