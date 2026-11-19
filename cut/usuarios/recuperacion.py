import json
import logging
import re
from contextlib import closing
from dataclasses import dataclass
from http.client import HTTPException, HTTPSConnection
from time import time

from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm
from django.core.exceptions import ValidationError
from django.core.validators import DomainNameValidator, validate_email
from django.http.request import validate_host
from django.template.loader import render_to_string
from django.utils.crypto import salted_hmac
from django.utils.http import parse_http_date_safe
from django.views.decorators.debug import sensitive_variables

from .cola_recuperacion import productor_configurado, publicar_solicitud
from .limites_recuperacion import (
    REINTENTO_SEGUNDOS, admitir_solicitud, cambiar_trabajo, reservar_envio, reservar_publicacion,
)


logger = logging.getLogger(__name__)
validar_dominio = DomainNameValidator(accept_idna=False)


@dataclass(frozen=True)
class ResultadoEnvio:
    estado: str
    anterior: str = 'preparando'
    espera: int = 0


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
def procesar_solicitud_brevo(correo, dominio, reclamo):
    formulario = FormularioRecuperacionBrevo({'email': correo}, reclamo=reclamo)
    if formulario.is_valid():
        _guardar(formulario, domain_override=dominio, use_https=True)
    return formulario.resultado


class FormularioRecuperacionBrevo(PasswordResetForm):
    def __init__(self, *args, reclamo, **kwargs):
        super().__init__(*args, **kwargs)
        self.reclamo = reclamo
        self.resultado = ResultadoEnvio('finalizado')

    @sensitive_variables()
    def send_mail(self, subject_template_name, email_template_name, context, from_email,
                  to_email, html_email_template_name=None):
        if self.resultado.estado != 'finalizado':
            return
        destinatario = salted_hmac(
            'usuarios.recuperacion.destinatario', f'{self.reclamo.identificador}:{context["user"].pk}',
            algorithm='sha256',
        ).hexdigest()
        if destinatario in self.reclamo.completados:
            return
        asunto = ''.join(render_to_string(subject_template_name, context).splitlines())
        texto = render_to_string(email_template_name, context)
        html = render_to_string(html_email_template_name, context) if html_email_template_name else None
        contenido = _contenido_brevo(to_email, asunto, texto, html)
        resultado = enviar_brevo(contenido, autorizar_envio=self._autorizar_envio)
        if resultado.estado != 'aceptado':
            self.resultado = resultado
        elif not cambiar_trabajo(self.reclamo, 'enviando', 'preparando', destinatario=destinatario):
            logger.warning('cola_recuperacion_aceptacion_no_persistida')
            self.resultado = ResultadoEnvio('sin_reclamo')

    def _autorizar_envio(self):
        espera = reservar_envio()
        if espera is None:
            return ResultadoEnvio('reintentar', espera=REINTENTO_SEGUNDOS)
        if espera:
            return ResultadoEnvio('limitado', espera=espera)
        if not cambiar_trabajo(self.reclamo, 'preparando', 'enviando'):
            return ResultadoEnvio('sin_reclamo')
        return None


@sensitive_variables()
def _contenido_brevo(destinatario, asunto, texto, html):
    contenido = {
        'sender': {'email': settings.BREVO_SENDER_EMAIL, 'name': settings.BREVO_SENDER_NAME},
        'to': [{'email': destinatario, 'contactPixelTrackingConsent': False}],
        'tags': ['cutless-recuperacion'],
        'subject': asunto,
        'textContent': texto,
    }
    if html is not None:
        contenido['htmlContent'] = html
    return contenido


@sensitive_variables()
def enviar_correo_brevo(destinatario, asunto, texto, html):
    return enviar_brevo(_contenido_brevo(destinatario, asunto, texto, html)).estado == 'aceptado'


def _espera_brevo(respuesta):
    esperas = []
    for nombre in ('Retry-After', 'X-Sib-Ratelimit-Reset'):
        valor = respuesta.getheader(nombre)
        if not isinstance(valor, str):
            continue
        if re.fullmatch(r'[0-9]{1,8}', valor):
            esperas.append(max(1, int(valor)))
        elif nombre == 'Retry-After':
            fecha = parse_http_date_safe(valor)
            if fecha is not None:
                esperas.append(max(1, fecha - int(time())))
    return max(esperas, default=REINTENTO_SEGUNDOS)


@sensitive_variables()
def enviar_brevo(contenido, *, autorizar_envio=None):
    # HTTPSConnection verifica TLS y no sigue redirecciones con la clave API.
    cuerpo = json.dumps(contenido).encode('utf-8')
    iniciada = False
    try:
        with closing(HTTPSConnection('api.brevo.com', timeout=5)) as conexion:
            conexion.connect()
            if autorizar_envio:
                bloqueo = autorizar_envio()
                if bloqueo:
                    return bloqueo
            iniciada = True
            conexion.request(
                'POST', '/v3/smtp/email',
                body=cuerpo,
                headers={'api-key': settings.BREVO_API_KEY, 'Content-Type': 'application/json'},
            )
            respuesta = conexion.getresponse()
            estado = respuesta.status
            espera = _espera_brevo(respuesta) if estado == 429 else 0
    except TimeoutError:
        logger.warning('brevo_recuperacion_tiempo_agotado')
    except (OSError, HTTPException, ValueError):
        logger.warning('brevo_recuperacion_error_transporte')
    else:
        # Un 201 confirma la aceptación. La entrega se confirma aparte.
        if estado == 201:
            logger.info('brevo_recuperacion_aceptada entrega=no_confirmada')
            return ResultadoEnvio('aceptado', 'enviando')
        if estado == 429:
            logger.warning('brevo_recuperacion_limite estado=%d', estado)
            return ResultadoEnvio('limitado', 'enviando', espera)
        if estado in (401, 403):
            logger.warning('brevo_recuperacion_autenticacion_o_permisos estado=%d', estado)
        else:
            logger.warning('brevo_recuperacion_respuesta_inesperada estado=%d', estado)
        if estado in (400, 401, 403, 404, 405, 413, 415, 422):
            return ResultadoEnvio('rechazado', 'enviando')
    if iniciada:
        return ResultadoEnvio('ambiguo', 'enviando')
    return ResultadoEnvio('reintentar', espera=REINTENTO_SEGUNDOS)
