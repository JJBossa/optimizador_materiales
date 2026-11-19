import json
import logging
from contextlib import closing
from http.client import HTTPException, HTTPSConnection

from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm
from django.core.exceptions import ValidationError
from django.core.validators import DomainNameValidator, validate_email
from django.http.request import validate_host
from django.template.loader import render_to_string
from django.views.decorators.debug import sensitive_variables

from .cola_recuperacion import productor_configurado, publicar_solicitud
from .limites_recuperacion import admitir_solicitud, reservar_envio, reservar_publicacion


logger = logging.getLogger(__name__)
validar_dominio = DomainNameValidator(accept_idna=False)


class FormularioRecuperacion(PasswordResetForm):
    def enviar(self, request):
        request.get_host()
        if settings.CUTLESS_ENV != 'production':
            _guardar(self, request=request, use_https=request.is_secure())
            return
        if not settings.BREVO_RECOVERY_ENABLED:
            return
        if not dominio_brevo_configurado():
            logger.warning('brevo_recuperacion_configuracion_incompleta')
            return
        if not settings.RECOVERY_QUEUE_CONSUMER_ENABLED or not productor_configurado():
            logger.warning('cola_recuperacion_configuracion_incompleta')
            return
        correo = self.cleaned_data['email']
        if admitir_solicitud(correo) and reservar_publicacion():
            publicar_solicitud(correo)


def dominio_brevo_configurado():
    dominio = settings.PASSWORD_RESET_HOST
    try:
        validar_dominio(dominio)
        validate_email(settings.BREVO_SENDER_EMAIL)
    except ValidationError:
        return None
    if validate_host(dominio, settings.ALLOWED_HOSTS) and settings.BREVO_API_KEY:
        return dominio
    return None


def _guardar(formulario, **parametros):
    formulario.save(
        subject_template_name='usuarios/reset_password_subject.txt',
        email_template_name='usuarios/reset_password_email.txt',
        html_email_template_name='usuarios/email_reset_password.html',
        **parametros,
    )


@sensitive_variables()
def procesar_solicitud_brevo(correo, dominio):
    formulario = FormularioRecuperacionBrevo({'email': correo})
    if formulario.is_valid():
        _guardar(formulario, domain_override=dominio, use_https=True)


class FormularioRecuperacionBrevo(PasswordResetForm):
    _envios_detenidos = False

    @sensitive_variables('context', 'asunto', 'texto', 'html', 'to_email')
    def send_mail(self, subject_template_name, email_template_name, context, from_email,
                  to_email, html_email_template_name=None):
        if self._envios_detenidos or not reservar_envio():
            self._envios_detenidos = True
            return
        asunto = ''.join(render_to_string(subject_template_name, context).splitlines())
        texto = render_to_string(email_template_name, context)
        html = render_to_string(html_email_template_name, context) if html_email_template_name else None
        self._envios_detenidos = not enviar_correo_brevo(to_email, asunto, texto, html)


@sensitive_variables()
def enviar_correo_brevo(destinatario, asunto, texto, html):
    contenido = {
        'sender': {'email': settings.BREVO_SENDER_EMAIL, 'name': settings.BREVO_SENDER_NAME},
        'to': [{'email': destinatario, 'contactPixelTrackingConsent': False}],
        'tags': ['cutless-recuperacion'],
        'subject': asunto,
        'textContent': texto,
    }
    if html is not None:
        contenido['htmlContent'] = html
    return enviar_brevo(contenido)


@sensitive_variables()
def enviar_brevo(contenido):
    # HTTPSConnection verifica TLS y no sigue redirecciones con la clave API.
    try:
        with closing(HTTPSConnection('api.brevo.com', timeout=5)) as conexion:
            conexion.request(
                'POST', '/v3/smtp/email',
                body=json.dumps(contenido).encode('utf-8'),
                headers={'api-key': settings.BREVO_API_KEY, 'Content-Type': 'application/json'},
            )
            estado = conexion.getresponse().status
    except TimeoutError:
        logger.warning('brevo_recuperacion_tiempo_agotado')
        return False
    except (OSError, HTTPException, ValueError):
        logger.warning('brevo_recuperacion_error_transporte')
        return False

    # Un 201 registra la aceptación de la solicitud por Brevo. La entrega se confirma aparte.
    if estado == 201:
        logger.info('brevo_recuperacion_aceptada entrega=no_confirmada')
        return True
    if estado in (401, 403):
        logger.warning('brevo_recuperacion_autenticacion_o_permisos estado=%d', estado)
    elif estado == 429:
        logger.warning('brevo_recuperacion_limite estado=%d', estado)
    else:
        logger.warning('brevo_recuperacion_respuesta_inesperada estado=%d', estado)
    return False
