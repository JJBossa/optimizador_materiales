from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from ..services.alertas import CATEGORIAS, obtener_alertas


def _parametros(request):
    categoria = request.GET.get('categoria', '')
    pagina = request.GET.get('pagina', '1')
    if categoria and categoria not in CATEGORIAS:
        return None
    if len(pagina) > 9 or not pagina.isascii() or not pagina.isdecimal() or int(pagina) < 1:
        return None
    return {'categoria': categoria, 'pagina': int(pagina)}


@never_cache
@require_GET
def api_alertas(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Sesión expirada.'}, status=401)
    parametros = _parametros(request)
    if parametros is None:
        return JsonResponse({'error': 'Filtro o página no válidos.'}, status=400)
    return JsonResponse(obtener_alertas(request.user, **parametros, solo_total=request.GET.get('resumen') == '1'))


@never_cache
@login_required
@require_GET
def centro_alertas(request):
    parametros = _parametros(request)
    if parametros is None:
        return HttpResponseBadRequest('Filtro o página no válidos.')
    resultado = obtener_alertas(request.user, **parametros)
    if not resultado['categorias']:
        raise PermissionDenied
    return render(request, 'cutless/centro_alertas.html', {**resultado, **parametros})
