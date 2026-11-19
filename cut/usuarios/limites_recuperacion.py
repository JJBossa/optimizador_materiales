import json
import logging
from datetime import timedelta
from unicodedata import normalize

from django.contrib.sessions.models import Session
from django.db import DatabaseError, transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac


logger = logging.getLogger('usuarios.recuperacion')

# (ventana en segundos, máximo, aplicar por dirección)
LIMITES_SOLICITUDES = ((300, 30, False), (1800, 2, True))
LIMITES_ENVIOS = ((300, 20, False), (86400, 240, False))

# Django 5.2 rechaza como cookie toda clave de sesión de menos de 8 caracteres.
CONTADOR_SOLICITUDES = 'reset:r'
CONTADOR_ENVIOS = 'reset:e'
CONTADOR_PUBLICACIONES = 'reset:q'
TRABAJOS_RECLAMADOS = 'reset:j'


def admitir_solicitud(correo):
    identificador = salted_hmac(
        'usuarios.recuperacion.correo', normalize('NFKC', correo).casefold(), algorithm='sha256',
    ).hexdigest()
    return _reservar(CONTADOR_SOLICITUDES, LIMITES_SOLICITUDES, identificador)


def reservar_envio():
    return _reservar(CONTADOR_ENVIOS, LIMITES_ENVIOS)


def reservar_publicacion():
    return _reservar(CONTADOR_PUBLICACIONES, ((86400, 1000, False),))


def reclamar_trabajo(identificador, vence):
    """True si lo reclama, False si ya fue reclamado o venció, None si no se pudo registrar."""
    try:
        with transaction.atomic():
            estado, _ = Session.objects.select_for_update().get_or_create(
                session_key=TRABAJOS_RECLAMADOS,
                defaults={'session_data': '{}', 'expire_date': timezone.now()},
            )
            ahora = timezone.now()
            instante = ahora.timestamp()
            historial = json.loads(estado.session_data) if estado.expire_date > ahora else {}
            vigentes = {clave: fecha for clave, fecha in historial.items() if fecha > instante}
            if identificador in vigentes or vence <= instante:
                return False
            if len(vigentes) >= 1000:
                return None
            vigentes[identificador] = vence
            estado.session_data = json.dumps(vigentes, separators=(',', ':'))
            estado.expire_date = ahora + timedelta(seconds=max(vigentes.values()) - instante)
            estado.save(update_fields=['session_data', 'expire_date'])
    except (DatabaseError, ValueError, TypeError, AttributeError):
        logger.warning('cola_recuperacion_registro_no_disponible')
        return None
    return True


def _reservar(clave, reglas, identificador=''):
    ventana_maxima = max(ventana for ventana, _, _ in reglas)
    try:
        with transaction.atomic():
            estado, _ = Session.objects.select_for_update().get_or_create(
                session_key=clave,
                defaults={'session_data': '[]', 'expire_date': timezone.now()},
            )
            ahora = timezone.now()
            instante = ahora.timestamp()
            historial = json.loads(estado.session_data) if estado.expire_date > ahora else []
            vigentes = [(fecha, valor) for fecha, valor in historial if fecha > instante - ventana_maxima]
            for ventana, limite, por_correo in reglas:
                usados = sum(
                    fecha > instante - ventana and (not por_correo or valor == identificador)
                    for fecha, valor in vigentes
                )
                if usados >= limite:
                    return False
            vigentes.append((instante, identificador))
            estado.session_data = json.dumps(vigentes, separators=(',', ':'))
            estado.expire_date = ahora + timedelta(seconds=ventana_maxima)
            estado.save(update_fields=['session_data', 'expire_date'])
    except (DatabaseError, ValueError, TypeError):
        logger.warning('brevo_recuperacion_limitador_no_disponible')
        return False
    return True
