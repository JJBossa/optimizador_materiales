"""Cuatro estados de proyecto para Chromium en una SQLite desechable."""

import json
import os
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from cutless.models import Cliente, Proyecto


if settings.CUTLESS_ENV != 'development' or settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
    raise SystemExit('Usa una base SQLite desechable en desarrollo.')
if User.objects.exists():
    raise SystemExit('Este escenario requiere una base vacía.')

usuario = User.objects.create_user('vis01_cuenta_sintetica')
usuario.perfil.puede_crear_proyectos = True
usuario.perfil.preferencias_menu = {'_inicio_completado': True}
usuario.perfil.tutorial_completado = True
usuario.perfil.save()
cliente = Cliente.objects.create(usuario=usuario, nombre='Cliente sintético')
proyectos = [
    Proyecto.objects.create(usuario=usuario, cliente=cliente, nombre=nombre, estado=estado)
    for estado, nombre in (
        ('cancelado', 'Vitrina'), ('completado', 'Escritorio'),
        ('en_proceso', 'Biblioteca'), ('planificacion', 'Armario'),
    )
]
sesion = Client()
sesion.force_login(usuario)

with Path(os.environ['CUTLESS_TEST_FIXTURE']).open('x', encoding='utf-8') as salida:
    json.dump({
        'session': sesion.cookies['sessionid'].value,
        'lista': reverse('cutless:lista_proyectos'),
        'detalles': {
            proyecto.get_estado_display(): reverse('cutless:detalle_proyecto', args=[proyecto.pk])
            for proyecto in proyectos
        },
    }, salida)
