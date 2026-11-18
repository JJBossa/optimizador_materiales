import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase

from smoke_test_templates import comprobar_respuestas


class SmokeAisladoTests(SimpleTestCase):
    def test_cualquier_http_inesperado_produce_fallo(self):
        cliente = Mock()
        cliente.get.side_effect = [SimpleNamespace(status_code=200), SimpleNamespace(status_code=500)]
        with self.assertRaisesRegex(RuntimeError, '500 /fallo/'):
            comprobar_respuestas(cliente, ['/bien/', '/fallo/'])

    def test_ignora_base_persistente_del_entorno(self):
        script = Path(__file__).resolve().parents[2] / 'smoke_test_templates.py'
        with TemporaryDirectory() as tmp:
            ruta = Path(tmp) / 'ajena.sqlite3'
            ruta.write_bytes(b'archivo centinela')
            entorno = {
                **os.environ, 'CUTLESS_ENV': 'production', 'CUTLESS_DB_ENGINE': 'sqlite',
                'CUTLESS_DB_PATH': str(ruta), 'DJANGO_SETTINGS_MODULE': 'configuracion.ajena',
                'CUTLESS_MEDIA_ROOT': tmp,
            }
            resultado = subprocess.run(
                [sys.executable, '-B', str(script)], env=entorno, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(resultado.returncode, 0, resultado.stderr)
            self.assertIn('HTTP 200', resultado.stdout)
            self.assertEqual(list(Path(tmp).iterdir()), [ruta])
            self.assertEqual(ruta.read_bytes(), b'archivo centinela')
