"""Nombres de países y territorios para direcciones, a partir de CLDR local."""
from babel import Locale
from babel.core import get_global


NOMBRES_PAISES = {
    codigo: nombre
    for codigo, nombre in Locale('es').territories.items()
    if len(codigo) == 2 and codigo != 'ZZ' and codigo in get_global('territory_languages')
}
