"""Prueba manual de CutLess con un único envío y una base desechable."""

import logging
import os
import secrets
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
from wsgiref.simple_server import WSGIRequestHandler, make_server


class SinRegistroHTTP(WSGIRequestHandler):
    def log_message(self, formato, *args):
        # La línea de acceso a la página de confirmación contiene el token.
        pass


def preparar_correo(destinatario, origen):
    from django.conf import settings
    from django.core import mail
    from django.test import Client
    from django.urls import Resolver404, resolve, reverse

    cliente = Client(enforce_csrf_checks=True, HTTP_HOST=urlsplit(origen).netloc)
    formulario = reverse('usuarios:recuperar_password')
    apertura = cliente.get(formulario)
    csrf = cliente.cookies.get(settings.CSRF_COOKIE_NAME)
    if apertura.status_code != 200 or csrf is None:
        raise RuntimeError('El formulario local no está disponible.')

    previos = len(getattr(mail, 'outbox', []))
    respuesta = cliente.post(formulario, {'email': destinatario}, HTTP_X_CSRFTOKEN=csrf.value)
    correos = getattr(mail, 'outbox', [])[previos:]
    if respuesta.status_code != 302 or len(correos) != 1:
        raise RuntimeError('El flujo local no generó exactamente un correo.')
    correo = correos[0]
    enlaces = [linea for linea in correo.body.splitlines() if linea.startswith(f'{origen}/')]
    html = next((parte.content for parte in correo.alternatives if parte.mimetype == 'text/html'), '')
    if correo.to != [destinatario] or len(enlaces) != 1 or f'href="{enlaces[0]}"' not in html:
        raise RuntimeError('El destinatario o el enlace local no coinciden.')
    try:
        pagina = resolve(urlsplit(enlaces[0]).path).view_name
    except Resolver404:
        pagina = None
    if pagina != 'usuarios:reset_password_confirm':
        raise RuntimeError('El enlace no corresponde al formulario de restablecimiento.')
    return correo.subject, correo.body, html


def main():
    if not sys.stdin.isatty():
        print('Ejecuta esta prueba desde una terminal interactiva.', file=sys.stderr)
        return 2
    clave = os.environ.get('CUTLESS_BREVO_API_KEY', '').strip()
    remitente = os.environ.get('CUTLESS_BREVO_SENDER_EMAIL', '').strip()
    nombre = os.environ.get('CUTLESS_BREVO_SENDER_NAME', '').strip() or 'CutLess prueba local'
    if not clave or not remitente:
        print('Falta la configuración de Brevo en el entorno del proceso.', file=sys.stderr)
        return 2
    destinatario = input('Dirección de prueba de tu propiedad: ').strip()

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'cut'))
    from cutless_project.standalone import django_aislado

    with TemporaryDirectory(prefix='cutless-brevo-') as temporal:
        with django_aislado(temporal, Path(temporal) / 'prueba.sqlite3'):
            from django.conf import settings
            from django.contrib.auth import get_user_model
            from django.contrib.staticfiles.handlers import StaticFilesHandler
            from django.core.exceptions import ValidationError
            from django.core.management import call_command
            from django.core.validators import validate_email
            from django.core.wsgi import get_wsgi_application
            from django.db import connections
            from django.test import override_settings
            from usuarios.recuperacion import enviar_correo_brevo

            try:
                validate_email(remitente)
                validate_email(destinatario)
            except ValidationError:
                print('El remitente o el destinatario tiene un formato inválido.', file=sys.stderr)
                return 2

            settings.DEBUG = False
            settings.ALLOWED_HOSTS = ['127.0.0.1']
            logging.basicConfig(level=logging.WARNING)
            try:
                call_command('migrate', interactive=False, verbosity=0)
                usuarios = get_user_model().objects
                destinatario = usuarios.normalize_email(destinatario)
                usuarios.create_user('recuperacion-prueba', destinatario, secrets.token_urlsafe(32))
                aplicacion = StaticFilesHandler(get_wsgi_application())
                with make_server('127.0.0.1', 0, aplicacion, handler_class=SinRegistroHTTP) as servidor:
                    origen = f'http://127.0.0.1:{servidor.server_port}'
                    asunto, texto, html = preparar_correo(destinatario, origen)
                    print(f'Servidor local preparado en {origen}. Usuario: recuperacion-prueba.')
                    if input('Para autorizar un solo intento escribe ENVIAR UNA VEZ: ') != 'ENVIAR UNA VEZ':
                        print('Prueba cancelada. No se envió correo.')
                        return 0
                    with override_settings(BREVO_API_KEY=clave, BREVO_SENDER_EMAIL=remitente, BREVO_SENDER_NAME=nombre):
                        aceptado = enviar_correo_brevo(destinatario, asunto, texto, html)
                    if not aceptado:
                        print('Brevo no confirmó la aceptación. Revisa su panel antes de volver a intentar.', file=sys.stderr)
                        return 1
                    print('Brevo aceptó el correo. Abre el enlace recibido en este equipo. Sal con Ctrl+C.', flush=True)
                    servidor.serve_forever()
            except KeyboardInterrupt:
                return 0
            except (OSError, RuntimeError):
                print('No se pudo preparar o mantener la prueba local.', file=sys.stderr)
                return 1
            finally:
                connections.close_all()


if __name__ == '__main__':
    raise SystemExit(main())
