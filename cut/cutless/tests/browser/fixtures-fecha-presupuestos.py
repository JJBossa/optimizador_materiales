"""Datos sintéticos para probar la fecha de validez en Chromium."""

import json
import os
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from cutless.models import Cliente, Optimizacion, Proyecto


if settings.CUTLESS_ENV != 'development' or settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
    raise SystemExit('Usa una base SQLite desechable en desarrollo.')
if User.objects.filter(username='pre01_cuenta_sintetica').exists():
    raise SystemExit('El escenario PRE-01 ya está cargado.')

usuario = User.objects.create_user('pre01_cuenta_sintetica')
usuario.perfil.puede_crear_presupuestos = True
usuario.perfil.preferencias_menu = {'_inicio_completado': True}
usuario.perfil.tutorial_completado = True
usuario.perfil.save()
cliente = Cliente.objects.create(usuario=usuario, nombre='Cliente sintético PRE-01')
proyecto = Proyecto.objects.create(usuario=usuario, nombre='Proyecto sintético PRE-01', cliente=cliente)
plan = Optimizacion.objects.create(
    usuario=usuario, cliente=cliente, proyecto=proyecto, nombre='Plan sintético PRE-01',
    ancho_tablero=122, alto_tablero=244, piezas='Puerta,40,50,1', num_tableros=2,
)
sesion = Client()
sesion.force_login(usuario)
hoy = timezone.localdate()

with Path(os.environ['CUTLESS_TEST_FIXTURE']).open('x', encoding='utf-8') as salida:
    json.dump({
        'session': sesion.cookies['sessionid'].value,
        'crear': reverse('cutless:crear_presupuesto'),
        'hoy': hoy.isoformat(),
        'ayer': (hoy - timedelta(days=1)).isoformat(),
        'cliente': cliente.pk,
        'proyecto': proyecto.pk,
        'plan': plan.pk,
    }, salida)
