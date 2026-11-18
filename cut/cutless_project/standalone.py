"""Configuración local para herramientas que crean datos desechables."""
from contextlib import contextmanager
import os
from pathlib import Path
import secrets
from unittest.mock import patch


@contextmanager
def django_aislado(directorio, base_de_datos):
    from django.conf import settings

    if settings.configured:
        raise RuntimeError('Ejecuta la herramienta en un proceso nuevo.')
    directorio = Path(directorio)
    entorno = {
        'DJANGO_SETTINGS_MODULE': 'cutless_project.settings',
        'CUTLESS_ENV': 'development',
        'CUTLESS_DB_ENGINE': 'sqlite',
        'CUTLESS_DB_PATH': str(base_de_datos),
        'CUTLESS_SECRET_KEY': secrets.token_urlsafe(64),
        'MPLCONFIGDIR': str(directorio / 'matplotlib'),
        'XDG_CACHE_HOME': str(directorio / 'cache'),
        'PATH': os.environ.get('PATH', os.defpath),
    }
    with patch.dict(os.environ, entorno, clear=True):
        import django

        esperado = {'default'}
        if (settings.CUTLESS_ENV != 'development' or set(settings.DATABASES) != esperado
                or settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3'
                or str(settings.DATABASES['default']['NAME']) != str(base_de_datos)):
            raise RuntimeError('No se pudo aislar la base SQLite de la herramienta.')
        settings.MEDIA_ROOT = directorio / 'media'
        settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
        settings.ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']
        django.setup()
        yield
