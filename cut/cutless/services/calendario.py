"""Fecha civil para los flujos comerciales de CutLess."""
from zoneinfo import ZoneInfo

from django.utils import timezone


ZONA_CHILE = ZoneInfo('America/Santiago')


def fecha_comercial():
    return timezone.localdate(timezone=ZONA_CHILE)
