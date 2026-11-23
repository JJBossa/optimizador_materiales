"""Nombres de países y territorios para direcciones, a partir de CLDR local."""
import json
from pathlib import Path
from unicodedata import normalize

from babel import Locale
from babel.core import get_global


NOMBRES_PAISES = {
    codigo: nombre
    for codigo, nombre in Locale('es').territories.items()
    if len(codigo) == 2 and codigo != 'ZZ' and codigo in get_global('territory_languages')
}


def nombre_comparable(nombre):
    return ''.join(c for c in normalize('NFKD', (nombre or '').casefold()) if c.isalnum())


def codigo_por_nombre(nombre, opciones):
    clave = nombre_comparable(nombre)
    candidatos = [codigo for codigo, etiqueta in opciones.items() if nombre_comparable(etiqueta) == clave]
    return candidatos[0] if len(candidatos) == 1 else nombre or ''


with Path(__file__).with_name('dpa_chile.json').open(encoding='utf-8') as archivo:
    DPA_CHILE = json.load(archivo)

REGIONES_CHILE = {codigo: region['nombre'] for codigo, region in DPA_CHILE.items()}
