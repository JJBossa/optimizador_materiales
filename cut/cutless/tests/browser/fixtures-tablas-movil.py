"""Crear una sesión y datos sintéticos en una SQLite local vacía."""
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

from cutless.models import Cliente, Material, Optimizacion, Presupuesto, Proyecto
from cutless.services.optimization import obtener_resultado_optimizacion

database = settings.DATABASES['default']
if settings.CUTLESS_ENV != 'development' or database['ENGINE'] != 'django.db.backends.sqlite3':
    raise SystemExit('La prueba requiere SQLite en desarrollo.')
if User.objects.exists():
    raise SystemExit('Usa una base de datos vacía y desechable para la prueba.')
output = Path(os.environ['CUTLESS_TEST_FIXTURE'])
if output.exists():
    raise SystemExit('Elige un archivo de prueba nuevo para guardar la sesión.')
owner = User.objects.create_superuser('control_tablas', 'control@ejemplo.invalid')
owner.perfil.tema_preferido = 'auto'
owner.perfil.preferencias_menu = {'_inicio_completado': True}
owner.perfil.tutorial_completado = True
owner.perfil.save()
for index in range(17):
    User.objects.create_user(f'control_usuario_{index}' + 'visual' * 15,
                             email='correo' * 9 + f'{index}@ejemplo.invalid')

contact = Cliente.objects.create(usuario=owner, nombre='Cliente' + 'SinEspacios' * 12,
                                 email='contacto' * 7 + '@ejemplo.invalid', rut='12345678-5',
                                 telefono='+56912345678', direccion='Dirección de prueba')
disposable = Cliente.objects.create(usuario=owner, nombre='ClienteEliminable')
price = Decimal('12345678.90')
material = Material.objects.create(usuario=owner, nombre='Material' + 'Roble' * 16,
                                   ancho=122, alto=244, precio=price)
Material.objects.create(nombre='Material de sistema de prueba', ancho=122, alto=244,
                        precio=Decimal('18293.25'), es_predefinido=True)
project = Proyecto.objects.create(usuario=owner, cliente=contact, nombre='Proyecto' + 'SinEspacios' * 12)
first = Optimizacion.objects.create(usuario=owner, nombre='Plan' + 'Tablero' * 12,
                                    cliente=contact, proyecto=project, material=material,
                                    ancho_tablero=122, alto_tablero=244,
                                    piezas='PiezaPrincipal,61,122,7\nRetal,20,40,2',
                                    precio_tablero=price, mano_obra=Decimal('14530.75'))
alternative = Optimizacion.objects.create(usuario=owner, nombre='Otra alternativa', ancho_tablero=130,
                                          alto_tablero=250, piezas=first.piezas, precio_tablero=price)
for index in range(12):
    Optimizacion.objects.create(usuario=owner, nombre=f'Muestra {index}', ancho_tablero=122,
                                alto_tablero=244, piezas='Pieza,40,40,2', num_tableros=1,
                                aprovechamiento_total=65 + index, precio_tablero=price)

client = Client(HTTP_HOST='127.0.0.1')
client.force_login(owner)
for plan in (first, alternative):
    obtener_resultado_optimizacion(plan)
    response = client.get(reverse('cutless:resultado', args=[plan.pk]))
    if response.status_code != 200:
        raise RuntimeError(f'No se pudo preparar el resultado sintético: HTTP {response.status_code}')
    plan.refresh_from_db()
    if not plan.num_tableros:
        raise RuntimeError('El resultado sintético debe tener al menos un tablero.')

budget = Presupuesto.objects.create(usuario=owner, proyecto=project, cliente=contact,
                                     numero='PRE-PRUEBA-MOVIL', precio_tablero=price,
                                     mano_obra=Decimal('14530.75'), costo_total=Decimal('0.00'),
                                     fecha_validez=timezone.localdate() + timedelta(days=30))
budget.optimizaciones.add(first)

views = {
    'clientes': ('lista_clientes', []),
    'materiales': ('lista_materiales', []),
    'proyectos': ('lista_proyectos', []),
    'presupuestos': ('lista_presupuestos', []),
    'detalleProyecto': ('detalle_proyecto', [project.pk]),
    'detallePresupuesto': ('detalle_presupuesto', [budget.pk]),
    'clienteHistorial': ('historial_cliente', [contact.pk]),
    'costos': ('historial_costos', []),
    'estadisticas': ('estadisticas', []),
    'resultado': ('resultado', [first.pk]),
    'historial': ('historial', []),
    'comparar': ('comparar_optimizaciones', []),
    'tiempo': ('calcular_tiempo_corte', [first.pk]),
    'asociar': ('agregar_optimizaciones_proyecto', [project.pk]),
    'crearProyecto': ('crear_proyecto', []),
    'crearPresupuesto': ('crear_presupuesto', []),
    'imprimir': ('imprimir_plan_corte', [first.pk]),
    'eliminarCliente': ('eliminar_cliente', [disposable.pk]),
}
routes = {name: reverse(f'cutless:{view}', args=args) for name, (view, args) in views.items()}
routes['comparar'] += f'?opt1={first.pk}&opt2={alternative.pk}'
routes['historial'] += f'?nombre_pieza={first.codigo}'
routes['admin'] = reverse('usuarios:admin_dashboard')
descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(descriptor, 'w', encoding='utf-8') as result:
    json.dump({'session': client.cookies['sessionid'].value, 'plan': first.pk, 'routes': routes}, result)
