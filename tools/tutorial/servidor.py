"""Servidor loopback con datos sintéticos para las pruebas Chromium del tutorial."""
import argparse
import os
import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from secrets import token_urlsafe
from tempfile import TemporaryDirectory


def sembrar(contrasena):
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    from cutless.models import Cliente, Material, Optimizacion, Plantilla, Presupuesto, Proyecto

    for nombre in ('auditoria', 'bienvenida'):
        usuario = get_user_model().objects.create_user(nombre, password=contrasena)
        perfil = usuario.perfil
        perfil.rol = 'admin'
        perfil.tema_preferido = 'auto'
        perfil.tutorial_completado = nombre == 'auditoria'
        perfil.preferencias_menu = {'_inicio_completado': True}
        perfil.save()
        if nombre == 'auditoria':
            admin = usuario

    material = Material.objects.create(usuario=admin, nombre='MDF de prueba', ancho=120, alto=240,
                                       precio=Decimal('9000'))
    cliente = Cliente.objects.create(usuario=admin, nombre='Cliente de prueba')
    proyecto = Proyecto.objects.create(usuario=admin, nombre='Proyecto de prueba', cliente=cliente)
    piezas = 'Panel,48,90,4\nRefuerzo,20,35,4'
    Plantilla.objects.create(usuario=admin, nombre='Plantilla de prueba',
                             ancho_tablero=120, alto_tablero=240, piezas=piezas)
    optimizaciones = [
        Optimizacion.objects.create(
            usuario=admin, nombre=f'Corte de prueba {i}', ancho_tablero=120, alto_tablero=240,
            piezas=piezas, num_tableros=i, aprovechamiento_total=56.0,
            material=material, precio_tablero=material.precio, mano_obra=Decimal('1200'),
            favorito=i == 1, cliente=cliente, proyecto=proyecto if i == 1 else None,
        )
        for i in (1, 2, 3)
    ]
    presupuesto = Presupuesto.objects.create(
        usuario=admin, cliente=cliente, proyecto=proyecto, numero='PRE-PRUEBA-01',
        estado='borrador', precio_tablero=Decimal('9000'), mano_obra=Decimal('1200'),
        costo_total=Decimal('10200'), fecha_validez=timezone.localdate() + timedelta(days=30),
    )
    presupuesto.optimizaciones.add(optimizaciones[0])
    emitido = Presupuesto.objects.create(
        usuario=admin, numero='PRE-PRUEBA-02', estado='enviado',
        precio_tablero=Decimal('9000'), mano_obra=Decimal('1200'),
        costo_total=Decimal('10200'), fecha_validez=presupuesto.fecha_validez,
    )
    emitido.optimizaciones.add(optimizaciones[0])
    emitido.cerrar_detalle()
    emitido.save(update_fields=['detalle_emitido'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--puerto', type=int, default=8775)
    args = parser.parse_args()
    contrasena = os.environ.get('TUTORIAL_TEST_PASSWORD')
    if not contrasena:
        parser.error('Define TUTORIAL_TEST_PASSWORD para las cuentas temporales de prueba.')
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'cut'))
    with TemporaryDirectory(prefix='cutless-tutorial-') as directorio:
        base = Path(directorio)
        os.environ.update(
            DJANGO_SETTINGS_MODULE='cutless_project.settings',
            CUTLESS_ENV='development',
            CUTLESS_DB_ENGINE='sqlite',
            CUTLESS_DB_PATH=str(base / 'tutorial.sqlite3'),
            CUTLESS_SECRET_KEY=token_urlsafe(48),
            CUTLESS_ALLOWED_HOSTS='127.0.0.1,localhost',
            CUTLESS_TRUST_PROXY_HEADERS='false',
            MPLCONFIGDIR=str(base / 'matplotlib'),
            XDG_CACHE_HOME=str(base / 'cache'),
        )
        import django
        from django.conf import settings
        from django.core.management import call_command

        if (settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3' or
                settings.DATABASES['default']['NAME'] != base / 'tutorial.sqlite3'):
            raise RuntimeError('Se requiere la base SQLite temporal de pruebas.')
        settings.MEDIA_ROOT = base / 'media'
        settings.STATIC_ROOT = base / 'static'
        settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
        settings.EMAIL_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'
        settings.BREVO_RECOVERY_ENABLED = False
        settings.RECOVERY_QUEUE_CONSUMER_ENABLED = False
        django.setup()
        call_command('migrate', interactive=False, verbosity=0)
        sembrar(contrasena)
        # Los contextos de navegador pueden actualizar sesiones a la vez en SQLite.
        call_command('runserver', f'127.0.0.1:{args.puerto}', use_reloader=False, use_threading=False)


if __name__ == '__main__':
    main()
