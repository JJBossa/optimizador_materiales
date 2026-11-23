"""Datos sintéticos para comparar acciones de gestión en dos servidores locales."""

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
    raise SystemExit('Usa una SQLite desechable en desarrollo.')
if User.objects.exists():
    raise SystemExit('La prueba requiere una base vacía.')

usuario = User.objects.create_superuser('vis02_sintetico')
usuario.perfil.preferencias_menu = {'_inicio_completado': True}
usuario.perfil.tutorial_completado = True
usuario.perfil.save()
User.objects.create_user('vis02_cuenta_administrable')
Material.objects.create(nombre='MDF de catálogo', ancho=122, alto=244, es_predefinido=True, precio=14000)
Plantilla.objects.create(nombre='Plantilla del sistema', ancho_tablero=122, alto_tablero=244,
                         es_predefinida=True, piezas='Puerta,20,30,1')
for indice, nombre in enumerate(('Armario', 'Biblioteca', 'Escritorio', 'Vitrina', 'Repisas'), start=1):
    cliente = Cliente.objects.create(usuario=usuario, nombre=f'Cliente {indice}',
                                     email=f'cliente{indice}@ejemplo.invalid')
    proyecto = Proyecto.objects.create(
        usuario=usuario, nombre=nombre, cliente=cliente,
        estado=('planificacion', 'en_proceso', 'completado', 'cancelado', 'planificacion')[indice - 1],
    )
    material = Material.objects.create(usuario=usuario, nombre=f'Tablero {indice}', ancho=122, alto=244, precio=15000)
    Plantilla.objects.create(usuario=usuario, nombre=f'Plantilla {nombre}', ancho_tablero=122, alto_tablero=244,
                             piezas='Puerta,20,30,1')
    plan = Optimizacion.objects.create(usuario=usuario, nombre=f'Corte {nombre}', cliente=cliente,
                                       proyecto=proyecto, material=material, ancho_tablero=122, alto_tablero=244,
                                       piezas='Puerta,20,30,1', num_tableros=1, precio_tablero=15000)
    presupuesto = Presupuesto.objects.create(
        usuario=usuario, cliente=cliente, proyecto=proyecto, numero=f'PRE-VIS02-{indice}',
        estado=('enviado', 'aceptado', 'rechazado', 'vencido', 'borrador')[indice - 1],
        precio_tablero=15000, costo_total=15000, fecha_validez=timezone.localdate() + timedelta(days=30),
    )
    presupuesto.optimizaciones.add(plan)

Optimizacion.objects.create(usuario=usuario, nombre='Corte sin proyecto', ancho_tablero=122, alto_tablero=244,
                            piezas='Puerta,20,30,1', num_tableros=1)

rutas = {
    clave: reverse('cutless:' + vista, args=args)
    for clave, vista, args in (
        ('proyectos', 'lista_proyectos', []), ('presupuestos', 'lista_presupuestos', []),
        ('clientes', 'lista_clientes', []), ('materiales', 'lista_materiales', []),
        ('plantillas', 'lista_plantillas', []), ('historial', 'historial', []),
        ('proyecto', 'detalle_proyecto', [proyecto.pk]), ('presupuesto', 'detalle_presupuesto', [presupuesto.pk]),
        ('historialCliente', 'historial_cliente', [cliente.pk]), ('costos', 'historial_costos', []),
        ('asociar', 'agregar_optimizaciones_proyecto', [proyecto.pk]),
    )
}
rutas['admin'] = reverse('usuarios:admin_dashboard')
sesion = Client()
sesion.force_login(usuario)
with Path(os.environ['CUTLESS_TEST_FIXTURE']).open('x', encoding='utf-8') as salida:
    json.dump({'session': sesion.cookies['sessionid'].value, 'rutas': rutas}, salida)
