"""Indicadores públicos de Findic.cl para el módulo de Presupuestos."""

import json
import re
from contextlib import closing
from datetime import date
from http.client import HTTPException, HTTPSConnection
from math import isfinite
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.utils import timezone


HOST = 'findic.cl'
RUTA = '/api/'
TIMEOUT = 2
MAX_RESPUESTA = 64 * 1024
CODIGOS = ('dolar', 'uf')
CHILE = ZoneInfo('America/Santiago')
CACHE_ACTUAL = 'presupuestos:indicadores:findic:v1:actual'
CACHE_RESPALDO = 'presupuestos:indicadores:findic:v1:respaldo'
CACHE_INTENTO = 'presupuestos:indicadores:findic:v1:intento'


def _validar_indicador(dato, hoy):
    if not isinstance(dato, dict):
        return None
    valor = dato.get('valor')
    if type(valor) not in (int, float) or valor <= 0:
        return None
    fecha = dato.get('fecha')
    if not isinstance(fecha, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', fecha):
        return None
    try:
        if not isfinite(valor):
            return None
        dia = date.fromisoformat(fecha)
    except (ValueError, OverflowError):
        return None
    if dia > hoy:
        return None
    return {'valor': valor, 'fecha': dia}


def _consultar(hoy):
    try:
        with closing(HTTPSConnection(HOST, timeout=TIMEOUT)) as conexion:
            conexion.request('GET', RUTA, headers={'Accept': 'application/json'})
            respuesta = conexion.getresponse()
            if respuesta.status != 200:
                return {}
            cuerpo = respuesta.read(MAX_RESPUESTA + 1)
        if len(cuerpo) > MAX_RESPUESTA:
            return {}
        datos = json.loads(cuerpo)
    except (OSError, HTTPException, ValueError, RecursionError):
        return {}
    if not isinstance(datos, dict):
        return {}
    return {
        codigo: indicador for codigo in CODIGOS
        if (indicador := _validar_indicador(datos.get(codigo), hoy)) is not None
    }


def obtener_indicadores():
    hoy = timezone.localdate(timezone=CHILE)
    datos = cache.get(CACHE_ACTUAL)
    desde_cache = True
    if datos is None:
        if cache.add(CACHE_INTENTO, True, timeout=60):
            datos = _consultar(hoy)
            if datos:
                cache.set(CACHE_RESPALDO, datos, timeout=24 * 60 * 60)
                cache.set(CACHE_ACTUAL, datos, timeout=15 * 60)
                desde_cache = False
        if not datos:
            datos = cache.get(CACHE_RESPALDO, {})
    return {
        'desde_cache': desde_cache and bool(datos),
        'indicadores': {
            codigo: {**dato, 'fecha_anterior': dato['fecha'] < hoy}
            for codigo, dato in datos.items()
        },
    }
