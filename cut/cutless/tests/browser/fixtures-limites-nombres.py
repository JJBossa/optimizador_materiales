"""Prepara el recorrido VAL-01B en una SQLite local vacía."""
import json
import os
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from cutless.models import Optimizacion, Plantilla
from cutless.pieces import serializar_piezas


if settings.CUTLESS_ENV != 'development' or settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
    raise SystemExit('Usa una base SQLite desechable en desarrollo.')
if User.objects.exists():
    raise SystemExit('El escenario requiere una base vacía.')

salida = Path(os.environ['CUTLESS_TEST_FIXTURE'])
with salida.open('x', encoding='utf-8') as archivo:
    usuario = User.objects.create_user('histórico_27.' + 'ñ' * 35, email='antiguo@example.test')
    perfil = usuario.perfil
    perfil.rol = 'admin'
    perfil.tutorial_completado = True
    perfil.preferencias_menu = {'_inicio_completado': True}
    perfil.save()
    cliente = Client()
    cliente.force_login(usuario)

    nombre_trabajo = '  Taller  ' + 'ñ' * 51 + ' '
    trabajos = [
        Optimizacion.objects.create(
            usuario=usuario, nombre=nombre_trabajo, ancho_tablero=122, alto_tablero=244,
            piezas='Puerta,40,50,1', num_tableros=1,
        ) for _ in range(6)
    ]
    nombre_pieza = '  Frente, "norte", ' + 'ñ' * 20 + '\r\nNivel 2 '
    piezas = serializar_piezas([{'nombre': nombre_pieza, 'ancho': 40, 'alto': 50, 'cantidad': 1}])
    plantillas = [
        Plantilla.objects.create(
            usuario=usuario, nombre=f'Plantilla histórica {indice}', ancho_tablero=122, alto_tablero=244,
            piezas=piezas,
        ) for indice in range(6)
    ]
    json.dump({
        'sesion': cliente.cookies[settings.SESSION_COOKIE_NAME].value,
        'usuario': usuario.username,
        'trabajo': nombre_trabajo,
        'perfil': reverse('usuarios:perfil'),
        'registro': reverse('usuarios:registro'),
        'inicio': reverse('cutless:index'),
        'historial': reverse('cutless:historial'),
        'presupuesto': reverse('cutless:crear_presupuesto'),
        'plantillas': [reverse('cutless:editar_plantilla', args=[plantilla.pk]) for plantilla in plantillas],
        'nombre_pieza_visible': nombre_pieza.replace('\r\n', '\n'),
        'renombrar': [reverse('cutless:renombrar_optimizacion', args=[plan.pk]) for plan in trabajos],
    }, archivo)
