"""Sintaxis de entradas numéricas individuales de CutLess."""

import re
from decimal import Decimal

AGRUPACION_AMBIGUA = r'[+\-]?0*[1-9][0-9]{0,2}[.,][0-9]{3}'
FORMATO_DECIMAL = rf'(?!{AGRUPACION_AMBIGUA}$)[+\-]?(?:[0-9]+(?:[.,][0-9]+)?|[.,][0-9]+)'
FORMATO_ENTERO = r'[0-9]+'
AYUDA_DECIMAL = 'Usa coma o punto decimal, sin separadores de miles.'


def preparar_decimal(valor):
    """Desambigua valores iniciales numéricos. Conserva el texto recibido."""
    if isinstance(valor, (float, Decimal)):
        texto = str(valor)
        if re.fullmatch(AGRUPACION_AMBIGUA, texto):
            return f'{texto}0'
        if 'e' in texto.lower():
            return format(Decimal(texto), 'f')
    return valor


def preparar_importe(valor):
    """Quita ceros decimales de un importe para mostrarlo. Conserva los textos enviados."""
    if not isinstance(valor, Decimal) or not valor.is_finite():
        return valor
    if valor.is_zero():
        return Decimal(0)
    texto = format(valor, 'f')
    if '.' in texto:
        texto = texto.rstrip('0').rstrip('.')
    return Decimal(texto)
