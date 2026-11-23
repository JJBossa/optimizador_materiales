import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from cutless.models import Optimizacion, Presupuesto
from cutless.services import indicadores


HOY = date(2026, 1, 10)
RESPUESTA = {
    'autor': 'findic.cl',
    'fecha': '2026-01-10',
    'dolar': {'codigo': 'dolar', 'unidad_medida': 'Pesos', 'fecha': '2026-01-09', 'valor': 800.75},
    'uf': {'codigo': 'uf', 'unidad_medida': 'Pesos', 'fecha': '2026-01-10', 'valor': 40000.25},
    'euro': {'fecha': '2026-01-10', 'valor': 900},
}


class IndicadoresServicioTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        fecha = patch.object(indicadores.timezone, 'localdate', return_value=HOY)
        self.hoy = fecha.start()
        self.addCleanup(fecha.stop)
        conexion = patch.object(indicadores, 'HTTPSConnection', autospec=True)
        self.https = conexion.start()
        self.addCleanup(conexion.stop)
        self.conexion = self.https.return_value
        self.respuesta = self.conexion.getresponse.return_value
        self.respuesta.status = 200
        self.respuesta.read.return_value = json.dumps(RESPUESTA).encode()

    def test_get_fijo_y_fechas_independientes_en_hora_de_chile(self):
        resultado = indicadores.obtener_indicadores()
        self.assertEqual(resultado, {'desde_cache': False, 'indicadores': {
            'dolar': {'valor': 800.75, 'fecha': date(2026, 1, 9), 'fecha_anterior': True},
            'uf': {'valor': 40000.25, 'fecha': HOY, 'fecha_anterior': False},
        }})
        self.https.assert_called_once_with('findic.cl', timeout=2)
        self.conexion.request.assert_called_once_with('GET', '/api/', headers={'Accept': 'application/json'})
        self.conexion.close.assert_called_once()

    def test_descarta_valores_invalidos_y_conserva_el_otro_indicador(self):
        for valor in (True, '800', None, 0, -1, float('inf'), float('nan'), 10**400):
            with self.subTest(valor=valor):
                datos = {**RESPUESTA, 'dolar': {**RESPUESTA['dolar'], 'valor': valor}}
                self.respuesta.read.return_value = json.dumps(datos).encode()
                cache.clear()
                self.assertEqual(set(indicadores.obtener_indicadores()['indicadores']), {'uf'})

    def test_descarta_fechas_invalidas_futuras_o_fuera_de_formato(self):
        for fecha in (None, 'texto', '2025-02-30', '20260110', '2026-01-10T03:00:00Z', '2026-01-11'):
            with self.subTest(fecha=fecha):
                datos = {'dolar': {'valor': 800, 'fecha': fecha}}
                self.respuesta.read.return_value = json.dumps(datos).encode()
                cache.clear()
                self.assertEqual(indicadores.obtener_indicadores()['indicadores'], {})

    def test_sin_indicadores_json_invalido_y_respuesta_excesiva(self):
        for cuerpo in (b'{}', b'[]', b'<html>', b'{' * (indicadores.MAX_RESPUESTA + 1)):
            with self.subTest(tamano=len(cuerpo)):
                self.respuesta.read.return_value = cuerpo
                cache.clear()
                self.assertEqual(indicadores.obtener_indicadores()['indicadores'], {})

    def test_timeout_y_error_http_aplican_espera_entre_intentos(self):
        self.conexion.request.side_effect = TimeoutError
        self.assertEqual(indicadores.obtener_indicadores()['indicadores'], {})
        self.assertEqual(indicadores.obtener_indicadores()['indicadores'], {})
        self.https.assert_called_once()
        cache.delete(indicadores.CACHE_INTENTO)
        self.conexion.request.side_effect = None
        self.respuesta.status = 302
        self.assertEqual(indicadores.obtener_indicadores()['indicadores'], {})
        cache.delete(indicadores.CACHE_INTENTO)
        self.respuesta.status = 503
        self.assertEqual(indicadores.obtener_indicadores()['indicadores'], {})
        self.assertEqual(self.https.call_count, 3)
        self.respuesta.read.assert_not_called()

    def test_cache_y_respaldo_recalculan_antiguedad(self):
        self.assertFalse(indicadores.obtener_indicadores()['desde_cache'])
        self.hoy.return_value = date(2026, 1, 11)
        resultado = indicadores.obtener_indicadores()
        self.assertTrue(resultado['desde_cache'])
        self.assertTrue(resultado['indicadores']['uf']['fecha_anterior'])
        self.https.assert_called_once()

        cache.delete_many((indicadores.CACHE_ACTUAL, indicadores.CACHE_INTENTO))
        self.respuesta.status = 503
        self.assertEqual(indicadores.obtener_indicadores(), resultado)
        self.assertEqual(indicadores.obtener_indicadores(), resultado)
        self.assertEqual(self.https.call_count, 2)
        cache.delete(indicadores.CACHE_RESPALDO)
        self.assertEqual(indicadores.obtener_indicadores(), {'desde_cache': False, 'indicadores': {}})


class IndicadoresPresupuestosTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        conexion = patch.object(indicadores, 'HTTPSConnection', autospec=True)
        self.https = conexion.start()
        self.addCleanup(conexion.stop)
        self.https.return_value.request.side_effect = TimeoutError
        self.usuario = User.objects.create_user('indicadores')
        self.client.force_login(self.usuario)
        self.api = reverse('cutless:indicadores_presupuestos')

    def test_caida_externa_no_impide_crear_listar_ni_consultar_el_total(self):
        self.assertEqual(self.client.get(self.api).json(), {'desde_cache': False, 'indicadores': {}})
        plan = Optimizacion.objects.create(
            usuario=self.usuario, ancho_tablero=122, alto_tablero=244,
            piezas='Puerta,40,50,1', num_tableros=2,
        )
        respuesta = self.client.post(reverse('cutless:crear_presupuesto'), {
            'optimizaciones': [plan.pk], 'precio_tablero': '1000.00', 'mano_obra': '400.00',
            'fecha_validez': (timezone.localdate() + timedelta(days=1)).isoformat(), 'estado': 'borrador',
        })
        self.assertEqual(respuesta.status_code, 302)
        presupuesto = Presupuesto.objects.get(usuario=self.usuario)
        listado = self.client.get(reverse('cutless:lista_presupuestos'))
        self.assertContains(listado, presupuesto.numero)
        self.assertContains(listado, 'Indicadores económicos')
        self.assertContains(listado, 'href="https://findic.cl/">Fuente: Findic.cl</a>')
        detalle = self.client.get(reverse('cutless:detalle_presupuesto', args=[presupuesto.pk]))
        self.assertContains(detalle, 'data-total-clp="2400.00"')
        self.assertEqual(detalle.context['total_presupuesto'], Decimal('2400.00'))
        presupuesto.refresh_from_db()
        self.assertEqual(presupuesto.costo_total, Decimal('2400.00'))
        self.https.assert_called_once()

    def test_endpoint_comparte_cache_entre_usuarios_y_exige_permiso(self):
        self.https.return_value.request.side_effect = None
        respuesta = self.https.return_value.getresponse.return_value
        respuesta.status = 200
        respuesta.read.return_value = json.dumps(RESPUESTA).encode()
        original = self.client.get(self.api).json()
        self.assertFalse(original['desde_cache'])
        self.assertEqual(
            {codigo: dato['valor'] for codigo, dato in original['indicadores'].items()},
            {'dolar': 800.75, 'uf': 40000.25},
        )
        otro = User.objects.create_user('otro-indicadores')
        self.client.force_login(otro)
        self.assertEqual(self.client.get(self.api).json(), {**original, 'desde_cache': True})
        otro.perfil.puede_crear_presupuestos = False
        otro.perfil.save(update_fields=['puede_crear_presupuestos'])
        self.assertEqual(self.client.get(self.api).status_code, 302)
        self.client.logout()
        self.assertEqual(self.client.get(self.api).status_code, 302)
        self.https.assert_called_once()
