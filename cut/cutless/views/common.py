from functools import wraps

from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, redirect

from ..materiales import dimension_material_valida, precio_material_valido
from ..models import Material
from ..pieces import FormatoPiezasInvalido
from ..permissions import usuario_tiene_permiso


def handler404(request, exception):
    """Maneja errores 404 con una página personalizada"""
    return render(request, 'cutless/404.html', status=404)


def requiere_permiso(permiso_nombre):
    """Decorador para verificar si el usuario tiene un permiso específico en su perfil."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('usuarios:login')

            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            try:
                perfil = request.user.perfil
            except AttributeError:
                return redirect('usuarios:login')

            if not usuario_tiene_permiso(request.user, permiso_nombre):
                messages.error(request, "❌ No tienes permiso para acceder a esta funcionalidad.")
                return redirect('cutless:index')

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def handler500(request):
    """Maneja errores 500 con una página personalizada"""
    return render(request, 'cutless/500.html', status=500)


def leer_id_optimizacion(valor):
    """Devuelve una clave positiva que cabe en el BigAutoField de Optimización."""
    if len(valor) > 19 or not valor.isascii() or not valor.isdecimal():
        return None
    numero = int(valor)
    if 0 < numero <= 2**63 - 1:
        return numero
    return None


def _materiales_data_index(user, *, incluir_medidas=True):
    """Datos de materiales para serializar con json_script (errores / reintentos)."""
    if not usuario_tiene_permiso(user, 'puede_ver_historial_costos'):
        return {}
    materiales_data = {}
    filtro = Q(es_predefinido=True)
    if getattr(user, 'is_authenticated', False):
        filtro = Q(usuario=user) | Q(es_predefinido=True)
    for material in Material.objects.filter(filtro):
        precio = material.precio
        datos = {
            'precio': float(precio) if precio is not None and precio_material_valido(precio) else None,
            'nombre': material.nombre,
        }
        if incluir_medidas:
            medidas_validas = dimension_material_valida(material.ancho) and dimension_material_valida(material.alto)
            datos.update(
                ancho=material.ancho if medidas_validas else None,
                alto=material.alto if medidas_validas else None,
                unidad_medida=material.unidad_medida or 'cm',
            )
        materiales_data[str(material.pk)] = datos
    return materiales_data


def exigir_piezas_completas(vista):
    @wraps(vista)
    def wrapper(*args, **kwargs):
        try:
            return vista(*args, **kwargs)
        except FormatoPiezasInvalido:
            return HttpResponse(
                'El listado de piezas necesita revisión. Se conservó el registro original.',
                status=422,
                content_type='text/plain; charset=utf-8',
            )
    return wrapper
