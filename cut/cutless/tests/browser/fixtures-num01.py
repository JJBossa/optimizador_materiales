"""Datos sintéticos para el recorrido de NUM-01 en SQLite desechable."""
import json
import os
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from cutless.models import Optimizacion


if settings.CUTLESS_ENV != 'development' or settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
    raise SystemExit('NUM-01 requiere SQLite local en desarrollo.')
if User.objects.exists():
    raise SystemExit('NUM-01 requiere una base vacía y desechable.')

with Path(os.environ['CUTLESS_TEST_FIXTURE']).open('x', encoding='utf-8') as salida:
    usuario = User.objects.create_superuser('num01_chromium')
    usuario.perfil.tutorial_completado = True
    usuario.perfil.preferencias_menu = {'_inicio_completado': True}
    usuario.perfil.save()
    plan = Optimizacion.objects.create(usuario=usuario, nombre='Plan sintético NUM-01', ancho_tablero=122,
                                      alto_tablero=244, piezas='Puerta,20,30,1', num_tableros=1)
    cliente = Client()
    cliente.force_login(usuario)
    rutas = {vista: reverse(f'cutless:{vista}') for vista in (
        'crear_material', 'lista_materiales', 'historial', 'crear_presupuesto', 'crear_plantilla',
    )}
    json.dump({'session': cliente.cookies['sessionid'].value, 'rutas': rutas, 'plan': plan.pk}, salida)
