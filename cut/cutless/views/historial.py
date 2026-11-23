from django.contrib import messages
from django.db import transaction
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from ..pieces import parsear_piezas_desde_texto
from ..models import Optimizacion
from ..services.board_presentation import preparar_plano_horizontal
from ..utils import convertir_desde_cm
from .common import leer_id_optimizacion


@require_POST
@transaction.atomic
def borrar_seleccion(request):
    seleccion = request.POST.getlist('seleccion')
    if not seleccion:
        messages.warning(request, 'No se seleccionó ninguna optimización para borrar.')
        return redirect('cutless:historial')

    ids = {leer_id_optimizacion(valor) for valor in seleccion}
    if None in ids:
        return HttpResponseBadRequest('La selección contiene identificadores de optimización inválidos.',
                                      content_type='text/plain; charset=utf-8')

    optimizaciones = Optimizacion.objects.filter(pk__in=ids, usuario=request.user)
    if set(optimizaciones.order_by('pk').select_for_update().values_list('pk', flat=True)) != ids:
        raise Http404

    optimizaciones.delete()
    messages.success(request, f'Se eliminaron {len(ids)} optimizaciones seleccionadas del historial.')
    return redirect('cutless:historial')


def borrar_historial(request):
    if request.method == "POST":
        optimizaciones = Optimizacion.objects.filter(usuario=request.user)
        count = optimizaciones.count()
        optimizaciones.delete()
        messages.success(request, f"Se eliminaron {count} optimizaciones del historial.")
        return redirect('cutless:historial')
    else:
        messages.error(request, "Operación no permitida.")
        return redirect('cutless:historial')

def historial(request):
    # Las posiciones del listado no intervienen en la identidad del registro.
    todas_optimizaciones = Optimizacion.objects.filter(usuario=request.user)
    total_absoluto = todas_optimizaciones.count()
    
    # Ordenamiento de presentación
    ordenar_por = request.GET.get('ordenar_por', 'fecha_desc')
    
    if ordenar_por == 'fecha_desc':
        todas_optimizaciones = todas_optimizaciones.order_by('-fecha')
    elif ordenar_por == 'fecha_asc':
        todas_optimizaciones = todas_optimizaciones.order_by('fecha')
    elif ordenar_por == 'aprovechamiento_desc':
        todas_optimizaciones = todas_optimizaciones.order_by('-aprovechamiento_total')
    elif ordenar_por == 'aprovechamiento_asc':
        todas_optimizaciones = todas_optimizaciones.order_by('aprovechamiento_total')
    else:
        todas_optimizaciones = todas_optimizaciones.order_by('-fecha')
    
    # Ahora aplicar filtros para mostrar
    optimizaciones = todas_optimizaciones
    
    # Filtro por favoritos
    solo_favoritos = request.GET.get('solo_favoritos', '').strip()
    if solo_favoritos == 'true':
        optimizaciones = optimizaciones.filter(favorito=True)
    
    # Filtro por nombre de pieza
    nombre_pieza = request.GET.get('nombre_pieza', '').strip()
    if nombre_pieza:
        optimizaciones = optimizaciones.buscar_referencia(nombre_pieza)
    
    # Filtro por fecha
    fecha_desde = request.GET.get('fecha_desde', '').strip()
    fecha_hasta = request.GET.get('fecha_hasta', '').strip()
    
    estado = 200
    try:
        desde, hasta = parse_date(fecha_desde), parse_date(fecha_hasta)
    except ValueError:
        desde = hasta = None
    if (fecha_desde and desde is None) or (fecha_hasta and hasta is None):
        messages.error(request, 'Fecha no válida. Usa el selector de calendario.')
        estado = 400
    elif desde and hasta and desde > hasta:
        messages.error(request, 'La fecha inicial no puede ser posterior a la fecha final.')
        estado = 400

    if estado == 400:
        optimizaciones = optimizaciones.none()
    else:
        if desde:
            optimizaciones = optimizaciones.filter(fecha__date__gte=desde)
        if hasta:
            optimizaciones = optimizaciones.filter(fecha__date__lte=hasta)
    
    # PAGINACIÓN
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    page = request.GET.get('page', 1)
    paginator = Paginator(optimizaciones, 12)  # 12 optimizaciones por página
    try:
        optimizaciones_page = paginator.page(page)
    except PageNotAnInteger:
        optimizaciones_page = paginator.page(1)
    except EmptyPage:
        optimizaciones_page = paginator.page(paginator.num_pages)

    optimizaciones_con_piezas = []
    for opt in optimizaciones_page:
        numero_mostrado = opt.correlativo
        piezas_procesadas = parsear_piezas_desde_texto(opt.piezas, opt.unidad_medida)
        unidad_opt = getattr(opt, 'unidad_medida', 'cm') or 'cm'
        ancho_mostrar = round(convertir_desde_cm(opt.ancho_tablero, unidad_opt), 2)
        alto_mostrar = round(convertir_desde_cm(opt.alto_tablero, unidad_opt), 2)
        # Miniatura derivada del primer tablero, sin regenerar ni guardar archivos.
        vistas = (opt.resultado_extra or {}).get('vistas_web', {})
        vista = vistas.get('1')
        miniatura = preparar_plano_horizontal(vista, unidad_opt, opt.margen_corte) if vista else None
        optimizaciones_con_piezas.append({
            'optimizacion': opt,
            'miniatura': {'plano': miniatura, 'numero': f'preview-{opt.pk}'} if miniatura else None,
            'piezas': piezas_procesadas,
            'numero': numero_mostrado,
            'ancho_mostrar': ancho_mostrar,
            'alto_mostrar': alto_mostrar,
            'unidad_medida': unidad_opt,
        })

    return render(request, 'cutless/historial.html', {
        'optimizaciones_con_piezas': optimizaciones_con_piezas,
        'nombre_pieza': nombre_pieza,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'ordenar_por': ordenar_por,
        'solo_favoritos': solo_favoritos,
        'total_sin_filtro': total_absoluto,
        'page_obj': optimizaciones_page,
        'paginator': paginator,
    }, status=estado)

def borrar_optimizacion(request, pk):
    """
    Elimina una optimización individual del usuario actual.
    """
    optimizacion = get_object_or_404(Optimizacion, pk=pk, usuario=request.user)
    codigo = optimizacion.codigo

    if request.method == "POST":
        optimizacion.delete()
        messages.success(request, f"Optimización {codigo} eliminada correctamente.")
        return redirect('cutless:historial')
    else:
        return render(request, 'cutless/eliminar_optimizacion.html', {
            'optimizacion': optimizacion,
            'numero_mostrado': optimizacion.pk,
        })

@require_POST
def toggle_favorito(request, pk):
    """
    Marca o desmarca una optimización como favorita.
    Soporta tanto peticiones AJAX como peticiones normales.
    """
    optimizacion = get_object_or_404(Optimizacion, pk=pk, usuario=request.user)
    optimizacion.favorito = not optimizacion.favorito
    optimizacion.save(update_fields=['favorito'])
    
    # Si es una petición AJAX, devolver JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('ajax') == 'true':
        from django.http import JsonResponse
        return JsonResponse({
            'success': True,
            'favorito': optimizacion.favorito,
            'message': f"⭐ Optimización {optimizacion.codigo} marcada como favorita." if optimizacion.favorito else f"Optimización {optimizacion.codigo} eliminada de favoritos."
        })
    
    # Si no es AJAX, comportamiento normal con mensajes
    if optimizacion.favorito:
        messages.success(request, f"⭐ Optimización {optimizacion.codigo} marcada como favorita.")
    else:
        messages.info(request, f"Optimización {optimizacion.codigo} eliminada de favoritos.")
    
    # Redirigir de vuelta a historial, manteniendo los filtros (solo si no es AJAX)
    retorno = request.headers.get('Referer')
    if url_has_allowed_host_and_scheme(retorno, {request.get_host()}, require_https=request.is_secure()):
        return redirect(retorno)
    return redirect('cutless:historial')

