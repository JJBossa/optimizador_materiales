import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import ceil
from secrets import token_hex
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
RECLAMO_SEGUNDOS = 60
REINTENTO_SEGUNDOS = 90
ESTADOS_TERMINALES = frozenset({'finalizado', 'ambiguo', 'rechazado'})


@dataclass(frozen=True)
class ReclamoTrabajo:
    identificador: str
    estado: str
    titular: str = ''
    completados: tuple[str, ...] = ()
    espera: int = 0


def admitir_solicitud(correo):
    identificador = salted_hmac(
        'usuarios.recuperacion.correo', normalize('NFKC', correo).casefold(), algorithm='sha256',
    ).hexdigest()
    return _reservar(CONTADOR_SOLICITUDES, LIMITES_SOLICITUDES, identificador) == 0


def reservar_envio():
    """Devuelve 0 al reservar, los segundos de espera si se agotó el cupo, o None ante fallo."""
    return _reservar(CONTADOR_ENVIOS, LIMITES_ENVIOS)


def reservar_publicacion():
    return _reservar(CONTADOR_PUBLICACIONES, ((86400, 1000, False),)) == 0


def _actualizar_trabajos(operacion):
    try:
        # Debe quedar confirmado antes de iniciar el POST a Brevo.
        with transaction.atomic(durable=True):
            estado, _ = Session.objects.select_for_update().get_or_create(
                session_key=TRABAJOS_RECLAMADOS,
                defaults={'session_data': '{}', 'expire_date': timezone.now()},
            )
            ahora = timezone.now()
            instante = int(ahora.timestamp())
            historial = json.loads(estado.session_data) if estado.expire_date > ahora else {}
            trabajos = {
                clave: {'vence': valor, 'estado': 'finalizado'} if type(valor) is int else valor
                for clave, valor in historial.items()
            }
            vigentes = {clave: valor for clave, valor in trabajos.items() if valor['vence'] > instante}
            resultado = operacion(vigentes, instante)
            if vigentes != historial:
                estado.session_data = json.dumps(vigentes, separators=(',', ':'))
                vence = max((valor['vence'] for valor in vigentes.values()), default=instante)
                estado.expire_date = datetime.fromtimestamp(vence, UTC)
                estado.save(update_fields=['session_data', 'expire_date'])
            return resultado
    except (DatabaseError, ValueError, TypeError, AttributeError, KeyError):
        logger.warning('cola_recuperacion_registro_no_disponible')
        return None


def reclamar_trabajo(identificador, vence):
    def reclamar(trabajos, instante):
        if vence <= instante:
            return ReclamoTrabajo(identificador, 'vencido')
        trabajo = trabajos.get(identificador, {})
        estado = trabajo.get('estado')
        if estado in ESTADOS_TERMINALES:
            return ReclamoTrabajo(identificador, estado)
        espera = trabajo.get('hasta', 0) - instante
        if espera > 0:
            return ReclamoTrabajo(identificador, 'ocupado', espera=espera)
        if estado == 'enviando':
            # Ya se autorizó un POST. Vencer el reclamo no prueba que Brevo no lo recibió.
            trabajos[identificador] = {'vence': trabajo['vence'], 'estado': 'ambiguo'}
            logger.warning('cola_recuperacion_envio_incierto_por_interrupcion')
            return ReclamoTrabajo(identificador, 'ambiguo')
        if not trabajo and len(trabajos) >= 1000:
            return None
        titular = token_hex(16)
        completados = trabajo.get('completados', [])
        trabajos[identificador] = {
            'vence': vence, 'estado': 'preparando', 'titular': titular,
            'hasta': instante + RECLAMO_SEGUNDOS, 'completados': completados,
        }
        return ReclamoTrabajo(identificador, 'preparando', titular, tuple(completados))

    return _actualizar_trabajos(reclamar)


def cambiar_trabajo(reclamo, anterior, destino, *, espera=0, destinatario=None):
    def cambiar(trabajos, instante):
        trabajo = trabajos.get(reclamo.identificador)
        if not trabajo or trabajo.get('titular') != reclamo.titular or trabajo['estado'] != anterior:
            return False
        if destino == 'enviando' and trabajo['hasta'] <= instante:
            return False
        if destino in ESTADOS_TERMINALES:
            trabajos[reclamo.identificador] = {'vence': trabajo['vence'], 'estado': destino}
            return True
        hasta = instante + (espera if destino == 'espera' else RECLAMO_SEGUNDOS)
        completados = trabajo['completados']
        if destinatario:
            completados = [*completados, destinatario]
        trabajos[reclamo.identificador] = {
            **trabajo, 'estado': destino, 'hasta': hasta, 'completados': completados,
            'titular': '' if destino == 'espera' else reclamo.titular,
        }
        return True

    return _actualizar_trabajos(cambiar)


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
            espera = 0
            for ventana, limite, por_correo in reglas:
                usados = sorted(fecha for fecha, valor in vigentes
                                if fecha > instante - ventana and (not por_correo or valor == identificador))
                if len(usados) >= limite:
                    espera = max(espera, ceil(usados[-limite] + ventana - instante))
            if espera:
                return espera
            vigentes.append((instante, identificador))
            estado.session_data = json.dumps(vigentes, separators=(',', ':'))
            estado.expire_date = ahora + timedelta(seconds=ventana_maxima)
            estado.save(update_fields=['session_data', 'expire_date'])
    except (DatabaseError, ValueError, TypeError):
        logger.warning('brevo_recuperacion_limitador_no_disponible')
        return None
    return 0
