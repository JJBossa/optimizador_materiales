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

from cutless.models import Cliente, Optimizacion, Presupuesto, Proyecto


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
hoy = timezone.localdate(timezone=timezone.get_default_timezone())
vencida = hoy - timedelta(days=5)
edicion = []
for indice in range(4):
    borradores = {}
    for tipo, fecha in (('vigente', hoy + timedelta(days=3)), ('vencido', vencida)):
        presupuesto = Presupuesto.objects.create(
            usuario=usuario, cliente=cliente, proyecto=proyecto, numero=f'PRE-02-{indice + 1}-{tipo.upper()}',
            precio_tablero='150.50', mano_obra='25.25', costo_total='326.25', fecha_validez=fecha,
        )
        presupuesto.optimizaciones.add(plan)
        borradores[tipo] = reverse('cutless:editar_presupuesto', args=[presupuesto.pk])
    edicion.append(borradores)

with Path(os.environ['CUTLESS_TEST_FIXTURE']).open('x', encoding='utf-8') as salida:
    json.dump({
        'session': sesion.cookies['sessionid'].value,
        'crear': reverse('cutless:crear_presupuesto'),
        'hoy': hoy.isoformat(),
        'ayer': (hoy - timedelta(days=1)).isoformat(),
        'manana': (hoy + timedelta(days=1)).isoformat(),
        'vencida': vencida.isoformat(),
        'edicion': edicion,
        'cliente': cliente.pk,
        'proyecto': proyecto.pk,
        'plan': plan.pk,
    }, salida)
