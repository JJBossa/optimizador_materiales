import base64
import hmac
import json
import logging
import re
from contextlib import closing
from http.client import HTTPException, HTTPSConnection
from secrets import token_bytes
from time import time
from uuid import uuid4

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.core.exceptions import RequestDataTooBig, ValidationError
from django.core.validators import validate_email
from django.db import DatabaseError
from django.http import HttpResponse
from django.http.request import RawPostDataException
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_POST

from .limites_recuperacion import REINTENTO_SEGUNDOS, cambiar_trabajo, reclamar_trabajo


logger = logging.getLogger('usuarios.recuperacion')
RUTA_CONSUMIDOR = '/usuarios/interno/recuperacion-cola/'
VIGENCIA_SEGUNDOS = 900
MAX_CUERPO = 2048


def claves_configuradas():
    cifrado = settings.RECOVERY_QUEUE_ENCRYPTION_KEY
    firma = settings.RECOVERY_QUEUE_HMAC_KEY
    return (
        re.fullmatch(r'[0-9a-fA-F]{64}', cifrado) is not None
        and re.fullmatch(r'[0-9a-fA-F]{64}', firma) is not None
        and cifrado.lower() != firma.lower()
    )


def productor_configurado():
    return (
        claves_configuradas()
        and re.fullmatch(r'[0-9a-f]{32}', settings.RECOVERY_QUEUE_ACCOUNT_ID) is not None
        and re.fullmatch(r'[0-9a-f]{32}', settings.RECOVERY_QUEUE_ID) is not None
        and bool(settings.RECOVERY_QUEUE_API_TOKEN)
    )


def _datos_asociados(identificador, vence):
    return f'cutless-recuperacion/v1/{identificador}/{vence}'.encode('ascii')


@sensitive_variables()
def crear_sobre(correo):
    identificador = uuid4().hex
    vence = int(time()) + VIGENCIA_SEGUNDOS
    nonce = token_bytes(12)
    cifrador = AESGCM(bytes.fromhex(settings.RECOVERY_QUEUE_ENCRYPTION_KEY))
    cifrado = cifrador.encrypt(nonce, json.dumps({'email': correo}, ensure_ascii=False).encode('utf-8'),
                              _datos_asociados(identificador, vence))
    return {
        'v': 1, 'id': identificador, 'exp': vence,
        'nonce': base64.urlsafe_b64encode(nonce).decode('ascii'),
        'data': base64.urlsafe_b64encode(cifrado).decode('ascii'),
    }


@sensitive_variables()
def publicar_solicitud(correo):
    cuenta, cola = settings.RECOVERY_QUEUE_ACCOUNT_ID, settings.RECOVERY_QUEUE_ID
    ruta = f'/client/v4/accounts/{cuenta}/queues/{cola}/messages'
    cuerpo = json.dumps({'body': crear_sobre(correo), 'content_type': 'json'}).encode('utf-8')
    try:
        with closing(HTTPSConnection('api.cloudflare.com', timeout=3)) as conexion:
            conexion.request('POST', ruta, body=cuerpo, headers={
                'Authorization': f'Bearer {settings.RECOVERY_QUEUE_API_TOKEN}',
                'Content-Type': 'application/json',
            })
            respuesta = conexion.getresponse()
            if respuesta.status == 200:
                resultado = json.loads(respuesta.read(4096))
                if isinstance(resultado, dict) and resultado.get('success') is True:
                    logger.info('cola_recuperacion_publicada')
                    return
            logger.warning('cola_recuperacion_publicacion_rechazada')
    except (OSError, HTTPException, ValueError):
        logger.warning('cola_recuperacion_publicacion_no_confirmada')


def _firma_valida(request, cuerpo):
    fecha = request.headers.get('X-Cutless-Timestamp', '')
    firma = request.headers.get('X-Cutless-Signature', '')
    if not re.fullmatch(r'[0-9]{10}', fecha) or abs(int(time()) - int(fecha)) > 300:
        return False
    if not re.fullmatch(r'[0-9a-f]{64}', firma):
        return False
    mensaje = b'cutless.queue.callback.v1\n' + fecha.encode('ascii') + b'\n' + cuerpo
    esperada = hmac.digest(bytes.fromhex(settings.RECOVERY_QUEUE_HMAC_KEY), mensaje, 'sha256').hex()
    return hmac.compare_digest(esperada, firma)


def _sobre_valido(sobre):
    return (
        isinstance(sobre, dict) and set(sobre) == {'v', 'id', 'exp', 'nonce', 'data'}
        and type(sobre['v']) is int and sobre['v'] == 1 and type(sobre['exp']) is int
        and isinstance(sobre['id'], str) and re.fullmatch(r'[0-9a-f]{32}', sobre['id']) is not None
        and isinstance(sobre['nonce'], str) and re.fullmatch(r'[A-Za-z0-9_-]{16}', sobre['nonce']) is not None
        and isinstance(sobre['data'], str) and re.fullmatch(r'[A-Za-z0-9_-]+={0,2}', sobre['data']) is not None
    )


@sensitive_variables()
def _descifrar(sobre):
    nonce = base64.b64decode(sobre['nonce'], altchars=b'-_', validate=True)
    cifrado = base64.b64decode(sobre['data'], altchars=b'-_', validate=True)
    cifrador = AESGCM(bytes.fromhex(settings.RECOVERY_QUEUE_ENCRYPTION_KEY))
    claro = cifrador.decrypt(nonce, cifrado, _datos_asociados(sobre['id'], sobre['exp']))
    datos = json.loads(claro)
    if not isinstance(datos, dict) or set(datos) != {'email'}:
        raise ValueError
    correo = datos['email']
    if correo is not None:
        if not isinstance(correo, str) or len(correo) > 254:
            raise ValueError
        validate_email(correo)
    return correo


def _acuse(resultado):
    return HttpResponse(status=204, headers={'X-Cutless-Queue': 'ack-v1', 'X-Cutless-Outcome': resultado})


def _reintento(estado=503, espera=REINTENTO_SEGUNDOS):
    return HttpResponse(status=estado, headers={'Retry-After': str(espera)})


@csrf_exempt
@require_POST
@never_cache
@sensitive_variables()
def consumir_recuperacion(request, *, solo_sonda=False):
    # El Worker se autentica con una firma del cuerpo. Las cookies no intervienen.
    from .recuperacion import ResultadoEnvio, dominio_brevo_configurado, procesar_solicitud_brevo

    if not settings.RECOVERY_QUEUE_CONSUMER_ENABLED or not claves_configuradas():
        return _reintento()
    if not request.is_secure():
        return HttpResponse(status=403)
    request.get_host()
    longitud = request.META.get('CONTENT_LENGTH', '')
    if request.content_type != 'application/json' or not re.fullmatch(r'[0-9]{1,4}', longitud):
        return HttpResponse(status=400)
    if not 0 < int(longitud) <= MAX_CUERPO:
        return HttpResponse(status=413)
    try:
        cuerpo = request.body
    except (OSError, RawPostDataException, RequestDataTooBig):
        return HttpResponse(status=400)
    if len(cuerpo) != int(longitud):
        return HttpResponse(status=400)
    if not _firma_valida(request, cuerpo):
        return HttpResponse(status=403)

    try:
        sobre = json.loads(cuerpo)
        if not _sobre_valido(sobre):
            return HttpResponse(status=400)
        ahora = int(time())
        if sobre['exp'] > ahora + VIGENCIA_SEGUNDOS + 30:
            return HttpResponse(status=400)
        correo = _descifrar(sobre)
    except (ValueError, InvalidTag, ValidationError):
        return HttpResponse(status=400)
    if solo_sonda and correo is not None:
        return HttpResponse(status=403)
    if sobre['exp'] <= ahora:
        return _acuse('vencido')
    if correo is None:
        logger.info('cola_recuperacion_sonda_confirmada')
        return _acuse('sonda')

    dominio = dominio_brevo_configurado()
    if not dominio:
        return _reintento()
    reclamo = reclamar_trabajo(sobre['id'], sobre['exp'])
    if reclamo is None:
        return _reintento()
    if reclamo.estado == 'ocupado':
        return _reintento(espera=reclamo.espera)
    if reclamo.estado != 'preparando':
        return _acuse(reclamo.estado)

    try:
        resultado = procesar_solicitud_brevo(correo, dominio, reclamo)
    except DatabaseError:
        logger.warning('cola_recuperacion_fallo_despues_de_reclamar')
        resultado = ResultadoEnvio('reintentar', espera=REINTENTO_SEGUNDOS)
    if resultado.estado == 'sin_reclamo':
        return _reintento()
    reintentar = resultado.estado in ('reintentar', 'limitado')
    destino = 'espera' if reintentar else resultado.estado
    if not cambiar_trabajo(reclamo, resultado.anterior, destino, espera=resultado.espera):
        return _reintento()
    if reintentar:
        return _reintento(429 if resultado.estado == 'limitado' else 503, resultado.espera)
    if destino == 'ambiguo':
        logger.warning('cola_recuperacion_envio_ambiguo')
    return _acuse(destino)
