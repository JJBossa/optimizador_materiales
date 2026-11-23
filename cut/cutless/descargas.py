"""Señal optativa de preparación para las descargas nativas de CutLess."""

import re
from urllib.parse import urlsplit

from django.urls import reverse
from django.utils.cache import patch_cache_control


XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
TIPOS_DESCARGA = {
    'cutless:descargar_pdf': 'application/pdf',
    'cutless:descargar_excel': XLSX,
    'cutless:descargar_png': 'image/png',
    'cutless:descargar_png_tablero': 'image/png',
    'cutless:generar_pdf_presupuesto': 'application/pdf',
    'cutless:exportar_excel_desperdicio': XLSX,
    'cutless:exportar_pdf_desperdicio': 'application/pdf',
    'cutless:historial_costos': XLSX,
}


def estado_descarga(response, vista, tipo):
    if response.status_code >= 400:
        return str(response.status_code)

    if 300 <= response.status_code < 400:
        destino = urlsplit(response.get('Location', '')).path
        if destino == reverse('usuarios:login'):
            return '401'
        if destino == reverse('cutless:index'):
            return '403'
        if destino in (reverse('cutless:historial'), reverse('cutless:lista_presupuestos')):
            return '404'
        return '500'

    disposicion = response.get('Content-Disposition', '').partition(';')[0].lower()
    tipo_respuesta = response.get('Content-Type', '').partition(';')[0].lower()
    es_archivo = disposicion == 'attachment' or (disposicion == 'inline' and vista == 'cutless:generar_pdf_presupuesto')
    if response.status_code == 200 and tipo_respuesta == tipo and es_archivo:
        return 'preparado'
    return 'inesperado'


class DescargaObservableMiddleware:
    """Adjunta el estado a las cabeceras originales, incluso para respuestas en streaming."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        vista = request.resolver_match.view_name if request.resolver_match else None
        tipo = TIPOS_DESCARGA.get(vista)
        if not tipo or request.method != 'GET':
            return response
        if vista == 'cutless:historial_costos' and request.GET.get('export') != 'excel':
            return response

        token = request.GET.get('_cutless_download', '')
        if not re.fullmatch(r'[0-9a-f]{32}', token):
            return response

        response.set_cookie(
            f'cutless_descarga_{token}', estado_descarga(response, vista, tipo),
            max_age=120, samesite='Lax', secure=request.is_secure(),
        )
        patch_cache_control(response, private=True, no_store=True)
        return response
