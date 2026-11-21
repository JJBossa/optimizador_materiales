"""Formato de lectura para importes expresados en pesos chilenos."""

import re
from decimal import ROUND_HALF_UP, Decimal


DECIMAL_CANONICO = re.compile(r'[+-]?[0-9]+(?:\.[0-9]+)?')


def formatear_clp(valor, con_signo=False):
    if isinstance(valor, str):
        if not DECIMAL_CANONICO.fullmatch(valor):
            return '—'
    elif isinstance(valor, bool) or not isinstance(valor, (Decimal, int, float)):
        return '—'

    monto = Decimal(str(valor))
    if not monto.is_finite():
        return '—'
    pesos = monto.copy_abs().to_integral_value(rounding=ROUND_HALF_UP)
    signo = '-' if monto < 0 else '+' if con_signo and monto > 0 else ''
    if not pesos and monto:
        return f'{signo}(menos de $1)' if signo else 'Menos de $1'
    agrupado = format(pesos, ',f').replace(',', '.')
    return f'{signo}${agrupado}'
