"""Registros sintéticos para el recorrido PRE-03 en SQLite local."""
import json
import os
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from cutless.models import Cliente, Optimizacion, Presupuesto
from cutless.services.presupuestos import fecha_comercial


if settings.CUTLESS_ENV != 'development' or settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
    raise SystemExit('Usa una base SQLite desechable en desarrollo.')
if User.objects.exists():
    raise SystemExit('El recorrido requiere una base vacía.')

usuario = User.objects.create_user('pre03_sintetico')
perfil = usuario.perfil
perfil.puede_crear_presupuestos = True
perfil.preferencias_menu = {'_inicio_completado': True}
perfil.tutorial_completado = True
perfil.save()
cliente = Cliente.objects.create(usuario=usuario, nombre='Cliente sintético PRE-03')
plan = Optimizacion.objects.create(
    usuario=usuario, cliente=cliente, nombre='Plan de prueba PRE-03', ancho_tablero=122, alto_tablero=244,
    piezas='Frente,20,30,1', num_tableros=2,
)
hoy = fecha_comercial()
ayer = hoy - timedelta(days=1)
borradores = {}
for ancho in (320, 390, 768, 1440):
    presupuesto = Presupuesto.objects.create(
        usuario=usuario, cliente=cliente, numero=f'BORRADOR-{ancho}', precio_tablero=100, mano_obra=10,
        costo_total=210, fecha_validez=ayer, notas='Nota histórica sintética',
    )
    presupuesto.optimizaciones.add(plan)
    borradores[ancho] = {
        'editar': reverse('cutless:editar_presupuesto', args=[presupuesto.pk]),
        'numero': presupuesto.numero,
    }
vencido = Presupuesto.objects.create(
    usuario=usuario, numero='PRE-VENCE-AYER', precio_tablero=100, mano_obra=10, costo_total=210,
    fecha_validez=ayer, estado='emitido', detalle_emitido={'cliente': None, 'optimizaciones': []},
)
vigente = Presupuesto.objects.create(
    usuario=usuario, numero='PRE-SIGUE-EMITIDO', precio_tablero=100, mano_obra=10, costo_total=210,
    fecha_validez=hoy, estado='emitido', detalle_emitido={'cliente': None, 'optimizaciones': []},
)
sesion = Client()
sesion.force_login(usuario)

with Path(os.environ['CUTLESS_TEST_FIXTURE']).open('x', encoding='utf-8') as salida:
    json.dump({
        'session': sesion.cookies['sessionid'].value, 'hoy': hoy.isoformat(), 'ayer': ayer.isoformat(),
        'alta': reverse('cutless:crear_presupuesto'), 'lista': reverse('cutless:lista_presupuestos'),
        'plan': plan.pk, 'cliente': cliente.pk, 'borradores': borradores, 'numero_vencido': vencido.numero,
        'numero_vigente': vigente.numero,
    }, salida)
