"""Prepara VAL-02 en una SQLite local vacía."""
import json
import os
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from cutless.models import Optimizacion, Proyecto


if settings.CUTLESS_ENV != 'development' or settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
    raise SystemExit('Usa una base SQLite desechable en desarrollo.')
if User.objects.exists():
    raise SystemExit('El escenario requiere una base vacía.')

with Path(os.environ['CUTLESS_TEST_FIXTURE']).open('x', encoding='utf-8') as salida:
    usuario = User.objects.create_user('val02_navegador')
    usuario.perfil.puede_crear_proyectos = True
    usuario.perfil.tutorial_completado = True
    usuario.perfil.preferencias_menu = {'_inicio_completado': True}
    usuario.perfil.save()

    hoy = timezone.localdate(timezone=ZoneInfo('America/Santiago'))
    ayer = hoy - timedelta(days=1)
    inicio = hoy - timedelta(days=30)
    proyecto = Proyecto.objects.create(usuario=usuario, nombre='Proyecto histórico',
                                       fecha_inicio=inicio, fecha_fin=ayer)
    Optimizacion.objects.create(usuario=usuario, proyecto=proyecto, ancho_tablero=122,
                                alto_tablero=244, piezas='Puerta,40,50,1')
    sesion = Client()
    sesion.force_login(usuario)
    json.dump({
        'sesion': sesion.cookies[settings.SESSION_COOKIE_NAME].value,
        'alta': reverse('cutless:crear_proyecto'),
        'edicion': reverse('cutless:editar_proyecto', args=[proyecto.pk]),
        'detalle': reverse('cutless:detalle_proyecto', args=[proyecto.pk]),
        'inicio': inicio.isoformat(),
        'ayer': ayer.isoformat(),
        'hoy': hoy.isoformat(),
        'manana': (hoy + timedelta(days=1)).isoformat(),
    }, salida)
