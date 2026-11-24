"""Parseo de piezas y mensajes al usuario."""
import csv
import io
import json
import logging
import math
import re
from collections import Counter

from .formatos_numericos import FORMATO_DECIMAL, FORMATO_ENTERO, preparar_decimal
from .units import convertir_a_cm, convertir_desde_cm, obtener_simbolo_unidad

logger = logging.getLogger(__name__)

VERSION_PIEZAS = 'piezas:v1:'


class FormatoPiezasInvalido(ValueError):
    """El registro no se puede interpretar por completo y necesita revisión."""


def serializar_piezas(piezas):
    filas = [[p['nombre'], p['ancho'], p['alto'], p['cantidad']] for p in piezas]
    return VERSION_PIEZAS + json.dumps(filas, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


def filas_piezas(texto, *, csv_editable=False):
    if texto.startswith(VERSION_PIEZAS):
        try:
            filas = json.loads(texto[len(VERSION_PIEZAS):])
        except json.JSONDecodeError:
            # El prefijo también puede ser parte del primer nombre histórico.
            # El lector exige que todas las filas de esta alternativa sean válidas.
            pass
        else:
            if not isinstance(filas, list) or any(
                not isinstance(fila, list) or len(fila) != 4 or not isinstance(fila[0], str)
                for fila in filas
            ):
                raise FormatoPiezasInvalido('Se esperaba una lista JSON de piezas')
            yield from filas
            return

    if csv_editable:
        yield from (fila for fila in csv.reader(io.StringIO(texto), strict=True) if any(fila))
    else:
        yield from (linea.rsplit(',', 3) for linea in texto.splitlines() if linea.strip())


def piezas_como_csv(texto):
    salida = io.StringIO(newline='')
    escritor = csv.writer(salida)
    for pieza in parsear_piezas_desde_texto(texto, estricto=True):
        escritor.writerow([pieza['nombre'], preparar_decimal(pieza['ancho']),
                           preparar_decimal(pieza['alto']), pieza['cantidad']])
    return salida.getvalue()


def parsear_piezas_desde_texto(texto_piezas, unidad_medida='cm', *, estricto=False, csv_editable=False):
    piezas = []
    texto = texto_piezas or ''
    exigir_todas = estricto or texto.startswith(VERSION_PIEZAS)
    try:
        for numero, fila in enumerate(filas_piezas(texto, csv_editable=csv_editable), 1):
            try:
                if not isinstance(fila, (tuple, list)):
                    raise ValueError('Fila de piezas inválida')
                if len(fila) == 3:
                    fila = [f'Pieza {len(piezas) + 1}', *fila]
                if csv_editable:
                    for medida in fila[1:3]:
                        if isinstance(medida, str) and (',' in medida or not re.fullmatch(FORMATO_DECIMAL, medida.strip())):
                            raise ValueError('Usa punto decimal sin separadores de miles en CSV')
                    if not re.fullmatch(FORMATO_ENTERO, str(fila[3]).strip()):
                        raise ValueError('Cantidad no entera en el formulario')
                nombre, ancho, alto, cantidad = map(str, fila)
                ancho, alto, cantidad = float(ancho), float(alto), int(cantidad)
                if not (math.isfinite(ancho) and math.isfinite(alto) and ancho > 0 and alto > 0 and cantidad > 0):
                    raise ValueError('Las dimensiones y la cantidad deben ser positivas y finitas')
                if csv_editable and not nombre:
                    raise ValueError('La pieza necesita un nombre')
                piezas.append({
                    'nombre': nombre or f'Pieza {len(piezas) + 1}',
                    'ancho': ancho,
                    'alto': alto,
                    'cantidad': cantidad,
                    'ancho_cm': convertir_a_cm(ancho, unidad_medida),
                    'alto_cm': convertir_a_cm(alto, unidad_medida),
                })
            except (ValueError, TypeError):
                if exigir_todas:
                    raise
                logger.warning('No se pudo interpretar la fila %s de un listado de piezas', numero)
    except (ValueError, csv.Error):
        if estricto:
            raise FormatoPiezasInvalido('Formato de piezas inválido') from None
        logger.warning('No se pudo interpretar un listado de piezas completo')
        return []
    return piezas


def mensaje_advertencia_piezas_no_colocadas(info_desperdicio, unidad='cm'):
    """
    Mensaje para el usuario cuando hubo piezas omitidas por no caber en el tablero.
    Devuelve None si no hay piezas omitidas.
    """
    omitidas = (info_desperdicio or {}).get('piezas_no_colocadas') or []
    if not omitidas:
        return None

    solicitadas = (info_desperdicio or {}).get('num_piezas_solicitadas')
    colocadas = (info_desperdicio or {}).get('num_piezas_colocadas')
    simbolo = obtener_simbolo_unidad(unidad)
    cuenta = Counter()
    for p in omitidas:
        key = (p.get('nombre', 'Pieza'), float(p.get('ancho_cm', 0)), float(p.get('alto_cm', 0)))
        cuenta[key] += 1
    partes_desc = []
    for (nombre, aw, ah), cnt in cuenta.items():
        wu = convertir_desde_cm(aw, unidad)
        hu = convertir_desde_cm(ah, unidad)
        partes_desc.append(f"{nombre} ×{cnt} ({wu}×{hu} {simbolo})")
    partes_desc.sort()
    max_items = 12
    texto = "; ".join(partes_desc[:max_items])
    if len(partes_desc) > max_items:
        texto += f"; …(+{len(partes_desc) - max_items})"
    sufix = ""
    if solicitadas is not None and colocadas is not None:
        sufix = f" Piezas en el plano: {colocadas} de {solicitadas}."
    elif colocadas is not None:
        sufix = f" Piezas en el plano: {colocadas}."
    return (
        f"No se pudieron colocar {len(omitidas)} pieza(s) (dimensiones mayores que el tablero en una sola orientación válida): {texto}.{sufix}"
    )
