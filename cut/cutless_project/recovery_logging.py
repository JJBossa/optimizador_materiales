from logging import Filter
from urllib.parse import unquote


class FiltroRecuperacion(Filter):
    """Evita registrar la URL del token o volcados de solicitudes de recuperación."""

    def filter(self, record):
        rutas = ('/usuarios/reset-password', '/usuarios/recuperar-password')
        solicitud = getattr(record, 'request', None)
        ruta = getattr(solicitud, 'path_info', '')
        referer = unquote(getattr(solicitud, 'META', {}).get('HTTP_REFERER', ''))
        mensaje = unquote(record.getMessage())
        return not any(fragmento in ruta or fragmento in referer or fragmento in mensaje for fragmento in rutas)
