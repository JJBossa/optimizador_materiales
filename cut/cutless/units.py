"""Conversiones de unidades y simbolos para medidas."""

from decimal import Decimal

UNIDADES_CHOICES = [
    ('cm', 'Centímetros (cm)'),
    ('m', 'Metros (m)'),
    ('mm', 'Milímetros (mm)'),
    ('in', 'Pulgadas (in)'),
    ('ft', 'Pies (ft)'),
]
LADO_TABLERO_MIN_CM = 10
LADO_PIEZA_MIN_CM = 0.1
LADO_MAX_CM = 300

CENTIMETROS_POR_UNIDAD = {'cm': 1.0, 'm': 100.0, 'mm': 0.1, 'in': 2.54, 'ft': 30.48}


def _factor_cm(unidad):
    return CENTIMETROS_POR_UNIDAD.get('in' if unidad == 'pulgadas' else unidad, 1.0)


def convertir_a_cm(valor, unidad):
    """Convierte a cm, conservando seis decimales para cálculos internos."""
    return round(valor * _factor_cm(unidad), 6)


def convertir_desde_cm(valor_cm, unidad_destino):
    """Convierte centímetros a la unidad solicitada."""
    return round(valor_cm * (1.0 / _factor_cm(unidad_destino)), 6)


def medida_editable(cm, unidad):
    """Presenta una medida para reingreso sin redondear a seis decimales en la unidad elegida."""
    return float(Decimal(str(cm)) / Decimal(str(_factor_cm(unidad))))


def margen_en_mm(cm):
    mm = float(Decimal(str(cm)) * 10)
    return int(mm) if mm.is_integer() else mm


def margen_en_cm(mm):
    return float(Decimal(str(mm)) / 10)


def medida_tablero_en_cm(valor, unidad, cm_original=None, unidad_original=None):
    if cm_original is not None and unidad == unidad_original and valor == medida_editable(cm_original, unidad):
        return cm_original
    return convertir_a_cm(valor, unidad)


def obtener_factor_area_desde_cm2(unidad):
    """Factor de cm² a la unidad², sin redondear el factor lineal."""
    return 1.0 / (_factor_cm(unidad) ** 2)


def obtener_simbolo_unidad(unidad):
    if unidad == 'pulgadas':
        unidad = 'in'
    return unidad if unidad in CENTIMETROS_POR_UNIDAD else 'cm'


def obtener_simbolo_area(unidad):
    return f'{obtener_simbolo_unidad(unidad)}²'
