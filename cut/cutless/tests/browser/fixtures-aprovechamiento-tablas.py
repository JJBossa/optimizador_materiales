"""Prepara porcentajes sintéticos para las tablas de gestión en SQLite."""

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
from cutless.services.optimization import obtener_resultado_optimizacion


if settings.CUTLESS_ENV != 'development' or settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
    raise SystemExit('Usa una SQLite desechable en desarrollo.')
if User.objects.exists():
    raise SystemExit('Este escenario requiere una base vacía.')

usuario = User.objects.create_superuser('vis07_sintetico')
usuario.perfil.tema_preferido = 'auto'
usuario.perfil.preferencias_menu = {'_inicio_completado': True}
usuario.perfil.tutorial_completado = True
usuario.perfil.save()
cliente = Cliente.objects.create(usuario=usuario, nombre='Estudio VIS-07')
proyecto = Proyecto.objects.create(usuario=usuario, cliente=cliente, nombre='Mobiliario de muestra')
presupuesto = Presupuesto.objects.create(
    usuario=usuario, cliente=cliente, proyecto=proyecto, numero='PRE-VIS07',
    precio_tablero=18000, costo_total=72000, fecha_validez=timezone.localdate() + timedelta(days=30),
)

planes = []
for nombre, porcentaje in (('Cajonera', 10.6), ('Estante', 53.6), ('Biblioteca', 70), ('Panel', 100)):
    datos = dict(usuario=usuario, ancho_tablero=122, alto_tablero=244, piezas='Pieza,40,50,2',
                 precio_tablero=18000, num_tableros=1)
    plan = Optimizacion.objects.create(nombre=nombre, cliente=cliente, proyecto=proyecto, **datos)
    obtener_resultado_optimizacion(plan, generar_imagenes=False)
    Optimizacion.objects.filter(pk=plan.pk).update(aprovechamiento_total=porcentaje)
    Optimizacion.objects.create(nombre=f'{nombre} disponible', aprovechamiento_total=porcentaje, **datos)
    planes.append(plan)
presupuesto.optimizaciones.add(*planes)

sesion = Client()
sesion.force_login(usuario)
with Path(os.environ['CUTLESS_TEST_FIXTURE']).open('x', encoding='utf-8') as salida:
    json.dump({
        'session': sesion.cookies['sessionid'].value,
        'vistas': {
            'proyecto': reverse('cutless:detalle_proyecto', args=[proyecto.pk]),
            'seleccion': reverse('cutless:agregar_optimizaciones_proyecto', args=[proyecto.pk]),
            'cliente': reverse('cutless:historial_cliente', args=[cliente.pk]),
            'presupuesto': reverse('cutless:detalle_presupuesto', args=[presupuesto.pk]),
        },
        'resultado': reverse('cutless:resultado', args=[planes[0].pk]),
        'etiqueta': planes[0].etiqueta,
    }, salida)
