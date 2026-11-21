from django.db import transaction
from decimal import Decimal


from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from ..exports.pdf import generar_pdf_presupuesto as construir_pdf_presupuesto
from ..formato_clp import formatear_clp
from ..forms import PresupuestoForm
from ..pieces import parsear_piezas_desde_texto
from ..models import Presupuesto, Optimizacion, Cliente
from ..services import enviar_notificacion
from ..services.indicadores import obtener_indicadores
from .common import exigir_piezas_completas
from .media import media_privada


class EstadoPresupuestoEmitidoForm(forms.ModelForm):
    estado = forms.ChoiceField(
        choices=[(valor, etiqueta) for valor, etiqueta in Presupuesto.ESTADOS_CHOICES if valor != 'borrador'],
        label='Estado',
    )

    class Meta:
        model = Presupuesto
        fields = ('estado',)


def guardar_detalle_presupuesto(presupuesto):
    presupuesto.costo_total = presupuesto.calcular_costo_total_multiple()
    if presupuesto.estado != 'borrador':
        presupuesto.cerrar_detalle()
    presupuesto.save(update_fields=['costo_total', 'detalle_emitido', 'fecha_actualizacion'])


@never_cache
@require_GET
def indicadores_presupuestos(request):
    return JsonResponse(obtener_indicadores())


def lista_presupuestos(request):
    """
    Lista todos los presupuestos del usuario.
    """
    # Filtrar presupuestos del usuario
    presupuestos = Presupuesto.objects.filter(
        usuario=request.user
    ).prefetch_related('optimizaciones__material').select_related('cliente', 'proyecto').order_by('-fecha_creacion')
    
    # Filtros
    estado_filtro = request.GET.get('estado', '')
    if estado_filtro:
        presupuestos = presupuestos.filter(estado=estado_filtro)
    
    # Búsqueda
    busqueda = request.GET.get('busqueda', '').strip()
    if busqueda:
        presupuestos = presupuestos.filter(
            Q(numero__icontains=busqueda) |
            Q(cliente__nombre__icontains=busqueda)
        )
    
    return render(request, 'cutless/lista_presupuestos.html', {
        'presupuestos': presupuestos,
        'estado_filtro': estado_filtro,
        'busqueda': busqueda,
    })

@transaction.atomic
def crear_presupuesto(request):
    """
    Crea un nuevo presupuesto desde una optimización.
    """
    # Si viene desde una optimización específica
    optimizacion_id = request.GET.get('optimizacion')
    optimizacion = None
    if optimizacion_id:
        optimizacion = get_object_or_404(Optimizacion, pk=optimizacion_id, usuario=request.user)
    
    if request.method == "POST":
        form = PresupuestoForm(request.POST, user=request.user)
        if form.is_valid():
            # El usuario existe antes de su primer presupuesto y serializa todas sus altas.
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            presupuesto = form.save(commit=False)
            presupuesto.usuario = request.user
            
            # Manejar nombre de cliente nuevo
            nombre_cliente_nuevo = form.cleaned_data.get('nombre_cliente_nuevo', '').strip()
            if nombre_cliente_nuevo:
                # Buscar o crear cliente con ese nombre
                cliente, created = Cliente.objects.get_or_create(
                    nombre=nombre_cliente_nuevo,
                    usuario=request.user,
                    defaults={'nombre': nombre_cliente_nuevo}
                )
                presupuesto.cliente = cliente
                if created:
                    messages.info(request, f'✅ Cliente "{nombre_cliente_nuevo}" creado automáticamente.')
            elif not presupuesto.cliente:
                # Si no hay cliente seleccionado ni nombre nuevo, usar el de la optimización si existe
                if optimizacion and optimizacion.cliente:
                    presupuesto.cliente = optimizacion.cliente
            
            # Generar número único
            presupuesto.numero = Presupuesto.generar_numero_presupuesto(usuario=request.user)
            
            optimizaciones_seleccionadas = form.cleaned_data['optimizaciones']
            presupuesto.costo_total = (
                presupuesto.precio_tablero * sum(opt.num_tableros or 0 for opt in optimizaciones_seleccionadas)
                + presupuesto.mano_obra
            )
            
            # Guardar primero para poder asignar las optimizaciones ManyToMany
            presupuesto.save()
            
            # Asignar optimizaciones (ManyToMany)
            presupuesto.optimizaciones.set(optimizaciones_seleccionadas)
            
            # Recalcular costo total (por si acaso) y guardar de nuevo
            guardar_detalle_presupuesto(presupuesto)
            
            # Enviar notificación de presupuesto creado (esto mostrará el mensaje según la configuración)
            enviar_notificacion(
                request,
                'presupuesto_creado',
                'Presupuesto Creado',
                f'Se ha creado el presupuesto #{presupuesto.numero} con un costo total de '
                f'{formatear_clp(presupuesto.costo_total).lower()}.',
                {'presupuesto_id': presupuesto.id, 'numero': presupuesto.numero, 'costo_total': presupuesto.costo_total}
            )
            return redirect('cutless:detalle_presupuesto', pk=presupuesto.pk)
    else:
        form = PresupuestoForm(user=request.user)
        if optimizacion:
            # Prellenar datos desde la optimización
            form.fields['optimizaciones'].initial = [optimizacion]
            if optimizacion.cliente:
                form.fields['cliente'].initial = optimizacion.cliente
            if optimizacion.precio_tablero:
                form.fields['precio_tablero'].initial = optimizacion.precio_tablero
            if optimizacion.mano_obra:
                form.fields['mano_obra'].initial = optimizacion.mano_obra
            if optimizacion.proyecto:
                form.fields['proyecto'].initial = optimizacion.proyecto
    
    # Preparar información adicional de optimizaciones para el template
    optimizaciones_info = []
    optimizaciones_seleccionadas_ids = [int(pk) for pk in request.POST.getlist('optimizaciones') if pk.isdecimal()] if form.is_bound else []
    if optimizacion and not form.is_bound:
        optimizaciones_seleccionadas_ids = [optimizacion.pk]
    
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
    
    return render(request, 'cutless/crear_presupuesto.html', {
        'form': form,
        'optimizacion': optimizacion,
        'optimizaciones_info': optimizaciones_info,
    })

@exigir_piezas_completas
def generar_pdf_presupuesto(request, pk):
    """
    Genera el PDF del presupuesto.
    """
    try:
        presupuesto = Presupuesto.objects.prefetch_related('optimizaciones__material').select_related('cliente').get(
            pk=pk,
            usuario=request.user
        )
    except Presupuesto.DoesNotExist:
        messages.error(request, "Presupuesto no encontrado.")
        return redirect('cutless:lista_presupuestos')
    
    if presupuesto.es_historico and presupuesto.pdf:
        try:
            return media_privada(request, presupuesto.pdf.name)
        except Http404:
            pass

    import io
    buffer = io.BytesIO()
    construir_pdf_presupuesto(presupuesto, archivo_salida=buffer)
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, content_type='application/pdf',
                        filename=f'presupuesto_{presupuesto.numero}.pdf')

def detalle_presupuesto(request, pk):
    """
    Muestra el detalle de un presupuesto y permite generar PDF.
    """
    try:
        presupuesto = Presupuesto.objects.prefetch_related('optimizaciones__material').select_related('cliente', 'proyecto').get(
            pk=pk,
            usuario=request.user
        )
    except Presupuesto.DoesNotExist:
        messages.error(request, "Presupuesto no encontrado.")
        return redirect('cutless:lista_presupuestos')
    
    # Calcular información adicional para el template
    # Obtener todas las optimizaciones del usuario ordenadas por fecha descendente (igual que en historial)
    
    optimizaciones_con_costos = []
    for opt in presupuesto.lineas_cotizadas:
        num_tableros = opt.num_tableros or 0
        costo_tableros = presupuesto.precio_tablero * Decimal(str(num_tableros))
        
        optimizaciones_con_costos.append({
            'optimizacion': opt,
            'num_tableros': num_tableros,
            'costo_tableros': costo_tableros,
        })
    
    return render(request, 'cutless/detalle_presupuesto.html', {
        'presupuesto': presupuesto,
        'total_presupuesto': presupuesto.total_vigente,
        'optimizaciones_con_costos': optimizaciones_con_costos,
        'total_tableros': presupuesto.get_total_tableros(),
    })

@transaction.atomic
def editar_presupuesto(request, pk):
    """
    Edita un presupuesto existente.
    """
    queryset = Presupuesto.objects.prefetch_related('optimizaciones__material')
    if request.method == 'POST':
        queryset = queryset.select_for_update()
    try:
        presupuesto = queryset.get(pk=pk, usuario=request.user)
    except Presupuesto.DoesNotExist:
        messages.error(request, 'Presupuesto no encontrado.')
        return redirect('cutless:lista_presupuestos')

    if presupuesto.estado != 'borrador':
        estado_form = EstadoPresupuestoEmitidoForm(
            request.POST if request.method == 'POST' else None, instance=presupuesto,
        )
        if request.method == 'POST' and estado_form.is_valid():
            presupuesto.save(update_fields=['estado', 'fecha_actualizacion'])
            messages.success(request, 'Estado del presupuesto actualizado.')
            return redirect('cutless:detalle_presupuesto', pk=pk)
        return render(request, 'cutless/editar_estado_presupuesto.html', {
            'presupuesto': presupuesto, 'form': estado_form,
        })

    if request.method == 'POST':
        form = PresupuestoForm(request.POST, instance=presupuesto, user=request.user)
        if form.is_valid():
            presupuesto = form.save(commit=False)
            
            # Manejar nombre de cliente nuevo
            nombre_cliente_nuevo = form.cleaned_data.get('nombre_cliente_nuevo', '').strip()
            if nombre_cliente_nuevo:
                # Buscar o crear cliente con ese nombre
                cliente, created = Cliente.objects.get_or_create(
                    nombre=nombre_cliente_nuevo,
                    usuario=request.user,
                    defaults={'nombre': nombre_cliente_nuevo}
                )
                presupuesto.cliente = cliente
                if created:
                    messages.info(request, f'✅ Cliente "{nombre_cliente_nuevo}" creado automáticamente.')
            
            # Guardar primero para poder asignar las optimizaciones ManyToMany
            presupuesto.save()
            
            # Asignar optimizaciones (ManyToMany)
            optimizaciones_seleccionadas = form.cleaned_data['optimizaciones']
            presupuesto.optimizaciones.set(optimizaciones_seleccionadas)
            
            # Recalcular costo total y guardar de nuevo
            guardar_detalle_presupuesto(presupuesto)
            
            num_optimizaciones = presupuesto.optimizaciones.count()
            messages.success(request, f'✅ Presupuesto "{presupuesto.numero}" actualizado exitosamente con {num_optimizaciones} optimización(es).')
            return redirect('cutless:detalle_presupuesto', pk=presupuesto.pk)
    else:
        form = PresupuestoForm(instance=presupuesto, user=request.user)
    
    # Preparar información adicional de optimizaciones para el template
    optimizaciones_info = []
    optimizaciones_seleccionadas_ids = ([int(pk) for pk in request.POST.getlist('optimizaciones') if pk.isdecimal()] if form.is_bound else list(presupuesto.optimizaciones.values_list('pk', flat=True)))
    
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
    
    return render(request, 'cutless/editar_presupuesto.html', {
        'form': form,
        'presupuesto': presupuesto,
        'optimizaciones_info': optimizaciones_info,
    })

@transaction.atomic
def agregar_optimizaciones_presupuesto(request, pk):
    """
    Permite agregar múltiples optimizaciones a un presupuesto existente.
    """
    queryset = Presupuesto.objects.all()
    if request.method == 'POST':
        queryset = queryset.select_for_update()
    try:
        presupuesto = queryset.get(pk=pk, usuario=request.user)
    except Presupuesto.DoesNotExist:
        messages.error(request, "Presupuesto no encontrado.")
        return redirect('cutless:lista_presupuestos')
    
    if presupuesto.estado != 'borrador':
        messages.error(request, 'Solo se pueden agregar optimizaciones a un borrador.')
        return redirect('cutless:detalle_presupuesto', pk=pk)

    # Obtener optimizaciones que aún no están en el presupuesto
    optimizaciones_en_presupuesto = presupuesto.optimizaciones.values_list('pk', flat=True)
    optimizaciones_disponibles = Optimizacion.objects.filter(
        usuario=request.user
    ).exclude(pk__in=optimizaciones_en_presupuesto).order_by('-fecha')
    
    if request.method == "POST":
        optimizaciones_ids = request.POST.getlist('optimizaciones')
        if any(not valor.isdecimal() for valor in optimizaciones_ids):
            messages.error(request, 'La selección contiene identificadores inválidos. Vuelve a seleccionar los planes.')
            return redirect(request.path)
        if optimizaciones_ids:
            optimizaciones_seleccionadas = Optimizacion.objects.filter(
                pk__in=optimizaciones_ids,
                usuario=request.user
            )
            if set(optimizaciones_seleccionadas.values_list('pk', flat=True)) != {int(valor) for valor in optimizaciones_ids}:
                messages.error(request, 'Algún plan ya no está disponible para esta selección. Actualiza la lista y vuelve a elegir.')
                return redirect(request.path)
            actuales = presupuesto.optimizaciones.all()
            ids = set(actuales.values_list('pk', flat=True))
            tableros = sum(opt.num_tableros for opt in actuales) + sum(opt.num_tableros for opt in optimizaciones_seleccionadas if opt.pk not in ids)
            if presupuesto.precio_tablero * tableros + presupuesto.mano_obra > Decimal('99999999.99'):
                messages.error(request, 'El total supera el máximo admitido: $99.999.999,99.')
                return redirect(request.path)
            # Agregar las optimizaciones al presupuesto (ManyToMany)
            presupuesto.optimizaciones.add(*optimizaciones_seleccionadas)
            
            # Recalcular costo total
            presupuesto.costo_total = presupuesto.calcular_costo_total_multiple()
            presupuesto.save()
            
            messages.success(
                request, 
                f'✅ {optimizaciones_seleccionadas.count()} optimización(es) agregada(s) al presupuesto "{presupuesto.numero}".'
            )
            return redirect('cutless:detalle_presupuesto', pk=presupuesto.pk)
        else:
            messages.warning(request, "Debes seleccionar al menos una optimización.")
    
    return render(request, 'cutless/agregar_optimizaciones_presupuesto.html', {
        'presupuesto': presupuesto,
        'optimizaciones_disponibles': optimizaciones_disponibles,
        'optimizaciones_info': [{'optimizacion': opt, 'seleccionada': False} for opt in optimizaciones_disponibles],
    })

