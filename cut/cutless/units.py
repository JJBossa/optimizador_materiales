"""Conversiones de unidades y simbolos para medidas."""

UNIDADES_CHOICES = [
    ('cm', 'Centímetros (cm)'),
    ('m', 'Metros (m)'),
    ('mm', 'Milímetros (mm)'),
    ('in', 'Pulgadas (in)'),
    ('ft', 'Pies (ft)'),
]
_CENTIMETROS_POR_UNIDAD = {'cm': 1.0, 'm': 100.0, 'mm': 0.1, 'in': 2.54, 'ft': 30.48}


def _factor_cm(unidad):
    return _CENTIMETROS_POR_UNIDAD.get('in' if unidad == 'pulgadas' else unidad, 1.0)


def convertir_a_cm(valor, unidad):
    """Convierte a cm, conservando seis decimales para cálculos internos."""
    return round(valor * _factor_cm(unidad), 6)


def convertir_desde_cm(valor_cm, unidad_destino):
    """Convierte centímetros a la unidad solicitada."""
    return round(valor_cm * (1.0 / _factor_cm(unidad_destino)), 6)


def obtener_factor_area_desde_cm2(unidad):
    """Factor de cm² a la unidad², sin redondear el factor lineal."""
    return 1.0 / (_factor_cm(unidad) ** 2)


def obtener_simbolo_unidad(unidad):
    if unidad == 'pulgadas':
        unidad = 'in'
    return unidad if unidad in _CENTIMETROS_POR_UNIDAD else 'cm'


def obtener_simbolo_area(unidad):
    return f'{obtener_simbolo_unidad(unidad)}²'
