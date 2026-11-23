"""Prepara el escenario de Clientes en una SQLite de pruebas vacía."""
import json
import os
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from cutless.models import Cliente


if settings.CUTLESS_ENV != 'development' or settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
    raise SystemExit('Usa una base SQLite desechable en desarrollo.')
if User.objects.exists() or Cliente.objects.exists():
    raise SystemExit('Este escenario requiere una base vacía.')

output = Path(os.environ['CUTLESS_TEST_FIXTURE'])
with output.open('x', encoding='utf-8') as fixture:
    owner = User.objects.create_user('control_contacto')
    owner.perfil.puede_crear_clientes = True
    owner.perfil.notificaciones_email = False
    owner.perfil.preferencias_menu = {'_inicio_completado': True}
    owner.perfil.tutorial_completado = True
    owner.perfil.save()
    customer = Cliente.objects.create(usuario=owner, nombre='Cliente histórico de prueba',
                                      telefono='Contacto antiguo', rut='FISCAL-ANTERIOR')
    client = Client()
    client.force_login(owner)
    json.dump({
        'session': client.cookies['sessionid'].value,
        'create': reverse('cutless:crear_cliente'),
        'edit': reverse('cutless:editar_cliente', args=[customer.pk]),
        'list': reverse('cutless:lista_clientes'),
    }, fixture)
