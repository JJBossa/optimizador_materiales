import re

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import PasswordResetConfirmView
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponseBadRequest, JsonResponse
from django.core.paginator import Paginator
from django.conf import settings
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from .forms import AccesoForm, RegistroForm, UsuarioEdicionForm, PermisosUsuarioForm, CambiarPasswordForm
from .models import PerfilUsuario
from .recuperacion import FormularioRecuperacion

@require_POST
def actividad_sesion(request):
    """Renueva la sesión solo cuando el navegador informa actividad real."""
    if not request.user.is_authenticated:
        return JsonResponse({'active': False}, status=401)
    request.session.modified = True
    return JsonResponse({'active': True})


@never_cache
def registro(request):
    if request.method == "POST":
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Asegurar la existencia de perfil
            PerfilUsuario.objects.get_or_create(usuario=user)
            messages.success(request, 'Tu cuenta está lista. Ahora inicia sesión.')
            return redirect('usuarios:login')
    else:
        form = RegistroForm()
    return render(request, 'usuarios/registro.html', {'form': form})


def es_admin(usuario):
    if not usuario.is_authenticated:
        return False
    if usuario.is_superuser:
        return True
    try:
        return usuario.perfil.rol == 'admin'
    except PerfilUsuario.DoesNotExist:
        return False


def puede_administrar_cuenta(actor, cuenta):
    return actor != cuenta and (
        actor.is_superuser or not (cuenta.is_superuser or cuenta.is_staff or es_admin(cuenta))
    )


def comprobar_rol(actor, rol):
    if rol not in dict(PerfilUsuario.ROL_CHOICES):
        return HttpResponseBadRequest('Rol desconocido.')
    if rol == 'admin' and not actor.is_superuser:
        raise PermissionDenied
    return None


@login_required
@user_passes_test(es_admin)
def admin_dashboard(request):
    usuarios = User.objects.select_related('perfil').all().order_by('username')
    busqueda = request.GET.get('busqueda', '').strip()

    if busqueda:
        usuarios = usuarios.filter(
            username__icontains=busqueda
        ) | usuarios.filter(
            email__icontains=busqueda
        ) | usuarios.filter(
            perfil__rol__icontains=busqueda
        )
        usuarios = usuarios.distinct().order_by('username')

    total_usuarios = usuarios.count()
    paginator = Paginator(usuarios, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    if request.method == 'POST' and 'crear_usuario' in request.POST:
        form = RegistroForm(request.POST)
        rol = request.POST.get('rol', 'usuario')
        error = comprobar_rol(request.user, rol)
        if error is not None:
            return error
        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                user.is_staff = rol == 'admin'
                user.save()
                perfil, _ = PerfilUsuario.objects.get_or_create(usuario=user)
                perfil.rol = rol
                perfil.save(update_fields=['rol'])
            messages.success(request, f"Usuario '{user.username}' creado con rol '{rol}'.")
            return redirect('usuarios:admin_dashboard')
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario de creación.')
    else:
        form = RegistroForm()

    return render(request, 'usuarios/admin_dashboard.html', {
        'usuarios': page_obj.object_list,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'form': form,
        'busqueda': busqueda,
        'total_usuarios': total_usuarios,
        'cuentas_administrables': {u.pk for u in page_obj.object_list if puede_administrar_cuenta(request.user, u)},
    })


@login_required
@user_passes_test(es_admin)
@require_POST
@transaction.atomic
def eliminar_usuario(request, pk):
    usuario = get_object_or_404(User.objects.select_for_update(), pk=pk)
    if not puede_administrar_cuenta(request.user, usuario):
        raise PermissionDenied

    usuario.delete()
    messages.success(request, f"Usuario {usuario.username} eliminado.")
    return redirect('usuarios:admin_dashboard')


@login_required
@user_passes_test(es_admin)
@transaction.atomic
def editar_usuario(request, pk):
    cuentas = User.objects
    if request.method == 'POST':
        cuentas = cuentas.select_for_update()
    usuario = get_object_or_404(cuentas, pk=pk)
    if not puede_administrar_cuenta(request.user, usuario):
        raise PermissionDenied

    try:
        perfil = usuario.perfil
    except PerfilUsuario.DoesNotExist:
        perfil = PerfilUsuario(usuario=usuario)

    if request.method == 'POST':
        form = UsuarioEdicionForm(request.POST, instance=usuario)
        permisos_form = PermisosUsuarioForm(request.POST, instance=perfil)
        if form.is_valid() and permisos_form.is_valid():
            password = form.cleaned_data.get('password1')
            if password:
                usuario.set_password(password)
            form.save()
            permisos_form.save()
            messages.success(request, f"Usuario '{usuario.username}' actualizado correctamente.")
            return redirect('usuarios:admin_dashboard')
        messages.error(request, 'Por favor corrige los errores del formulario.')
    else:
        form = UsuarioEdicionForm(instance=usuario)
        permisos_form = PermisosUsuarioForm(instance=perfil)

    return render(request, 'usuarios/editar_usuario.html', {
        'usuario_obj': usuario,
        'form': form,
        'permisos_form': permisos_form,
        'perfil': perfil,
    })


@login_required
@user_passes_test(es_admin)
@require_POST
@transaction.atomic
def actualizar_rol(request, pk):
    usuario = get_object_or_404(User.objects.select_for_update(), pk=pk)
    if not puede_administrar_cuenta(request.user, usuario):
        raise PermissionDenied
    rol = request.POST.get('rol', 'usuario')
    error = comprobar_rol(request.user, rol)
    if error is not None:
        return error
    perfil, _ = PerfilUsuario.objects.get_or_create(usuario=usuario)
    perfil.rol = rol
    perfil.save(update_fields=['rol'])
    usuario.is_staff = rol == 'admin' or usuario.is_superuser
    usuario.save(update_fields=['is_staff'])
    messages.success(request, f"Rol del usuario {usuario.username} actualizado a {rol}.")
    return redirect('usuarios:admin_dashboard')


@never_cache
def login_view(request):
    if request.user.is_authenticated:
        return redirect('cutless:index' if request.user.perfil.inicio_personalizado else 'usuarios:configuracion_inicial')
    if request.method == "POST":
        form = AccesoForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # Asegurar que el usuario tenga un perfil
            perfil, created = PerfilUsuario.objects.get_or_create(usuario=user)
            # Configurar timeout de sesión según el perfil del usuario
            if perfil.timeout_sesion is not None and perfil.timeout_sesion != 0:
                timeout_segundos = perfil.get_timeout_segundos()
                if timeout_segundos:
                    request.session['timeout_personalizado'] = timeout_segundos
                    # Configurar expiración de sesión en Django (en segundos)
                    request.session.set_expiry(timeout_segundos)
            elif perfil.timeout_sesion == 0:
                # Si está desactivado (0), configurar sesión para que no expire nunca
                # Usar un valor muy grande (10 años en segundos) para simular "sin expiración"
                request.session.pop('timeout_personalizado', None)
                request.session.set_expiry(315360000)  # 10 años en segundos (prácticamente sin expiración)
            else:
                # Si es None, usar el valor por defecto del sistema
                request.session.pop('timeout_personalizado', None)
                request.session.set_expiry(None)  # Usar SESSION_COOKIE_AGE por defecto
            # Mostrar modal de bienvenida solo en la primera vista tras login exitoso
            request.session['mostrar_bienvenida_cutless'] = perfil.inicio_personalizado
            return redirect('cutless:index' if perfil.inicio_personalizado else 'usuarios:configuracion_inicial')
    else:
        form = AccesoForm()
    return render(request, 'usuarios/login.html', {'form': form})

@login_required
@never_cache
@transaction.atomic
def configuracion_inicial(request):
    from .forms import ConfiguracionInicialForm

    perfiles = PerfilUsuario.objects
    enviado = request.method == 'POST'
    if enviado:
        perfiles = perfiles.select_for_update()
    perfil, _ = perfiles.get_or_create(usuario=request.user)
    omitir = enviado and request.POST.get('setup_action') == 'skip'
    datos = request.POST if enviado else None
    if omitir:
        datos = None if perfil.inicio_personalizado else {
            'modo': 'esencial',
            'tema_preferido': perfil.tema_preferido,
            'tamanio_fuente': perfil.tamanio_fuente,
        }

    form = ConfiguracionInicialForm(datos, instance=perfil)
    if enviado and ((omitir and perfil.inicio_personalizado) or form.is_valid()):
        if form.is_bound:
            form.save()
        borrador = request.POST.get('setup_draft_id', '')
        if re.fullmatch(r'[a-zA-Z0-9-]{1,64}', borrador):
            request.session['setup_draft_confirmado'] = borrador
        request.session.pop('mostrar_bienvenida_cutless', None)
        messages.success(request, 'Tu espacio está listo. Puedes cambiar estas preferencias desde Cuenta.')
        return redirect('cutless:index')
    return render(request, 'usuarios/configuracion_inicial.html', {
        'form': form, 'inicio_completado': perfil.inicio_personalizado,
        'borrador_confirmado': request.session.get('setup_draft_confirmado', ''),
        'ocultar_tutorial': True,
    })


@never_cache
@require_POST
def logout_view(request):
    logout(request)
    request.session.flush()
    return redirect('usuarios:login')

@login_required
def perfil(request):
    """Vista para ver y editar el perfil del usuario"""
    from .forms import PreferenciasPerfilForm, CuentaPerfilForm
    try:
        perfil = request.user.perfil
    except PerfilUsuario.DoesNotExist:
        # Si no existe, crearlo
        perfil = PerfilUsuario.objects.create(usuario=request.user)
    
    # CORREGIDO: Refrescar el perfil desde la BD antes de inicializar el formulario
    # Esto asegura que siempre tengamos los valores más recientes
    perfil.refresh_from_db()
    
    perfil_form = PreferenciasPerfilForm(instance=perfil, user=request.user)
    cuenta_form = CuentaPerfilForm(instance=perfil, user=request.user)
    password_form = CambiarPasswordForm(user=request.user)
    
    if request.method == "POST":
        if 'editar_perfil' in request.POST:
            perfil_form = PreferenciasPerfilForm(request.POST, instance=perfil, user=request.user)
            if perfil_form.is_valid():
                perfil_form.save()
                # Actualizar timeout en sesión
                perfil.refresh_from_db()  # Recargar para obtener los valores actualizados
                if perfil.timeout_sesion is not None and perfil.timeout_sesion != 0:
                    timeout_segundos = perfil.get_timeout_segundos()
                    if timeout_segundos:
                        request.session['timeout_personalizado'] = timeout_segundos
                        # Configurar expiración de sesión en Django (en segundos)
                        request.session.set_expiry(timeout_segundos)
                elif perfil.timeout_sesion == 0:
                    # Si está desactivado (0), configurar sesión para que no expire nunca
                    request.session.pop('timeout_personalizado', None)
                    request.session.set_expiry(315360000)  # 10 años en segundos (prácticamente sin expiración)
                else:
                    # Si es None, usar el valor por defecto del sistema
                    request.session.pop('timeout_personalizado', None)
                    request.session.set_expiry(None)  # Usar SESSION_COOKIE_AGE por defecto
                # Guardar tema preferido en sesión y localStorage (se aplicará con JavaScript)
                if perfil.tema_preferido != 'auto':
                    request.session['tema_preferido'] = perfil.tema_preferido
                else:
                    request.session.pop('tema_preferido', None)

                # Guardar otras preferencias en sesión para consistencia (también en JS localStorage)
                request.session['unidad_medida_predeterminada'] = perfil.unidad_medida_predeterminada
                request.session['tamanio_fuente'] = perfil.tamanio_fuente

                messages.success(request, 'Perfil actualizado exitosamente.')
                return redirect('usuarios:perfil')
        
        elif 'editar_cuenta' in request.POST:
            cuenta_form = CuentaPerfilForm(request.POST, instance=perfil, user=request.user)
            if cuenta_form.is_valid():
                cuenta_form.save()
                messages.success(request, 'Datos de cuenta actualizados.')
                return redirect('usuarios:perfil')

        elif 'cambiar_password' in request.POST:
            password_form = CambiarPasswordForm(user=request.user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                messages.success(request, 'Contraseña cambiada exitosamente.')
                return redirect('usuarios:perfil')
    
    return render(request, 'usuarios/perfil.html', {
        'perfil_form': perfil_form,
        'cuenta_form': cuenta_form,
        'password_form': password_form,
        'perfil': perfil
    })


@login_required
def configuracion_sistema(request):
    """Vista para editar solo la configuración del sistema (valores predeterminados)"""
    from .forms import ConfiguracionSistemaForm, PersonalizarMenuForm
    try:
        perfil = request.user.perfil
    except PerfilUsuario.DoesNotExist:
        perfil = PerfilUsuario.objects.create(usuario=request.user)
    
    perfil.refresh_from_db()
    
    # Crear formulario solo con campos de configuración del sistema
    perfil_form = ConfiguracionSistemaForm(instance=perfil, user=request.user)
    permisos_form = PersonalizarMenuForm(instance=perfil)
    password_form = CambiarPasswordForm(user=request.user)  # Necesario para el template
    mostrar_tab_funcionalidades = False
    
    if request.method == "POST":
        if 'editar_permisos_menu' in request.POST:
            permisos_form = PersonalizarMenuForm(request.POST, instance=perfil)
            if permisos_form.is_valid():
                permisos_form.save()
                messages.success(
                    request,
                    'Menú personalizado. Tus datos y permisos de acceso se conservan.',
                )
                url = reverse('usuarios:configuracion_sistema') + '?tab=funcionalidades'
                return redirect(url)
            messages.error(request, 'Por favor corrige los errores al personalizar el menú.')
            mostrar_tab_funcionalidades = True
        elif 'editar_configuracion' in request.POST:
            perfil_form = ConfiguracionSistemaForm(request.POST, instance=perfil, user=request.user)
            if perfil_form.is_valid():
                perfil_form.save()
                perfil.refresh_from_db()

                # Sincronizar preferencias de configuración de sistema a sesión
                request.session['unidad_medida_predeterminada'] = perfil.unidad_medida_predeterminada
                request.session['tamanio_fuente'] = perfil.tamanio_fuente
                request.session['tema_preferido'] = perfil.tema_preferido

                messages.success(request, 'Configuración del sistema actualizada exitosamente.')
                return redirect('usuarios:configuracion_sistema')
            else:
                primer_error = next(iter(perfil_form.errors.values()), None)
                detalle = primer_error[0] if primer_error else None
                mensaje = 'Por favor corrige los errores en el formulario.'
                if detalle:
                    mensaje = f'{mensaje} {detalle}'
                messages.error(request, mensaje)
                if settings.DEBUG:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Errores del formulario: {perfil_form.errors}")
                    print(f"Errores del formulario: {perfil_form.errors}")
    
    return render(request, 'usuarios/configuracion_sistema.html', {
        'perfil_form': perfil_form,
        'permisos_form': permisos_form,
        'password_form': password_form,
        'perfil': perfil,
        'mostrar_tab_funcionalidades': mostrar_tab_funcionalidades,
    })


@login_required
@require_POST
def completar_tutorial(request):
    perfil, _ = PerfilUsuario.objects.get_or_create(usuario=request.user)
    perfil.tutorial_completado = True
    perfil.save(update_fields=['tutorial_completado'])
    return JsonResponse({'success': True, 'message': 'Tutorial marcado como completado'})


@never_cache
def recuperar_password(request):
    form = FormularioRecuperacion(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        form.enviar(request)
        messages.success(
            request, 'Si el correo existe en nuestro sistema, recibirás las instrucciones para recuperar tu contraseña.'
        )
        return redirect('usuarios:login')
    return render(request, 'usuarios/recuperar_password.html', {'form': form})


class ConfirmarRecuperacionView(PasswordResetConfirmView):
    template_name = 'usuarios/reset_password_confirm.html'
    success_url = reverse_lazy('usuarios:login')

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        response.headers.setdefault('Referrer-Policy', 'no-referrer')
        return response

    def get_user(self, uidb64):
        usuario = super().get_user(uidb64)
        return usuario if usuario and usuario.is_active else None

    def render_to_response(self, context, **response_kwargs):
        if not self.validlink:
            messages.error(self.request, 'El enlace de recuperación no es válido o ha expirado. Por favor solicita uno nuevo.')
            return redirect('usuarios:recuperar_password')
        response = super().render_to_response(context, **response_kwargs)
        # Django ya retiró el token de la URL. El formulario necesita conservar Origin para CSRF.
        response.headers['Referrer-Policy'] = 'same-origin'
        return response

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Tu contraseña ha sido restablecida. Puedes iniciar sesión ahora.')
        return response


@never_cache
def csrf_failure(request, reason=''):
    """Rechazar el envío y ofrecer navegación GET segura, sin reintentar la operación."""
    destino = reverse('cutless:index') if request.user.is_authenticated else reverse('usuarios:login')
    mensaje = 'Este formulario ya no es válido. Puede ocurrir al retroceder después de iniciar sesión, abrir otra sesión o dejar una página abierta durante mucho tiempo.'
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', ''):
        return JsonResponse({'error': 'formulario_desactualizado', 'message': mensaje, 'recovery_url': destino}, status=403)
    return render(request, 'usuarios/formulario_desactualizado.html', {
        'ocultar_tutorial': True, 'recovery_url': destino,
        'recovery_label': 'Continuar en Inicio' if request.user.is_authenticated else 'Volver a iniciar sesión',
        'mensaje_recuperacion': mensaje,
    }, status=403)
