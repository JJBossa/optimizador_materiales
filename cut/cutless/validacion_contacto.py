import re
import unicodedata
from itertools import cycle

import phonenumbers
from babel import Locale
from django.core.exceptions import ValidationError


PAIS_TELEFONO_PREDETERMINADO = 'CL'


def _opciones_pais():
    paises = Locale.parse('es_CL').territories
    opciones = []
    for region in phonenumbers.SUPPORTED_REGIONS:
        nombre = paises.get(region, region)
        bandera = ''.join(chr(0x1F1E6 + ord(letra) - ord('A')) for letra in region)
        prefijo = phonenumbers.country_code_for_region(region)
        opciones.append((region, nombre, f'{bandera} {nombre} (+{prefijo})'))
    opciones.sort(key=lambda opcion: unicodedata.normalize('NFKD', opcion[1]).casefold())
    return [(region, etiqueta) for region, _, etiqueta in opciones]


PAISES_TELEFONICOS = _opciones_pais()


def pais_para_telefono_guardado(telefono):
    if telefono.startswith('+'):
        try:
            numero = phonenumbers.parse(telefono, None)
        except phonenumbers.NumberParseException:
            pass
        else:
            region = phonenumbers.region_code_for_number(numero)
            if region in phonenumbers.SUPPORTED_REGIONS:
                return region
    return PAIS_TELEFONO_PREDETERMINADO


def normalizar_telefono(telefono, pais):
    if not telefono:
        return ''
    if not re.fullmatch(r'\+?[0-9(). \u00a0\u202f-]+', telefono):
        raise ValidationError('Usa dígitos y, si quieres, espacios, guiones, puntos o paréntesis. '
                              'Escribe el prefijo internacional con +. No se admiten extensiones.', code='formato')

    telefono = telefono.replace('\u00a0', ' ').replace('\u202f', ' ')
    internacional = telefono.startswith('+')
    try:
        numero = phonenumbers.parse(telefono, None if internacional else pais)
    except phonenumbers.NumberParseException:
        raise ValidationError('Escribe un teléfono válido con el prefijo correcto.', code='telefono_invalido') from None

    valido = (phonenumbers.is_valid_number(numero) if internacional
              else phonenumbers.is_valid_number_for_region(numero, pais))
    e164 = phonenumbers.format_number(numero, phonenumbers.PhoneNumberFormat.E164)
    if not valido or not re.fullmatch(r'\+[1-9][0-9]{1,14}', e164):
        mensaje = ('Escribe un teléfono válido con el prefijo internacional correcto.' if internacional
                   else 'Escribe un teléfono válido para el país seleccionado o ingresa el número completo con +.')
        raise ValidationError(mensaje, code='telefono_invalido')
    return e164


def normalizar_rut(rut):
    if not rut:
        return ''
    coincidencia = re.fullmatch(r'([0-9]{1,8}|[0-9]{1,3}\.[0-9]{3}|[0-9]{1,2}\.[0-9]{3}\.[0-9]{3})-?([0-9K])', rut.upper())
    if not coincidencia:
        raise ValidationError('Escribe un RUT chileno con su dígito verificador. Ej.: 12.345.678-5.', code='formato')
    cuerpo, verificador = coincidencia.groups()
    cuerpo = cuerpo.replace('.', '')
    if int(cuerpo) == 0:
        raise ValidationError('El número del RUT debe ser mayor que cero.', code='formato')

    suma = sum(int(digito) * factor for digito, factor in zip(reversed(cuerpo), cycle(range(2, 8))))
    # El resto complementario 0 representa 0 y el 10 se escribe K.
    esperado = '0123456789K'[-suma % 11]
    if verificador != esperado:
        raise ValidationError('El dígito verificador del RUT no coincide. Revisa el número y el dígito final.',
                              code='digito_verificador')
    return f'{cuerpo}-{verificador}'


def clave_rut_cliente(rut):
    """Identidad comparable de un RUT chileno válido, incluidos valores históricos."""
    return normalizar_rut(rut.strip()).lstrip('0')
