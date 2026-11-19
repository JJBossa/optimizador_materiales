"""Genera una sonda cifrada o recibe su entrega en un servidor aislado."""

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from types import ModuleType
from wsgiref.simple_server import WSGIRequestHandler, make_server


class SinRegistroHTTP(WSGIRequestHandler):
    def log_message(self, formato, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('accion', choices=('mensaje', 'servir'))
    parser.add_argument('--host', help='Host exacto de la URL temporal de Cloudflare Tunnel.')
    opciones = parser.parse_args()
    if opciones.accion == 'servir' and not re.fullmatch(
        r'[a-z0-9-]+\.trycloudflare\.com', opciones.host or '',
    ):
        parser.error('Para servir indica el host de un Quick Tunnel con --host, sin esquema ni ruta.')
    cifrado = os.environ.get('CUTLESS_RECOVERY_QUEUE_ENCRYPTION_KEY', '').strip()
    firma = os.environ.get('CUTLESS_RECOVERY_QUEUE_HMAC_KEY', '').strip()

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cut'))
    from cutless_project.standalone import django_aislado

    with TemporaryDirectory(prefix='cutless-sonda-cola-') as directorio:
        with django_aislado(directorio, Path(directorio) / 'prueba.sqlite3'):
            from django.conf import settings
            from django.core.wsgi import get_wsgi_application
            from django.db import connections
            from django.urls import path
            from usuarios.cola_recuperacion import RUTA_CONSUMIDOR, claves_configuradas, consumir_recuperacion, crear_sobre

            settings.RECOVERY_QUEUE_ENCRYPTION_KEY = cifrado
            settings.RECOVERY_QUEUE_HMAC_KEY = firma
            if not claves_configuradas():
                parser.error('Se requieren dos claves hexadecimales distintas de 32 bytes en el entorno.')
            if opciones.accion == 'mensaje':
                print(json.dumps(crear_sobre(None)))
                return

            settings.DEBUG = False
            settings.ALLOWED_HOSTS = [opciones.host]
            settings.RECOVERY_QUEUE_CONSUMER_ENABLED = True
            settings.BREVO_RECOVERY_ENABLED = False
            settings.BREVO_API_KEY = ''
            # El socket solo escucha en loopback, detrás del Quick Tunnel de la prueba.
            settings.SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
            settings.MIDDLEWARE = [m for m in settings.MIDDLEWARE if not m.endswith('.DatabaseHealthCheckMiddleware')]
            urlconf = ModuleType('cutless_sonda_cola')
            urlconf.urlpatterns = [path(RUTA_CONSUMIDOR.lstrip('/'), consumir_recuperacion, {'solo_sonda': True})]
            settings.ROOT_URLCONF = urlconf
            django = get_wsgi_application()
            registros = logging.getLogger('usuarios.recuperacion')
            registros.addHandler(logging.StreamHandler())
            registros.setLevel(logging.INFO)
            registros.propagate = False

            def aplicacion(entorno, responder):
                if entorno['PATH_INFO'] != RUTA_CONSUMIDOR:
                    responder('404 Not Found', [('Content-Length', '0')])
                    return [b'']
                return django(entorno, responder)

            try:
                with make_server('127.0.0.1', 8765, aplicacion, handler_class=SinRegistroHTTP) as servidor:
                    print('Esperando la sonda cifrada en 127.0.0.1:8765.', flush=True)
                    servidor.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                connections.close_all()


if __name__ == '__main__':
    main()
