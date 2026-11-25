from django.db import connection, transaction
from django.contrib import messages
from django.db.models import Avg, Q
from django.http import HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..forms import ProyectoForm
from ..pieces import parsear_piezas_desde_texto
from ..models import Proyecto, Optimizacion
from ..services import enviar_notificacion
from ..services.calendario import fecha_comercial
from ..services.proyectos import ACCIONES, ESTADOS_VISIBLES, TRANSICIONES, con_estado_efectivo, registrar_transicion
from .common import leer_id_optimizacion


def _ids_seleccionados(datos):
    return {pk for valor in datos.getlist('optimizaciones') if (pk := leer_id_optimizacion(valor)) is not None}


def _bloquear_proyectos(proyectos):
    # Permite que otras operaciones comprueben la FK mientras se serializa la edición.
    return proyectos.select_for_update(no_key=connection.features.has_select_for_no_key_update)


def _bloquear_planes(usuario, seleccionadas, *, proyecto=None):
    candidatos = Q(pk__in=seleccionadas)
    if proyecto is not None:
        candidatos |= Q(proyecto=proyecto)
    planes = Optimizacion.objects.filter(usuario=usuario).filter(candidatos).order_by('pk')
    list(planes.select_for_update().values_list('pk', flat=True))


@transaction.atomic
def crear_proyecto(request):
    """
    Crea un nuevo proyecto con opción de agregar optimizaciones.
    """
    if request.method == "POST":
        _bloquear_planes(request.user, _ids_seleccionados(request.POST))
        form = ProyectoForm(request.POST, user=request.user)
        if form.is_valid():
            proyecto = form.save(commit=False)
            proyecto.usuario = request.user
            proyecto.save()
            
            # Asignar optimizaciones seleccionadas al proyecto
            optimizaciones_seleccionadas = form.cleaned_data.get('optimizaciones', [])
            if optimizaciones_seleccionadas:
                # Obtener IDs de las optimizaciones seleccionadas
                optimizaciones_ids = [opt.pk for opt in optimizaciones_seleccionadas]
                # Verificar que las optimizaciones pertenezcan al usuario y asignarlas
                num_optimizaciones = Optimizacion.objects.filter(
                    pk__in=optimizaciones_ids, usuario=request.user, proyecto__isnull=True,
                ).update(proyecto=proyecto)
                mensaje_proyecto = f'Se ha creado el proyecto "{proyecto.nombre}" exitosamente con {num_optimizaciones} optimización(es) asociada(s).'
            else:
                mensaje_proyecto = f'Se ha creado el proyecto "{proyecto.nombre}" exitosamente.'
            
            # Enviar notificación de proyecto creado (esto mostrará el mensaje según la configuración)
            enviar_notificacion(
                request,
                'proyecto_creado',
                'Proyecto Creado',
                mensaje_proyecto,
                {'proyecto_id': proyecto.id, 'nombre': proyecto.nombre}
            )
            
            return redirect('cutless:detalle_proyecto', pk=proyecto.pk)
    else:
        form = ProyectoForm(user=request.user)
    
    # Preparar información adicional de optimizaciones para el template
    optimizaciones_info = []
    optimizaciones_seleccionadas_ids = _ids_seleccionados(request.POST) if form.is_bound else set()
    
    if form.fields['optimizaciones'].queryset:
        
        for opt in form.fields['optimizaciones'].queryset:
            # Referencia estable del registro
            numero_lista = opt.correlativo
            
            # Extraer nombres de piezas
            nombres_piezas = [
                f"{pieza['nombre']} (x{pieza['cantidad']})"
                for pieza in parsear_piezas_desde_texto(opt.piezas, opt.unidad_medida)
            ]

            optimizaciones_info.append({
                'optimizacion': opt,
                'numero_lista': numero_lista,
                'seleccionada': opt.pk in optimizaciones_seleccionadas_ids,
                'nombres_piezas': nombres_piezas[:5],  # Máximo 5 piezas para no hacer muy largo
                'total_piezas': len(nombres_piezas),
            })
    
    return render(request, 'cutless/crear_proyecto.html', {
        'form': form,
        'optimizaciones_info': optimizaciones_info,
    })

@transaction.atomic
def eliminar_proyecto(request, pk):
    """
    Elimina un proyecto.
    """
    try:
        proyecto = Proyecto.objects.get(pk=pk, usuario=request.user)
    except Proyecto.DoesNotExist:
        messages.error(request, "No se encontró el proyecto.")
        return redirect('cutless:lista_proyectos')
    
    optimizaciones_count = proyecto.get_total_optimizaciones()
    
    if request.method == "POST":
        accion = request.POST.get('accion', 'mover')
        if accion not in ('mover', 'eliminar'):
            messages.error(request, 'Selecciona si deseas conservar o eliminar las optimizaciones.')
            return redirect('cutless:eliminar_proyecto', pk=pk)
        
        if accion == 'eliminar':
            # Eliminar todas las optimizaciones del proyecto
            proyecto.optimizacion_set.all().delete()
        # Si es 'mover', las optimizaciones simplemente perderán la referencia al proyecto (SET_NULL)
        
        nombre = proyecto.nombre
        proyecto.delete()
        messages.success(request, f'✅ Proyecto "{nombre}" eliminado exitosamente.')
        return redirect('cutless:lista_proyectos')
    
    return render(request, 'cutless/eliminar_proyecto.html', {
        'proyecto': proyecto,
        'optimizaciones_count': optimizaciones_count,
    })

@transaction.atomic
def agregar_optimizaciones_proyecto(request, pk):
    """Selección paginada; navegar y buscar conserva lo marcado sin guardarlo aún."""
    from django.core.paginator import Paginator

    proyectos = Proyecto.objects.filter(usuario=request.user)
    if request.method == 'POST' and request.POST.get('operacion', 'agregar') == 'agregar':
        proyectos = _bloquear_proyectos(proyectos)
    proyecto = get_object_or_404(proyectos, pk=pk)
    disponibles = Optimizacion.objects.filter(usuario=request.user, proyecto__isnull=True).order_by('-fecha', '-pk')
    datos = request.POST if request.method == 'POST' else request.GET
    busqueda = datos.get('busqueda', '').strip()[:100]
    seleccionadas = set()
    operacion = datos.get('operacion', 'agregar') if request.method == 'POST' else 'buscar'
    if request.method == 'POST':
        valores = request.POST.getlist('optimizaciones')
        if any(not valor.isascii() or not valor.isdecimal() or len(valor) > 18 for valor in valores):
            messages.error(request, 'La selección contiene identificadores inválidos. Vuelve a seleccionar los planes.')
            return redirect(request.path)
        seleccionadas = {int(valor) for valor in valores}
        if operacion == 'agregar':
            if seleccionadas:
                _bloquear_planes(request.user, seleccionadas)
                elegidas = disponibles.filter(pk__in=seleccionadas)
                if set(elegidas.values_list('pk', flat=True)) != seleccionadas:
                    messages.error(request, 'Algún plan ya no está disponible. Actualiza la lista y vuelve a elegir.')
                else:
                    cantidad = elegidas.update(proyecto=proyecto)
                    proyectos.filter(pk=pk).update(fecha_actualizacion=timezone.now())
                    messages.success(request, f'{cantidad} optimización(es) agregada(s) al proyecto "{proyecto.nombre}".')
                    return redirect('cutless:detalle_proyecto', pk=proyecto.pk)
            else:
                messages.warning(request, 'Selecciona al menos una optimización para agregar.')
        elif operacion not in ('buscar', 'anterior', 'siguiente'):
            messages.error(request, 'La acción solicitada no es válida.')
            return redirect(request.path)

    filtradas = disponibles
    if busqueda:
        filtradas = filtradas.buscar_referencia(busqueda, admite_numero=True)
    try:
        numero = int(datos.get('pagina', '1'))
    except (ValueError, TypeError):
        numero = 1
    if operacion == 'buscar':
        numero = 1
    elif operacion == 'anterior':
        numero -= 1
    elif operacion == 'siguiente':
        numero += 1
    paginas = Paginator(filtradas, 8)
    pagina = paginas.get_page(max(1, numero))
    visibles = list(pagina.object_list)
    ids_visibles = {opt.pk for opt in visibles}
    return render(request, 'cutless/agregar_optimizaciones_proyecto.html', {
        'proyecto': proyecto, 'optimizaciones_disponibles': visibles,
        'pagina': pagina, 'busqueda': busqueda, 'total_disponibles': disponibles.count(),
        'seleccionadas': seleccionadas, 'seleccionadas_ocultas': sorted(seleccionadas - ids_visibles),
    })


def lista_proyectos(request):
    """
    Lista todos los proyectos del usuario con filtros y búsqueda.
    """
    proyectos = con_estado_efectivo(Proyecto.objects.filter(usuario=request.user).select_related('cliente'))
    
    # Filtros
    estado_filtro = request.GET.get('estado', '')
    if estado_filtro:
        proyectos = proyectos.filter(estado_efectivo=estado_filtro)
    
    # Búsqueda
    busqueda = request.GET.get('busqueda', '').strip()
    if busqueda:
        proyectos = proyectos.filter(
            Q(nombre__icontains=busqueda) |
            Q(descripcion__icontains=busqueda) |
            Q(cliente__nombre__icontains=busqueda)
        )
    
    return render(request, 'cutless/lista_proyectos.html', {
        'proyectos': proyectos,
        'estado_filtro': estado_filtro,
        'estados': ESTADOS_VISIBLES,
        'busqueda': busqueda,
    })

def detalle_proyecto(request, pk):
    """
    Muestra el detalle de un proyecto con sus optimizaciones y métricas.
    """
    hoy = fecha_comercial()
    try:
        proyecto = con_estado_efectivo(Proyecto.objects.select_related('cliente'), hoy=hoy).get(
            pk=pk, usuario=request.user,
        )
    except Proyecto.DoesNotExist:
        messages.error(request, "Proyecto no encontrado.")
        return redirect('cutless:lista_proyectos')
    
    # Optimizaciones del proyecto
    optimizaciones = Optimizacion.objects.filter(proyecto=proyecto, usuario=request.user).order_by('-fecha')
    
    # Estadísticas
    total_optimizaciones = optimizaciones.count()
    costo_total = proyecto.get_total_costo()
    
    # Calcular promedio de aprovechamiento
    aprovechamiento_promedio = optimizaciones.aggregate(
        promedio=Avg('aprovechamiento_total')
    )['promedio'] or 0
    
    # Total de tableros
    total_tableros = sum(opt.num_tableros or 0 for opt in optimizaciones)
    
    return render(request, 'cutless/detalle_proyecto.html', {
        'proyecto': proyecto,
        'acciones_estado': [(accion, ACCIONES[accion]) for accion in TRANSICIONES.get(proyecto.estado, ())],
        'inicio_futuro': proyecto.fecha_inicio is not None and proyecto.fecha_inicio > hoy,
        'optimizaciones': optimizaciones,
        'total_optimizaciones': total_optimizaciones,
        'costo_total': costo_total,
        'aprovechamiento_promedio': aprovechamiento_promedio,
        'total_tableros': total_tableros,
    })

@require_POST
@transaction.atomic
def cambiar_estado_proyecto(request, pk):
    propios = Proyecto.objects.filter(usuario=request.user, pk=pk)
    proyecto = get_object_or_404(_bloquear_proyectos(propios))
    acciones = request.POST.getlist('accion')
    if len(acciones) != 1 or acciones[0] not in ACCIONES:
        return HttpResponseBadRequest('Selecciona una sola acción válida para el proyecto.')
    origen = request.POST.getlist('estado_origen')
    if origen != [proyecto.estado] or registrar_transicion(propios, origen=proyecto.estado, accion=acciones[0]) is None:
        messages.error(request, 'Esa acción ya no está disponible. Revisa el estado actual del proyecto.')
    else:
        mensajes = {'iniciar': 'Proyecto iniciado.', 'completar': 'Proyecto completado.', 'cancelar': 'Proyecto cancelado.'}
        messages.success(request, mensajes[acciones[0]])
    return redirect('cutless:detalle_proyecto', pk=pk)


@transaction.atomic
def editar_proyecto(request, pk):
    """
    Edita un proyecto existente.
    """
    proyectos = Proyecto.objects.filter(usuario=request.user)
    if request.method == 'POST':
        proyectos = _bloquear_proyectos(proyectos)
    proyecto = get_object_or_404(con_estado_efectivo(proyectos), pk=pk)

    if request.method == 'POST':
        seleccionadas = _ids_seleccionados(request.POST)
        if 'optimizaciones' in request.POST or 'seleccion_optimizaciones' in request.POST:
            _bloquear_planes(request.user, seleccionadas, proyecto=proyecto)
        form = ProyectoForm(request.POST, instance=proyecto, user=request.user)
        if form.is_valid():
            proyecto = form.save(commit=False)
            campos = ['nombre', 'descripcion', 'fecha_inicio', 'fecha_fin', 'fecha_actualizacion']
            if 'cliente' in request.POST:
                campos.append('cliente')
            proyecto.save(update_fields=campos)

            if form.modifica_optimizaciones:
                elegidas = {opt.pk for opt in form.cleaned_data['optimizaciones']}
                quitar = set(form.optimizaciones_guardadas) - elegidas
                proyecto.optimizacion_set.filter(usuario=request.user, pk__in=quitar).update(proyecto=None)
                Optimizacion.objects.filter(
                    usuario=request.user, proyecto__isnull=True, pk__in=elegidas,
                ).update(proyecto=proyecto)

            messages.success(request, f'✅ Proyecto "{proyecto.nombre}" actualizado exitosamente.')
            return redirect('cutless:detalle_proyecto', pk=proyecto.pk)
    else:
        form = ProyectoForm(instance=proyecto, user=request.user)
    
    # Preparar información adicional de optimizaciones para el template
    optimizaciones_info = []
    optimizaciones_seleccionadas_ids = (
        seleccionadas if form.modifica_optimizaciones else set(form.optimizaciones_guardadas)
    )
    
    if form.fields['optimizaciones'].queryset:
        
        for opt in form.fields['optimizaciones'].queryset:
            # Referencia estable del registro
            numero_lista = opt.correlativo
            
            # Extraer nombres de piezas
            nombres_piezas = [
                f"{pieza['nombre']} (x{pieza['cantidad']})"
                for pieza in parsear_piezas_desde_texto(opt.piezas, opt.unidad_medida)
            ]

            optimizaciones_info.append({
                'optimizacion': opt,
                'numero_lista': numero_lista,
                'seleccionada': opt.pk in optimizaciones_seleccionadas_ids,
                'nombres_piezas': nombres_piezas[:5],  # Máximo 5 piezas para no hacer muy largo
                'total_piezas': len(nombres_piezas),
            })
    
    return render(request, 'cutless/editar_proyecto.html', {
        'form': form,
        'proyecto': proyecto,
        'optimizaciones_info': optimizaciones_info,
    })

