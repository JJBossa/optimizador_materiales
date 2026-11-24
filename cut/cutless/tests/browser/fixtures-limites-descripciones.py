"""Registros sintéticos para verificar VAL-03 en una SQLite local vacía."""
import json
import os
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from cutless.models import Cliente, Material, Optimizacion, Plantilla, Presupuesto, Proyecto

if settings.CUTLESS_ENV != 'development' or settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
    raise SystemExit('Usa SQLite en desarrollo.')
if User.objects.exists():
    raise SystemExit('La prueba requiere una base vacía.')

usuario = User.objects.create_superuser('val03_sintetico')
usuario.perfil.preferencias_menu = {'_inicio_completado': True}
usuario.perfil.tutorial_completado = True
usuario.perfil.save()
texto = '  Inicio\r\n' + 'Taller ñ 🪵 · ' * 17 + '\rDetalle\n  '
hoy = timezone.localdate()
material = Material.objects.create(usuario=usuario, nombre='Material sintético', ancho=122, alto=244, descripcion=texto)
otro_material = Material.objects.create(usuario=usuario, nombre='Material sin JS', ancho=122, alto=244, descripcion=texto)
cliente = Cliente.objects.create(usuario=usuario, nombre='Cliente sintético', notas=texto)
proyecto = Proyecto.objects.create(usuario=usuario, nombre='Proyecto sintético', fecha_inicio=hoy-timedelta(days=5),
                                    descripcion=texto)
piezas = 'Puerta,40,50,1'
plantilla = Plantilla.objects.create(usuario=usuario, nombre='Plantilla sintética', ancho_tablero=122,
                                     alto_tablero=244, piezas=piezas, descripcion=texto)
plan = Optimizacion.objects.create(usuario=usuario, ancho_tablero=122, alto_tablero=244, piezas=piezas, num_tableros=1)
presupuesto = Presupuesto.objects.create(usuario=usuario, cliente=cliente, fecha_validez=hoy, notas=texto,
                                          precio_tablero=1000, mano_obra=0, costo_total=1000)
presupuesto.optimizaciones.add(plan)
registros = {'material': material, 'cliente': cliente, 'proyecto': proyecto,
             'plantilla': plantilla, 'presupuesto': presupuesto}
rutas = {
    nombre: {'alta': reverse(f'cutless:crear_{nombre}'),
             'edicion': reverse(f'cutless:editar_{nombre}', args=[registro.pk])}
    for nombre, registro in registros.items()
}
rutas['sin_js'] = reverse('cutless:editar_material', args=[otro_material.pk])

sesion = Client()
sesion.force_login(usuario)
with Path(os.environ['CUTLESS_TEST_FIXTURE']).open('x', encoding='utf-8') as salida:
    json.dump({'session': sesion.cookies['sessionid'].value, 'rutas': rutas, 'texto': texto}, salida)
