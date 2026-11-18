"""Permisos funcionales compartidos por formularios y vistas."""

PERMISOS_ADMIN_EXPLICITOS = {
    'puede_crear_materiales',
    'puede_crear_clientes',
    'puede_crear_proyectos',
    'puede_crear_presupuestos',
    'puede_crear_plantillas',
    'puede_ver_estadisticas',
    'puede_ver_historial_costos',
    'puede_comparar_optimizaciones',
}


def usuario_tiene_permiso(usuario, permiso_nombre):
    """Evalúa permisos funcionales sin aplicar un bypass global por rol."""
    if not getattr(usuario, 'is_authenticated', False):
        return False

    if getattr(usuario, 'is_superuser', False):
        return True

    perfil = getattr(usuario, 'perfil', None)
    if perfil is None:
        return False

    if getattr(perfil, 'rol', None) == 'admin' and permiso_nombre in PERMISOS_ADMIN_EXPLICITOS:
        return True

    return bool(getattr(perfil, permiso_nombre, False))
