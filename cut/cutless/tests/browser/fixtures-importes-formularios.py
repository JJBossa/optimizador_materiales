"""Datos sintéticos para revisar importes de formularios en Chromium."""

import json
import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from cutless.models import Material, Optimizacion, Presupuesto


if settings.CUTLESS_ENV != 'development' or settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
    raise SystemExit('Usa una SQLite desechable en desarrollo.')
if User.objects.exists():
    raise SystemExit('La prueba requiere una base vacía.')

usuario = User.objects.create_superuser('vis05_sintetico')
perfil = usuario.perfil
perfil.preferencias_menu = {'_inicio_completado': True}
perfil.tutorial_completado = True
perfil.precio_tablero_predeterminado = Decimal('10000.00')
perfil.mano_obra_predeterminada = Decimal('5500.00')
perfil.save()

importes = {'entero': '10000.00', 'medio': '12500.50', 'centavos': '12500.25', 'cero': '0.00', 'vacio': None}
materiales = {clave: Material.objects.create(usuario=usuario, nombre=f'Material sintético {clave}',
                                           ancho=122.1234, alto=244, precio=valor)
              for clave, valor in importes.items()}
planes = {}
presupuestos = {}
for clave, precio, mano in (('entero', '10000.00', '5500.00'), ('fraccion', '12500.50', '12500.25'),
                           ('cero', '0.00', '0.00'), ('vacio', None, '0.00')):
    plan = Optimizacion.objects.create(
        usuario=usuario, nombre=f'Plan sintético {clave}', ancho_tablero=122.1234, alto_tablero=244,
        margen_corte=.125, piezas='Pieza,40,50,1', num_tableros=2, precio_tablero=precio, mano_obra=mano,
    )
    planes[clave] = plan
    if precio is not None:
        presupuesto = Presupuesto.objects.create(
            usuario=usuario, numero=f'VIS05-{clave}', precio_tablero=precio, mano_obra=mano,
            costo_total=Decimal(precio) * 2 + Decimal(mano), fecha_validez=timezone.localdate() + timedelta(days=10),
        )
        presupuesto.optimizaciones.add(plan)
        presupuestos[clave] = presupuesto

sesion = Client()
sesion.force_login(usuario)
rutas = {
    'material_nuevo': reverse('cutless:crear_material'),
    'material_admin_nuevo': reverse('admin:cutless_material_add'),
    'presupuesto_nuevo': reverse('cutless:crear_presupuesto'),
    'opt_nueva': reverse('cutless:index'),
    'opt_admin_nueva': reverse('admin:cutless_optimizacion_add'),
    'perfil_admin': reverse('admin:usuarios_perfilusuario_change', args=[perfil.pk]),
    'perfil_admin_nuevo': reverse('admin:usuarios_perfilusuario_add'),
}
for clave, registro in materiales.items():
    rutas[f'material_{clave}'] = reverse('cutless:editar_material', args=[registro.pk])
    rutas[f'material_admin_{clave}'] = reverse('admin:cutless_material_change', args=[registro.pk])
for clave, registro in planes.items():
    rutas[f'opt_{clave}'] = reverse('cutless:editar_optimizacion', args=[registro.pk])
    rutas[f'opt_admin_{clave}'] = reverse('admin:cutless_optimizacion_change', args=[registro.pk])
    rutas[f'presupuesto_desde_{clave}'] = f'{rutas["presupuesto_nuevo"]}?optimizacion={registro.pk}'
for clave, registro in presupuestos.items():
    rutas[f'presupuesto_{clave}'] = reverse('cutless:editar_presupuesto', args=[registro.pk])

with Path(os.environ['CUTLESS_TEST_FIXTURE']).open('x', encoding='utf-8') as salida:
    json.dump({'session': sesion.cookies['sessionid'].value, 'rutas': rutas,
               'materiales': {clave: item.pk for clave, item in materiales.items()}, 'plan': planes['entero'].pk}, salida)
