"""Reglas del ciclo de vida de presupuestos y fecha comercial de Chile."""

from django.utils import timezone

from .calendario import fecha_comercial


ESTADOS_VENCIBLES = ('emitido', 'enviado')
TRANSICIONES_REGISTRO = {
    'emitido': ('enviado', 'aceptado', 'rechazado'),
    'enviado': ('aceptado', 'rechazado'),
}


def fecha_vencida(fecha, *, hoy=None):
    return fecha < (hoy if hoy is not None else fecha_comercial())


def estado_efectivo(presupuesto, *, hoy=None):
    if presupuesto.estado in ESTADOS_VENCIBLES and fecha_vencida(presupuesto.fecha_validez, hoy=hoy):
        return 'vencido'
    return presupuesto.estado


def presupuestos_por_vencer(presupuestos, *, antes_de):
    """Selecciona cotizaciones abiertas con validez anterior al límite indicado."""
    return presupuestos.filter(estado__in=ESTADOS_VENCIBLES, fecha_validez__lt=antes_de)


def sincronizar_vencimientos(presupuestos, *, hoy=None, simulacion=False):
    elegibles = presupuestos_por_vencer(presupuestos, antes_de=hoy if hoy is not None else fecha_comercial())
    if simulacion:
        return elegibles.count()
    # El UPDATE vuelve a comprobar el estado y la fecha, incluso tras esperar por un bloqueo.
    return elegibles.update(estado='vencido')


def registrar_transicion(presupuestos, *, origen, destino, hoy):
    if destino not in TRANSICIONES_REGISTRO.get(origen, ()):
        return 0
    return presupuestos.filter(estado=origen, fecha_validez__gte=hoy).update(
        estado=destino, fecha_actualizacion=timezone.now(),
    )
