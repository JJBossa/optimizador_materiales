"""Proyectos sintéticos para el recorrido PRO-03 en SQLite local."""
import json
import os
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from cutless.models import Cliente, Proyecto
from cutless.services.calendario import fecha_comercial


if settings.CUTLESS_ENV != 'development' or settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
    raise SystemExit('Usa una base SQLite desechable en desarrollo.')
if User.objects.exists():
    raise SystemExit('El recorrido requiere una base vacía.')

usuario = User.objects.create_user('pro03_sintetico')
perfil = usuario.perfil
perfil.puede_crear_clientes = True
perfil.puede_crear_proyectos = True
perfil.preferencias_menu = {'_inicio_completado': True}
perfil.tutorial_completado = True
perfil.save()
cliente = Cliente.objects.create(usuario=usuario, nombre='Cliente sintético PRO-03')
hoy = fecha_comercial()
ayer = hoy - timedelta(days=1)
proyectos = {}
for ancho in (320, 390, 768, 1440):
    operativo = 'planificacion' if ancho in (320, 768) else 'en_proceso'
    proyecto = Proyecto.objects.create(
        usuario=usuario, cliente=cliente, nombre=f'Proyecto histórico {ancho}', fecha_fin=ayer,
        estado=operativo, descripcion='Mueble sintético',
    )
    proyectos[ancho] = {
        'editar': reverse('cutless:editar_proyecto', args=[proyecto.pk]),
        'detalle': reverse('cutless:detalle_proyecto', args=[proyecto.pk]),
        'nombre': proyecto.nombre, 'operativo': operativo,
    }
sesion = Client()
sesion.force_login(usuario)

with Path(os.environ['CUTLESS_TEST_FIXTURE']).open('x', encoding='utf-8') as salida:
    json.dump({
        'session': sesion.cookies['sessionid'].value, 'hoy': hoy.isoformat(), 'ayer': ayer.isoformat(),
        'manana': (hoy + timedelta(days=1)).isoformat(), 'proyectos': proyectos, 'cliente': cliente.pk,
        'alta': reverse('cutless:crear_proyecto'), 'lista': reverse('cutless:lista_proyectos'),
        'historial': reverse('cutless:historial_cliente', args=[cliente.pk]),
    }, salida)
