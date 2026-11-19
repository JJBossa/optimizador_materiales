import hmac
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from http.client import HTTPException
from logging import LogRecord, Logger
from runpy import run_path
from secrets import token_hex, token_urlsafe
from threading import Barrier
from time import time
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.core import mail
from django.core.management import call_command
from django.db import OperationalError, connections, transaction
from django.test import (
    Client, RequestFactory, SimpleTestCase, TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature,
)
from django.urls import path, reverse
from django.utils import timezone

from cutless_project.recovery_logging import FiltroRecuperacion
from usuarios.cola_recuperacion import consumir_recuperacion, crear_sobre
from usuarios.limites_recuperacion import (
    CONTADOR_ENVIOS, CONTADOR_SOLICITUDES, TRABAJOS_RECLAMADOS, admitir_solicitud, reclamar_trabajo, reservar_envio,
)
from usuarios.recuperacion import enviar_correo_brevo


DOMINIO = 'cutless.example.test'
ALIAS = 'alias.example.test'
REMITENTE = 'recuperacion@example.test'
CLAVE_DE_PRUEBA = token_urlsafe(24)
CORREO = 'activa@example.test'
CLAVE_ANTERIOR = token_urlsafe(24)
RUTA_CONFIRMACION_FICTICIA = f'/usuarios/reset-password/uid/{token_urlsafe(24)}/'
RESPUESTA_GENERICA = 'Si el correo existe en nuestro sistema'
LOGGER = 'usuarios.recuperacion'


@override_settings(
    CUTLESS_ENV='production',
    PASSWORD_RESET_HOST=DOMINIO,
    ALLOWED_HOSTS=[DOMINIO, ALIAS],
    BREVO_RECOVERY_ENABLED=True,
    BREVO_API_KEY=CLAVE_DE_PRUEBA,
    BREVO_SENDER_EMAIL=REMITENTE,
    BREVO_SENDER_NAME='CutLess pruebas',
    RECOVERY_QUEUE_CONSUMER_ENABLED=True,
    RECOVERY_QUEUE_ACCOUNT_ID=token_hex(16),
    RECOVERY_QUEUE_ID=token_hex(16),
    RECOVERY_QUEUE_API_TOKEN=token_urlsafe(24),
    RECOVERY_QUEUE_ENCRYPTION_KEY=token_hex(32),
    RECOVERY_QUEUE_HMAC_KEY=token_hex(32),
)
class RecuperacionBrevoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user('activa', CORREO, password=CLAVE_ANTERIOR)
        cls.inactiva = User.objects.create_user('inactiva', 'inactiva@example.test', token_urlsafe(24), is_active=False)
        cls.sin_password = User.objects.create_user('sin-password', 'sin-password@example.test')
        cls.otra = User.objects.create_user('otra', 'otra@example.test', token_urlsafe(24))

    def setUp(self):
        simulacion = patch('usuarios.recuperacion.HTTPSConnection', autospec=True)
        self.https = simulacion.start()
        self.addCleanup(simulacion.stop)
        self.conexion = self.https.return_value
        self.respuesta_brevo = self.conexion.getresponse.return_value
        self.respuesta_brevo.status = 201
        cola = patch('usuarios.cola_recuperacion.HTTPSConnection', autospec=True)
        self.cloudflare = cola.start()
        self.addCleanup(cola.stop)
        self.conexion_cola = self.cloudflare.return_value
        self.respuesta_cola = self.conexion_cola.getresponse.return_value
        self.respuesta_cola.status = 200
        self.respuesta_cola.read.return_value = b'{"success":true}'

    def solicitar(self, correo=CORREO, *, host=DOMINIO, entregar=True, **headers):
        antes = self.conexion_cola.request.call_count
        respuesta = self.client.post(
            reverse('usuarios:recuperar_password'), {'email': correo},
            secure=True, HTTP_HOST=host, follow=True, **headers,
        )
        self.assertEqual(respuesta.redirect_chain, [(reverse('usuarios:login'), 302)])
        self.assertContains(respuesta, RESPUESTA_GENERICA)
        if entregar and self.conexion_cola.request.call_count > antes:
            self.assert_acuse(self.entregar(self.ultimo_sobre()))
        return respuesta

    def ultimo_sobre(self):
        return json.loads(self.conexion_cola.request.call_args.kwargs['body'])['body']

    def entregar(self, sobre, *, firmado=None, fecha=None, secure=True, ruta=None):
        fecha = str(int(time()) if fecha is None else fecha)
        cuerpo = json.dumps(sobre).encode()
        firmado = cuerpo if firmado is None else firmado
        datos = b'cutless.queue.callback.v1\n' + fecha.encode() + b'\n' + firmado
        firma = hmac.digest(bytes.fromhex(settings.RECOVERY_QUEUE_HMAC_KEY), datos, 'sha256').hex()
        return Client(enforce_csrf_checks=True).post(
            ruta or reverse('usuarios:consumir_recuperacion'), cuerpo, content_type='application/json',
            secure=secure, HTTP_HOST=DOMINIO, HTTP_X_CUTLESS_TIMESTAMP=fecha, HTTP_X_CUTLESS_SIGNATURE=firma,
        )

    def assert_acuse(self, respuesta):
        self.assertEqual(respuesta.status_code, 204)
        self.assertEqual(respuesta.headers['X-Cutless-Queue'], 'ack-v1')

    def enlace_enviado(self):
        contenido = json.loads(self.conexion.request.call_args.kwargs['body'])
        return next(linea for linea in contenido['textContent'].splitlines() if linea.startswith('https://'))

    def test_publica_texto_y_html_https_en_dominio_oficial(self):
        with self.assertLogs(LOGGER, 'INFO') as logs:
            self.solicitar(CORREO.upper(), host=ALIAS, HTTP_X_FORWARDED_HOST='otro.example.test')

        self.https.assert_called_once_with('api.brevo.com', timeout=5)
        self.conexion.request.assert_called_once()
        self.conexion.close.assert_called_once()
        envio = self.conexion.request.call_args
        self.assertEqual(envio.args, ('POST', '/v3/smtp/email'))
        self.assertEqual(envio.kwargs['headers'], {'api-key': CLAVE_DE_PRUEBA, 'Content-Type': 'application/json'})
        contenido = json.loads(envio.kwargs['body'])
        self.assertEqual(contenido['sender'], {'email': REMITENTE, 'name': 'CutLess pruebas'})
        self.assertEqual(contenido['to'], [{'email': CORREO, 'contactPixelTrackingConsent': False}])
        self.assertEqual(contenido['tags'], ['cutless-recuperacion'])
        self.assertEqual(contenido['subject'], 'Recuperación de contraseña - CutLess')
        enlace = self.enlace_enviado()
        self.assertEqual(urlsplit(enlace).netloc, DOMINIO)
        self.assertIn(f'href="{enlace}"', contenido['htmlContent'])
        self.assertIn('brevo_recuperacion_aceptada entrega=no_confirmada',
                      [registro.getMessage() for registro in logs.records])
        self.assertEqual(mail.outbox, [])

    def test_desconocida_inactiva_y_sin_password_reciben_la_misma_respuesta(self):
        for correo in ('no-registrada@example.test', self.inactiva.email, self.sin_password.email):
            with self.subTest(correo=correo):
                self.solicitar(correo)
        self.https.assert_not_called()

    def test_publica_antes_de_buscar_cuentas_y_cifra_el_correo(self):
        correos = (CORREO, self.inactiva.email, 'no-registrada@example.test')
        with patch('usuarios.recuperacion.PasswordResetForm.get_users') as buscar:
            for correo in correos:
                self.solicitar(correo, entregar=False)
            buscar.assert_not_called()
        self.https.assert_not_called()
        self.assertEqual(self.cloudflare.call_count, len(correos))
        for llamada in self.cloudflare.call_args_list:
            self.assertEqual(llamada.args, ('api.cloudflare.com',))
        for correo, envio in zip(correos, self.conexion_cola.request.call_args_list):
            cuerpo = envio.kwargs['body']
            self.assertNotIn(correo.encode(), cuerpo)
            carga = json.loads(cuerpo)
            self.assertEqual(carga['content_type'], 'json')
            self.assertEqual(set(carga['body']), {'v', 'id', 'exp', 'nonce', 'data'})
            self.assertEqual(envio.args, ('POST', f'/client/v4/accounts/{settings.RECOVERY_QUEUE_ACCOUNT_ID}'
                                                 f'/queues/{settings.RECOVERY_QUEUE_ID}/messages'))
            self.assertEqual(envio.kwargs['headers']['Authorization'], f'Bearer {settings.RECOVERY_QUEUE_API_TOKEN}')

    def test_fallo_de_publicacion_no_envia_por_brevo_desde_la_vista(self):
        self.respuesta_cola.status = 429
        with self.assertLogs(LOGGER, 'WARNING') as logs:
            self.solicitar(entregar=False)
        self.assertEqual(logs.records[0].getMessage(), 'cola_recuperacion_publicacion_rechazada')
        self.https.assert_not_called()

    def test_publico_sigue_exigiendo_csrf_y_no_publica_sin_token(self):
        respuesta = Client(enforce_csrf_checks=True).post(
            reverse('usuarios:recuperar_password'), {'email': CORREO}, secure=True, HTTP_HOST=DOMINIO,
        )
        self.assertEqual(respuesta.status_code, 403)
        self.cloudflare.assert_not_called()
        self.https.assert_not_called()

    def test_reentrega_del_mismo_sobre_no_repite_brevo_ni_la_reserva(self):
        self.solicitar()
        sobre = self.ultimo_sobre()
        self.assert_acuse(self.entregar(sobre))
        self.https.assert_called_once()
        reserva = Session.objects.get(pk=TRABAJOS_RECLAMADOS)
        self.assertEqual(json.loads(reserva.session_data), {sobre['id']: sobre['exp']})

    def test_reentrega_despues_de_timeout_ambiguo_no_repite_brevo(self):
        self.conexion.getresponse.side_effect = TimeoutError
        with self.assertLogs(LOGGER, 'WARNING'):
            self.solicitar()
        self.assert_acuse(self.entregar(self.ultimo_sobre()))
        self.https.assert_called_once()

    def test_rechaza_firma_incorrecta_fecha_antigua_http_y_sobre_alterado(self):
        sobre = crear_sobre(CORREO)
        for opciones in ({'firmado': b'{}'}, {'fecha': int(time()) - 600}, {'secure': False}):
            with self.subTest(opciones=opciones):
                self.assertEqual(self.entregar(sobre, **opciones).status_code, 403)
        self.assertEqual(self.entregar({**sobre, 'id': token_hex(16)}).status_code, 400)
        self.assertFalse(Session.objects.filter(pk=TRABAJOS_RECLAMADOS).exists())
        self.https.assert_not_called()

    def test_rechaza_callback_sin_firma_antes_de_descifrar(self):
        with patch('usuarios.cola_recuperacion._descifrar') as descifrar:
            respuesta = Client(enforce_csrf_checks=True).post(
                reverse('usuarios:consumir_recuperacion'), json.dumps(crear_sobre(CORREO)),
                content_type='application/json', secure=True, HTTP_HOST=DOMINIO,
            )
        self.assertEqual(respuesta.status_code, 403)
        descifrar.assert_not_called()
        self.https.assert_not_called()

    def test_fallo_del_receptor_no_registra_email_credencial_ni_cifrado(self):
        sobre = crear_sobre(CORREO)
        datos = f'{CORREO} {settings.RECOVERY_QUEUE_HMAC_KEY} {sobre["data"]}'
        with patch('usuarios.recuperacion.procesar_solicitud_brevo', side_effect=OperationalError(datos)):
            with self.assertLogs(LOGGER, 'WARNING') as logs:
                self.assert_acuse(self.entregar(sobre))
        self.assertEqual([registro.getMessage() for registro in logs.records],
                         ['cola_recuperacion_fallo_despues_de_reclamar'])
        self.assert_acuse(self.entregar(sobre))
        self.https.assert_not_called()

    def test_omite_trabajo_expirado_sin_buscar_ni_enviar(self):
        with patch('usuarios.cola_recuperacion.time', return_value=time() - 901):
            sobre = crear_sobre(CORREO)
        with patch('usuarios.recuperacion.FormularioRecuperacionBrevo.get_users') as buscar:
            self.assert_acuse(self.entregar(sobre))
        buscar.assert_not_called()
        self.https.assert_not_called()

    @override_settings(BREVO_RECOVERY_ENABLED=False, BREVO_API_KEY='')
    def test_sonda_con_publico_apagado_no_busca_ni_usa_brevo(self):
        with patch('usuarios.recuperacion.FormularioRecuperacionBrevo.get_users') as buscar:
            self.assert_acuse(self.entregar(crear_sobre(None)))
        buscar.assert_not_called()
        self.https.assert_not_called()
        self.assertFalse(Session.objects.filter(pk=TRABAJOS_RECLAMADOS).exists())

    def test_receptor_de_prueba_solo_acepta_sondas_aun_con_brevo_configurado(self):
        prueba = ModuleType('urlconf_sonda_cola_tests')
        ruta = reverse('usuarios:consumir_recuperacion')
        prueba.urlpatterns = [path(ruta.lstrip('/'), consumir_recuperacion, {'solo_sonda': True})]
        with override_settings(ROOT_URLCONF=prueba):
            with patch('usuarios.recuperacion.FormularioRecuperacionBrevo.get_users') as buscar:
                self.assertEqual(self.entregar(crear_sobre(CORREO), ruta=ruta).status_code, 403)
                self.assert_acuse(self.entregar(crear_sobre(None), ruta=ruta))
            buscar.assert_not_called()
        self.https.assert_not_called()
        self.assertFalse(Session.objects.filter(pk=TRABAJOS_RECLAMADOS).exists())

    @override_settings(RECOVERY_QUEUE_CONSUMER_ENABLED=False)
    def test_consumidor_apagado_impide_publicacion_y_procesamiento(self):
        self.assertEqual(self.entregar(crear_sobre(CORREO)).status_code, 503)
        with self.assertLogs(LOGGER, 'WARNING'):
            self.solicitar()
        self.cloudflare.assert_not_called()
        self.https.assert_not_called()

    def test_fallo_de_registro_se_puede_reintentar_antes_de_enviar(self):
        sobre = crear_sobre(CORREO)
        with patch('usuarios.cola_recuperacion.reclamar_trabajo', return_value=None):
            self.assertEqual(self.entregar(sobre).status_code, 503)
        self.https.assert_not_called()
        self.assert_acuse(self.entregar(sobre))
        self.https.assert_called_once()

    def test_correo_invalido_conserva_el_error_del_formulario(self):
        respuesta = self.client.post(
            reverse('usuarios:recuperar_password'), {'email': 'sin-dominio'}, secure=True, HTTP_HOST=DOMINIO,
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context['form'].errors.as_data()['email'][0].code, 'invalid')
        self.assertNotContains(respuesta, RESPUESTA_GENERICA)
        self.https.assert_not_called()

    def test_host_de_solicitud_no_autorizado_es_rechazado(self):
        respuesta = self.client.post(
            reverse('usuarios:recuperar_password'), {'email': CORREO},
            secure=True, HTTP_HOST='otro.example.test',
        )
        self.assertEqual(respuesta.status_code, 400)
        self.https.assert_not_called()

    @override_settings(BREVO_RECOVERY_ENABLED=False)
    def test_interruptor_apagado_no_busca_ni_envia_aunque_las_credenciales_esten_configuradas(self):
        with patch('usuarios.recuperacion.FormularioRecuperacion.get_users') as buscar:
            self.solicitar()
        buscar.assert_not_called()
        self.https.assert_not_called()
        self.cloudflare.assert_not_called()
        self.assertEqual(mail.outbox, [])
        self.assertFalse(Session.objects.filter(pk=CONTADOR_SOLICITUDES).exists())

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    @patch('django.core.mail.backends.console.EmailBackend.send_messages', autospec=True)
    def test_configuracion_faltante_o_invalida_no_recurre_a_la_consola(self, correo_consola):
        casos = (
            {'BREVO_API_KEY': ''},
            {'BREVO_SENDER_EMAIL': ''},
            {'BREVO_SENDER_EMAIL': 'Nombre <recuperacion@example.test>'},
            {'PASSWORD_RESET_HOST': ''},
            {'PASSWORD_RESET_HOST': f'https://{DOMINIO}'},
            {'PASSWORD_RESET_HOST': f'{DOMINIO}/ruta'},
            {'PASSWORD_RESET_HOST': f'{DOMINIO}:443'},
            {'PASSWORD_RESET_HOST': 'otro.example.test'},
        )
        for cambios in casos:
            with self.subTest(cambios=cambios), override_settings(**cambios):
                with self.assertLogs(LOGGER, 'WARNING') as logs:
                    self.solicitar()
                self.assertEqual(logs.records[0].getMessage(), 'brevo_recuperacion_configuracion_incompleta')
        self.https.assert_not_called()
        correo_consola.assert_not_called()

        with override_settings(BREVO_API_KEY=''):
            ingreso = self.client.post(
                reverse('usuarios:login'), {'username': self.usuario.username, 'password': CLAVE_ANTERIOR},
                secure=True, HTTP_HOST=DOMINIO,
            )
        self.assertEqual(ingreso.status_code, 302)
        self.assertEqual(self.client.session['_auth_user_id'], str(self.usuario.pk))

    @patch('usuarios.recuperacion.admitir_solicitud', return_value=True)
    def test_errores_http_conservan_la_respuesta_y_omiten_el_cuerpo_de_brevo(self, _):
        for estado, evento in (
            (401, 'autenticacion_o_permisos'), (403, 'autenticacion_o_permisos'), (429, 'limite'),
            (400, 'respuesta_inesperada'), (503, 'respuesta_inesperada'), (302, 'respuesta_inesperada'),
        ):
            with self.subTest(estado=estado):
                self.https.reset_mock()
                self.respuesta_brevo.status = estado
                with self.assertLogs(LOGGER, 'WARNING') as logs:
                    self.solicitar()
                self.assertEqual(logs.records[0].getMessage(), f'brevo_recuperacion_{evento} estado={estado}')
                self.https.assert_called_once()
                self.respuesta_brevo.read.assert_not_called()
                self.conexion.close.assert_called_once()

    @patch('usuarios.recuperacion.admitir_solicitud', return_value=True)
    def test_timeout_y_caida_no_registran_datos_de_la_excepcion_ni_reintentan(self, _):
        for excepcion, evento in (
            (TimeoutError, 'tiempo_agotado'),
            (OSError, 'error_transporte'),
            (HTTPException, 'error_transporte'),
        ):
            with self.subTest(excepcion=excepcion):
                self.https.reset_mock()
                datos_sensibles = f'{CLAVE_DE_PRUEBA} {CORREO} {RUTA_CONFIRMACION_FICTICIA}'
                self.conexion.getresponse.side_effect = excepcion(datos_sensibles)
                with self.assertLogs(LOGGER, 'WARNING') as logs:
                    self.solicitar()
                self.assertEqual(logs.records[0].getMessage(), f'brevo_recuperacion_{evento}')
                self.assertIsNone(logs.records[0].exc_info)
                self.https.assert_called_once()
                self.conexion.close.assert_called_once()

    def test_429_detiene_el_lote_de_cuentas_con_correo_compartido(self):
        User.objects.create_user('segunda', CORREO, token_urlsafe(24))
        self.respuesta_brevo.status = 429
        with self.assertLogs(LOGGER, 'WARNING'):
            self.solicitar()
        self.https.assert_called_once()
        login = self.client.post(
            reverse('usuarios:login'), {'username': self.usuario.username, 'password': CLAVE_ANTERIOR},
            secure=True, HTTP_HOST=DOMINIO,
        )
        self.assertEqual(login.status_code, 302)
        self.assertEqual(self.client.session['_auth_user_id'], str(self.usuario.pk))

    def test_dos_cuentas_con_correo_compartido_reciben_sus_enlaces(self):
        User.objects.create_user('segunda', CORREO, token_urlsafe(24))
        self.solicitar()
        envios = self.conexion.request.call_args_list
        self.assertEqual(len(envios), 2)
        self.assertNotEqual(*[json.loads(envio.kwargs['body'])['textContent'] for envio in envios])

    def test_limita_por_igual_correos_activos_inactivos_y_desconocidos(self):
        for correo in (CORREO, self.inactiva.email, 'no-registrada@example.test'):
            for _ in range(2):
                self.solicitar(correo)
            with patch('usuarios.recuperacion.FormularioRecuperacion.get_users') as buscar:
                self.solicitar(correo.upper())
                buscar.assert_not_called()
        self.assertEqual(self.https.call_count, 2)

    def test_cuota_global_de_envios_no_afecta_sesion_ni_respuesta(self):
        otra_sesion = Client()
        otra_sesion.force_login(self.otra)
        clave_sesion = otra_sesion.session.session_key
        estado_previo = Session.objects.get(pk=clave_sesion).session_data

        with patch('usuarios.limites_recuperacion.LIMITES_ENVIOS', ((300, 1, False),)):
            self.solicitar()
            self.solicitar(self.otra.email)
        self.https.assert_called_once()
        self.assertEqual(Session.objects.get(pk=clave_sesion).session_data, estado_previo)
        self.assertEqual(otra_sesion.session['_auth_user_id'], str(self.otra.pk))

    def test_fallo_del_limitador_omite_envios_y_detalles_privados(self):
        fallo = OperationalError(f'dato ficticio sensible {CLAVE_DE_PRUEBA} {CORREO}')
        with patch.object(Session.objects, 'select_for_update', side_effect=fallo):
            with self.assertLogs(LOGGER, 'WARNING') as logs:
                self.solicitar()
        self.assertEqual(logs.records[0].getMessage(), 'brevo_recuperacion_limitador_no_disponible')
        self.assertIsNone(logs.records[0].exc_info)
        self.https.assert_not_called()

    def test_enlace_vence_a_la_hora(self):
        self.assertEqual(settings.PASSWORD_RESET_TIMEOUT, 3600)
        emitido = datetime(2026, 1, 1, 12)
        with patch.object(default_token_generator, '_now', return_value=emitido):
            self.solicitar()
        ruta = urlsplit(self.enlace_enviado()).path
        with patch.object(default_token_generator, '_now', return_value=emitido + timedelta(seconds=3600)):
            vigente = self.client.get(ruta, secure=True, HTTP_HOST=DOMINIO)
            self.assertIn('/set-password/', vigente.url)
        with patch.object(default_token_generator, '_now', return_value=emitido + timedelta(seconds=3601)):
            vencido = self.client.get(ruta, secure=True, HTTP_HOST=DOMINIO)
            self.assertEqual(vencido.url, reverse('usuarios:recuperar_password'))

    def test_restablece_password_rechaza_reuso_y_conserva_otras_cuentas(self):
        otras_cuentas = User.objects.exclude(pk=self.usuario.pk).values_list('pk', 'password', 'last_login').order_by('pk')
        estado_original = list(otras_cuentas)
        nueva_clave = token_urlsafe(24)
        self.solicitar()
        enlace = urlsplit(self.enlace_enviado()).path
        destino = self.client.get(enlace, secure=True, HTTP_HOST=DOMINIO)
        self.assertIn('/set-password/', destino.url)
        self.assertEqual(destino.headers['Referrer-Policy'], 'no-referrer')
        formulario = self.client.get(destino.url, secure=True, HTTP_HOST=DOMINIO)
        self.assertEqual(formulario.status_code, 200)
        self.assertEqual(formulario.headers['Referrer-Policy'], 'same-origin')
        cambio = self.client.post(
            destino.url, {'new_password1': nueva_clave, 'new_password2': nueva_clave},
            secure=True, HTTP_HOST=DOMINIO,
        )
        self.assertEqual(cambio.url, reverse('usuarios:login'))
        reusado = Client().get(enlace, secure=True, HTTP_HOST=DOMINIO)
        self.assertEqual(reusado.url, reverse('usuarios:recuperar_password'))

        login = reverse('usuarios:login')
        antigua = self.client.post(login, {'username': self.usuario.username, 'password': CLAVE_ANTERIOR},
                                   secure=True, HTTP_HOST=DOMINIO)
        self.assertEqual(antigua.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)
        nueva = self.client.post(login, {'username': self.usuario.username, 'password': nueva_clave},
                                 secure=True, HTTP_HOST=DOMINIO)
        self.assertEqual(nueva.status_code, 302)
        self.assertEqual(self.client.session['_auth_user_id'], str(self.usuario.pk))
        self.assertEqual(list(otras_cuentas.all()), estado_original)


class RegistroSeguroRecuperacionTests(SimpleTestCase):
    def test_filtra_rutas_sensibles_de_logs_django_y_wsgi(self):
        filtro = FiltroRecuperacion()
        ruta = RUTA_CONFIRMACION_FICTICIA
        acceso = LogRecord('django.server', 20, '', 0, 'GET %s HTTP/1.1', (ruta,), None)
        acceso_codificado = LogRecord('django.server', 20, '', 0, 'GET %s HTTP/1.1',
                                     (ruta.replace('reset', '%72eset'),), None)
        error = LogRecord('django.security', 40, '', 0, 'Error en solicitud', (), None)
        error.request = RequestFactory().post('/usuarios/recuperar-password/', {'email': CORREO})
        referido = LogRecord('django.request', 40, '', 0, 'Error en otra solicitud', (), None)
        referido.request = RequestFactory().get('/otra/', HTTP_REFERER=f'https://{DOMINIO}{ruta}')
        normal = LogRecord('django.server', 20, '', 0, 'GET /usuarios/login/ HTTP/1.1', (), None)
        self.assertFalse(filtro.filter(acceso))
        self.assertFalse(filtro.filter(acceso_codificado))
        self.assertFalse(filtro.filter(error))
        self.assertFalse(filtro.filter(referido))
        self.assertTrue(filtro.filter(normal))

    def test_gunicorn_configura_acceso_sin_url_y_filtra_errores_con_tokens(self):
        configuracion = run_path(str(settings.BASE_DIR.parent / 'gunicorn.conf.py'))
        self.assertEqual(configuracion['access_log_format'], '%(m)s %(s)s %(D)s')
        logger = Logger('gunicorn.error')
        configuracion['on_starting'](SimpleNamespace(log=SimpleNamespace(error_log=logger)))
        registro = LogRecord('gunicorn.error', 40, '', 0, 'Error handling request %s',
                             (RUTA_CONFIRMACION_FICTICIA,), None)
        self.assertFalse(logger.filter(registro))


class LimitesRecuperacionTests(TestCase):
    def test_normaliza_correos_persiste_solo_hmac_y_vence_la_ventana(self):
        ahora = timezone.now()
        with patch('usuarios.limites_recuperacion.timezone.now', return_value=ahora):
            self.assertTrue(admitir_solicitud('JÓSE@EXAMPLE.TEST'))
            self.assertTrue(admitir_solicitud('jóse@example.test'))
            self.assertFalse(admitir_solicitud('JÓSE@example.test'))
        registro = Session.objects.get(session_key__startswith='reset:')
        self.assertNotIn('@', registro.session_data)
        self.assertLess(len(registro.session_key), 8)
        esperado = ahora + timedelta(minutes=30)
        self.assertEqual(registro.expire_date, esperado)
        with patch('usuarios.limites_recuperacion.timezone.now', return_value=esperado):
            self.assertTrue(admitir_solicitud('jóse@example.test'))

    def test_cookies_reservadas_no_se_convierten_en_sesiones_ni_se_borran_al_iniciar_sesion(self):
        cuenta = User.objects.create_user('reservada', 'reservada@example.test', password=CLAVE_ANTERIOR)
        self.assertTrue(admitir_solicitud(cuenta.email))
        self.assertTrue(reservar_envio())
        for clave in (CONTADOR_SOLICITUDES, CONTADOR_ENVIOS):
            with self.subTest(clave=clave):
                self.assertIsNone(SessionStore(session_key=clave).session_key)
                estado = Session.objects.get(pk=clave).session_data
                cliente = Client()
                cliente.cookies[settings.SESSION_COOKIE_NAME] = clave
                self.assertNotIn('_auth_user_id', cliente.session)
                respuesta = cliente.post(
                    reverse('usuarios:login'), {'username': cuenta.username, 'password': CLAVE_ANTERIOR},
                )
                self.assertEqual(respuesta.status_code, 302)
                self.assertEqual(cliente.session['_auth_user_id'], str(cuenta.pk))
                self.assertEqual(Session.objects.get(pk=clave).session_data, estado)

    def test_clearsessions_elimina_contador_expirado_y_conserva_sesion_activa(self):
        usuario = User.objects.create_user('vigente')
        self.client.force_login(usuario)
        clave_activa = self.client.session.session_key
        self.assertTrue(admitir_solicitud('caducada@example.test'))
        self.assertTrue(reservar_envio())
        Session.objects.filter(pk=CONTADOR_SOLICITUDES).update(expire_date=timezone.now() - timedelta(seconds=1))

        call_command('clearsessions', verbosity=0)

        self.assertFalse(Session.objects.filter(pk=CONTADOR_SOLICITUDES).exists())
        self.assertTrue(Session.objects.filter(pk=CONTADOR_ENVIOS).exists())
        self.assertEqual(self.client.session.session_key, clave_activa)
        self.assertEqual(self.client.session['_auth_user_id'], str(usuario.pk))
        self.assertTrue(admitir_solicitud('caducada@example.test'))

    def test_limite_global_de_solicitudes_acota_direcciones_distintas(self):
        for i in range(30):
            self.assertTrue(admitir_solicitud(f'prueba-{i}@example.test'))
        self.assertFalse(admitir_solicitud('distinta@example.test'))

    def test_tope_de_envios_en_cinco_minutos_y_en_24_horas(self):
        inicio = timezone.now()
        for bloque in range(12):
            ahora = inicio + timedelta(minutes=5 * bloque)
            with patch('usuarios.limites_recuperacion.timezone.now', return_value=ahora):
                for _ in range(20):
                    self.assertTrue(reservar_envio())
                self.assertFalse(reservar_envio())
        with patch('usuarios.limites_recuperacion.timezone.now', return_value=inicio + timedelta(hours=23)):
            self.assertFalse(reservar_envio())
        with patch('usuarios.limites_recuperacion.timezone.now', return_value=inicio + timedelta(hours=24)):
            self.assertTrue(reservar_envio())


class LimitesConcurrentesRecuperacionTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_varias_conexiones_reclaman_un_trabajo_una_sola_vez(self):
        barrera = Barrier(8)
        identificador, vence = token_hex(16), int(time()) + 900

        def reclamar(_):
            try:
                barrera.wait(timeout=10)
                return reclamar_trabajo(identificador, vence)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=8) as ejecutor:
            resultados = list(ejecutor.map(reclamar, range(8)))
        self.assertEqual(resultados.count(True), 1)
        self.assertEqual(resultados.count(False), 7)

    @skipUnlessDBFeature('has_select_for_update')
    def test_varias_conexiones_comparten_tope_desde_la_primera_insercion(self):
        barrera = Barrier(8)

        def solicitar(_):
            try:
                barrera.wait(timeout=10)
                return admitir_solicitud('compartida@example.test')
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=8) as procesos:
            resultados = list(procesos.map(solicitar, range(8)))
        self.assertEqual(sum(resultados), 2)
        self.assertEqual(Session.objects.filter(session_key__startswith='reset:').count(), 1)

    @skipUnlessDBFeature('has_select_for_update')
    def test_bloqueo_del_contador_no_bloquea_escritura_de_una_sesion_autenticada(self):
        usuario = User.objects.create_user('otro-proceso')
        self.client.force_login(usuario)
        clave = self.client.session.session_key
        self.assertTrue(admitir_solicitud('reservada@example.test'))

        def actualizar_sesion():
            try:
                sesion = SessionStore(session_key=clave)
                sesion['prueba_concurrencia'] = True
                sesion.save()
                return sesion['_auth_user_id']
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as ejecutor:
            with transaction.atomic():
                Session.objects.select_for_update().get(pk=CONTADOR_SOLICITUDES)
                resultado = ejecutor.submit(actualizar_sesion)
                self.assertEqual(resultado.result(timeout=5), str(usuario.pk))


@override_settings(
    CUTLESS_ENV='development',
    ALLOWED_HOSTS=['127.0.0.1'],
    BREVO_RECOVERY_ENABLED=False,
    BREVO_API_KEY=CLAVE_DE_PRUEBA,
    BREVO_SENDER_EMAIL=REMITENTE,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class PruebaLocalBrevoTests(TestCase):
    def extraer_csrf(self, respuesta):
        campo = re.search(rb'name="csrfmiddlewaretoken" value="([^"]+)"', respuesta.content)
        self.assertIsNotNone(campo)
        return campo[1].decode()

    @patch('usuarios.recuperacion.HTTPSConnection', autospec=True)
    def test_solicitud_local_con_csrf_envio_simulado_y_restablecimiento(self, https):
        origen = 'http://127.0.0.1:8765'
        self.assertNotIn(origen, settings.CSRF_TRUSTED_ORIGINS)
        usuario = User.objects.create_user('recuperacion-prueba', CORREO, CLAVE_ANTERIOR)
        herramienta = run_path(str(settings.BASE_DIR.parent / 'tools' / 'probar_recuperacion_brevo.py'))
        asunto, texto, html = herramienta['preparar_correo'](CORREO, origen)
        https.assert_not_called()

        https.return_value.getresponse.return_value.status = 201
        self.assertTrue(enviar_correo_brevo(CORREO, asunto, texto, html))
        https.assert_called_once_with('api.brevo.com', timeout=5)
        datos = json.loads(https.return_value.request.call_args.kwargs['body'])
        enlace = next(linea for linea in datos['textContent'].splitlines() if linea.startswith(f'{origen}/'))
        self.assertIn(f'href="{enlace}"', datos['htmlContent'])

        cliente = Client(enforce_csrf_checks=True, HTTP_HOST=urlsplit(origen).netloc)
        redireccion = cliente.get(urlsplit(enlace).path)
        self.assertEqual(redireccion.status_code, 302)
        self.assertIn('/set-password/', redireccion.url)
        self.assertNotIn(urlsplit(enlace).path.split('/')[-2], redireccion.url)
        self.assertEqual(redireccion.headers['Referrer-Policy'], 'no-referrer')
        self.assertIn(settings.SESSION_COOKIE_NAME, redireccion.cookies)
        formulario = cliente.get(redireccion.url)
        self.assertEqual(formulario.status_code, 200)
        self.assertIn(settings.CSRF_COOKIE_NAME, formulario.cookies)
        nueva = token_urlsafe(24)
        contrasenas = {'new_password1': nueva, 'new_password2': nueva}
        datos = {**contrasenas, 'csrfmiddlewaretoken': self.extraer_csrf(formulario)}
        for origen_invalido in ('null', 'http://127.0.0.1:8766'):
            with self.subTest(origen=origen_invalido), self.assertLogs('django.security.csrf', 'WARNING') as log:
                rechazo = cliente.post(redireccion.url, datos, HTTP_ORIGIN=origen_invalido)
                self.assertEqual(rechazo.status_code, 403)
                self.assertIn(f'Origin checking failed - {origen_invalido}', log.output[0])
        with self.assertLogs('django.security.csrf', 'WARNING') as log:
            rechazo = cliente.post(redireccion.url, contrasenas, HTTP_ORIGIN=origen)
        self.assertEqual(rechazo.status_code, 403)
        self.assertIn('CSRF token missing', log.output[0])
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password(CLAVE_ANTERIOR))

        # Client no calcula Origin. Reproduce lo que hace Chromium al enviar el formulario.
        origen_post = 'null' if formulario.headers['Referrer-Policy'] == 'no-referrer' else origen
        cambio = cliente.post(redireccion.url, datos, HTTP_ORIGIN=origen_post)
        self.assertEqual(cambio.status_code, 302)
        self.assertEqual(cambio.url, reverse('usuarios:login'))
        self.assertEqual(formulario.headers['Referrer-Policy'], 'same-origin')
        usuario.refresh_from_db()
        self.assertTrue(usuario.check_password(nueva))

        login = cliente.get(cambio.url)
        acceso = {'username': usuario.username, 'csrfmiddlewaretoken': self.extraer_csrf(login)}
        antigua = cliente.post(cambio.url, {**acceso, 'password': CLAVE_ANTERIOR}, HTTP_ORIGIN=origen)
        self.assertEqual(antigua.status_code, 200)
        self.assertNotIn('_auth_user_id', cliente.session)
        nueva_sesion = cliente.post(cambio.url, {**acceso, 'password': nueva}, HTTP_ORIGIN=origen)
        self.assertEqual(nueva_sesion.status_code, 302)
        self.assertEqual(cliente.session['_auth_user_id'], str(usuario.pk))
        reuso = Client(enforce_csrf_checks=True, HTTP_HOST=urlsplit(origen).netloc).get(urlsplit(enlace).path)
        self.assertEqual(reuso.url, reverse('usuarios:recuperar_password'))
        self.assertEqual(reuso.headers['Referrer-Policy'], 'no-referrer')
