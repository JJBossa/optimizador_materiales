"""Datos sintéticos para el navegador en SQLite de desarrollo."""
import json
import os
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from cutless.models import Cliente


if settings.CUTLESS_ENV != 'development' or settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
    raise SystemExit('Usa una base SQLite desechable en desarrollo.')
if User.objects.exists() or Cliente.objects.exists():
    raise SystemExit('Este escenario requiere una base vacía.')

usuario = User.objects.create_user('cli02_cuenta_sintetica')
usuario.perfil.puede_crear_clientes = True
usuario.perfil.preferencias_menu = {'_inicio_completado': True}
usuario.perfil.tutorial_completado = True
usuario.perfil.save()
Cliente.objects.create(usuario=usuario, nombre='Ficha sintética con RUT', rut='1.000.005-k')
sesion = Client()
sesion.force_login(usuario)
direccion = '  Pasaje Chromium 12-A\r\nUnidad S/N\n  Texto <legado>  '
ediciones = {}
for modo in ('js', 'html'):
    for ancho in (320, 390, 768, 1280):
        nombre = f'CLI-02 Editar {modo}-{ancho}'
        cliente = Cliente.objects.create(usuario=usuario, nombre=nombre, direccion=direccion)
        ediciones[f'{modo}-{ancho}'] = {
            'editar': reverse('cutless:editar_cliente', args=[cliente.pk]),
            'historial': reverse('cutless:historial_cliente', args=[cliente.pk]),
        }

with Path(os.environ['CUTLESS_TEST_FIXTURE']).open('x', encoding='utf-8') as salida:
    json.dump({
        'session': sesion.cookies['sessionid'].value,
        'crear': reverse('cutless:crear_cliente'),
        'lista': reverse('cutless:lista_clientes'),
        'ediciones': ediciones,
        'direccion': direccion,
    }, salida)
