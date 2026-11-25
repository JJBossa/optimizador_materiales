"""Estado operativo y vigencia de proyectos, sin escrituras por el paso del tiempo."""
from django.db.models import Case, CharField, F, Q, Value, When
from django.utils import timezone

from .calendario import fecha_comercial


ESTADOS_VISIBLES = (
    ('planificacion', 'Planificación'),
    ('en_proceso', 'En proceso'),
    ('atrasado', 'Atrasado'),
    ('completado', 'Completado'),
    ('cancelado', 'Cancelado'),
)
TRANSICIONES = {
    'planificacion': {'iniciar': 'en_proceso', 'cancelar': 'cancelado'},
    'en_proceso': {'completar': 'completado', 'cancelar': 'cancelado'},
}
ACCIONES = {
    'iniciar': 'Iniciar proyecto',
    'completar': 'Completar proyecto',
    'cancelar': 'Cancelar proyecto',
}


def _condicion_atraso(hoy):
    return Q(estado__in=TRANSICIONES, fecha_fin__lt=hoy)


def proyectos_atrasados(proyectos, *, hoy=None):
    return proyectos.filter(_condicion_atraso(hoy if hoy is not None else fecha_comercial()))


def con_estado_efectivo(proyectos, *, hoy=None):
    return proyectos.annotate(estado_efectivo=Case(
        When(_condicion_atraso(hoy if hoy is not None else fecha_comercial()), then=Value('atrasado')),
        default=F('estado'),
        output_field=CharField(),
    ))


def inicios_planificados(proyectos, *, hasta, desde=None):
    """Proyectos pendientes de iniciar con fecha dentro del intervalo inclusivo."""
    programados = proyectos.filter(estado='planificacion', fecha_inicio__lte=hasta)
    return programados if desde is None else programados.filter(fecha_inicio__gte=desde)


def finales_planificados(proyectos, *, hasta, desde=None):
    """Proyectos activos con finalización estimada dentro del intervalo inclusivo."""
    programados = proyectos.filter(estado__in=TRANSICIONES, fecha_fin__lte=hasta)
    return programados if desde is None else programados.filter(fecha_fin__gte=desde)


def registrar_transicion(proyectos, *, origen, accion):
    destino = TRANSICIONES.get(origen, {}).get(accion)
    if destino is None:
        return None
    if proyectos.filter(estado=origen).update(estado=destino, fecha_actualizacion=timezone.now()):
        return destino
    return None
