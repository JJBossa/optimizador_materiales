"""Comprobación de plantillas usando una cuenta y una base temporales."""
from tempfile import TemporaryDirectory

from cutless_project.standalone import django_aislado


def comprobar_respuestas(cliente, rutas):
    fallos = []
    for ruta in rutas:
        respuesta = cliente.get(ruta)
        if respuesta.status_code != 200:
            fallos.append(f'{respuesta.status_code} {ruta}')
    if fallos:
        raise RuntimeError('Respuestas inesperadas:\n' + '\n'.join(fallos))
    return len(rutas)


def main():
    with TemporaryDirectory(prefix='cutless-smoke-') as tmp, django_aislado(tmp, ':memory:'):
        from django.contrib.auth import get_user_model
        from django.core.management import call_command
        from django.test import Client
        from django.urls import reverse

        call_command('migrate', verbosity=0, interactive=False)
        cliente = Client(raise_request_exception=False)
        total = comprobar_respuestas(cliente, [reverse(nombre) for nombre in (
            'usuarios:login', 'usuarios:registro', 'usuarios:recuperar_password',
        )])
        usuario = get_user_model().objects.create_user('smoke-local')
        usuario.perfil.rol = 'admin'
        usuario.perfil.preferencias_menu = {'_inicio_completado': True}
        usuario.perfil.save(update_fields=['rol', 'preferencias_menu'])
        cliente.force_login(usuario)
        total += comprobar_respuestas(cliente, [reverse(nombre) for nombre in (
            'usuarios:perfil', 'usuarios:configuracion_inicial', 'usuarios:configuracion_sistema',
            'usuarios:admin_dashboard', 'cutless:index', 'cutless:historial',
            'cutless:lista_materiales', 'cutless:lista_clientes', 'cutless:lista_proyectos',
            'cutless:lista_presupuestos', 'cutless:lista_plantillas', 'cutless:estadisticas',
            'cutless:historial_costos',
        )])
        print(f'{total} plantillas respondieron con HTTP 200.')


if __name__ == '__main__':
    main()
