"""Valida la forma de una dirección postal a partir del texto recibido."""
import re
from unicodedata import category, normalize

from django.core.exceptions import ValidationError


LETRA = r'[^\W\d_]'
BLOQUE_NUMERICO = rf'\d+(?: *{LETRA})?'
NUMERO_DOMICILIARIO = re.compile(
    rf'(?:{LETRA} *[-‐‑–]? *)?{BLOQUE_NUMERICO}'
    rf'(?: *[-‐‑–/] *(?:{BLOQUE_NUMERICO}|{LETRA}))?'
    r'(?: +(?:bis|ter|quater))?'
)


def tiene_controles_direccion(valor):
    # ZWNJ y ZWJ son necesarios para la escritura de algunos nombres.
    return any(category(c) in {'Cc', 'Cf', 'Cs', 'Zl', 'Zp'} and c not in '\u200c\u200d' for c in valor)


def validar_texto_direccion(valor, *, admite_calle_numerada=False):
    texto = normalize('NFC', valor)
    if not any(c.isalpha() or (admite_calle_numerada and c.isdecimal()) for c in texto):
        mensaje = ('Escribe un nombre de calle con letras o una calle numerada.'
                   if admite_calle_numerada else 'Escribe un nombre de lugar que contenga al menos una letra.')
        raise ValidationError(mensaje, code='contenido_direccion')
    if len(texto) >= 8 and texto[0].isalpha() and all(c.casefold() == texto[0].casefold() for c in texto):
        raise ValidationError('Escribe el nombre completo. Una sola letra repetida no es válida.',
                              code='repeticion_direccion')


def validar_numero_direccion(valor):
    comparable = normalize('NFKC', valor).casefold()
    if not (re.fullmatch(r's */ *n', comparable) or NUMERO_DOMICILIARIO.fullmatch(comparable)):
        raise ValidationError('Escribe un número de dirección como 100, 12-B o 100A. Si no tiene número, escribe S/N.',
                              code='numero_direccion')
