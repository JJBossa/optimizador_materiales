"""Alertas sintéticas para verificar NOTI-01 con Chromium y SQLite local."""
import json
import os
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from cutless.models import Presupuesto, Proyecto
from cutless.services.calendario import fecha_comercial


if settings.CUTLESS_ENV != 'development' or settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
    raise SystemExit('Usa una base SQLite desechable en desarrollo.')
if User.objects.exists():
    raise SystemExit('El recorrido requiere una base vacía.')

hoy = fecha_comercial()
sesiones = {}
nombres = {
    'inicio': 'Inicio pendiente sintético',
    'atrasado': 'Proyecto atrasado sintético',
    'finaliza': 'Finaliza hoy sintético',
    'especial': '<img src=x> «Taller Ñ» ' + 'Texto largo ' * 10,
}


def cuenta(clave, tema, fuente='normal', pantalla=True):
    usuario = User.objects.create_user(f'noti01_sintetico_{clave}')
    perfil = usuario.perfil
    perfil.tema_preferido = tema
    perfil.tamanio_fuente = fuente
    perfil.notificaciones_pantalla = pantalla
    perfil.tutorial_completado = True
    perfil.preferencias_menu = {'_inicio_completado': True}
    perfil.save()
    sesion = Client()
    sesion.force_login(usuario)
    sesiones[clave] = sesion.cookies[settings.SESSION_COOKIE_NAME].value
    return usuario


for ancho, tema, fuente in ((320, 'auto', 'xlarge'), (390, 'light', 'normal'),
                            (768, 'auto', 'large'), (1440, 'dark', 'normal')):
    usuario = cuenta(ancho, tema, fuente)
    for nombre, estado, dias in (
        ('PRE-VENCIDO', 'emitido', -1), ('PRE-PROXIMO', 'enviado', 1), ('PRE-ENVIO', 'emitido', 7),
        ('PRE-ACEPTADO', 'aceptado', -1), ('PRE-RECHAZADO', 'rechazado', 0),
    ):
        Presupuesto.objects.create(
            usuario=usuario, numero=nombre, estado=estado, fecha_validez=hoy + timedelta(days=dias),
            precio_tablero=20, costo_total=80, detalle_emitido={'cliente': None, 'optimizaciones': []},
        )
    proyectos = (
        (nombres['inicio'], 'planificacion', hoy - timedelta(days=3), None),
        (nombres['atrasado'], 'en_proceso', None, hoy - timedelta(days=2)),
        (nombres['finaliza'], 'en_proceso', None, hoy),
        (nombres['especial'], 'planificacion', hoy, None),
        ('Completado excluido', 'completado', hoy - timedelta(days=4), hoy - timedelta(days=1)),
        ('Cancelado excluido', 'cancelado', hoy, hoy),
    )
    Proyecto.objects.bulk_create([
        Proyecto(usuario=usuario, nombre=nombre, estado=estado, fecha_inicio=inicio, fecha_fin=fin)
        for nombre, estado, inicio, fin in proyectos
    ])
    if ancho == 320:
        Proyecto.objects.bulk_create([
            Proyecto(usuario=usuario, nombre=f'Datos sintéticos de volumen {i}', fecha_inicio=hoy)
            for i in range(105)
        ])

otro = cuenta('otro', 'light')
Proyecto.objects.create(usuario=otro, nombre='Proyecto ajeno sintético', fecha_fin=hoy - timedelta(days=1))
cuenta('vacio', 'light')
silencio = cuenta('silencio', 'light', pantalla=False)
Proyecto.objects.create(usuario=silencio, nombre='Proyecto de avisos deshabilitados', fecha_inicio=hoy)

with Path(os.environ['CUTLESS_TEST_FIXTURE']).open('x', encoding='utf-8') as salida:
    json.dump({
        'session': sesiones[390], 'sesiones': sesiones, 'nombres': nombres,
        'api': reverse('cutless:api_alertas'), 'centro': reverse('cutless:centro_alertas'),
        'inicio': reverse('cutless:index'), 'futura': (hoy + timedelta(days=5)).isoformat(),
        'configuracion': reverse('usuarios:configuracion_sistema'),
    }, salida)
