from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from cutless.models import Optimizacion


class TiempoDeCorteTests(TestCase):
    def setUp(self):
        usuario = User.objects.create_user('calculadora')
        self.client.force_login(usuario)
        self.opt = Optimizacion.objects.create(usuario=usuario, ancho_tablero=100, alto_tablero=100,
                                              piezas='Pieza,100,100,1', num_tableros=4)
        self.url = reverse('cutless:calcular_tiempo_corte', args=[self.opt.pk])

    def test_usa_tableros_del_plan_y_preparacion_por_tablero(self):
        respuesta = self.client.post(self.url, {'velocidad_corte': 10, 'tiempo_setup': 3})
        self.assertEqual(respuesta.context['num_tableros_estimado'], 4)
        self.assertEqual(respuesta.context['tiempo_setup_total'], 12)
        self.assertContains(respuesta, 'Tableros del plan')

    def test_en_legado_division_exacta_no_agrega_tablero_adicional(self):
        self.opt.num_tableros = 0
        self.opt.save(update_fields=['num_tableros'])
        respuesta = self.client.get(self.url)
        self.assertEqual(respuesta.context['num_tableros_estimado'], 1)
        self.assertContains(respuesta, 'Tableros estimados')

    def test_rechaza_parametros_invalidos_y_desbordamiento(self):
        for campo, valor in (('velocidad_corte', '0'), ('velocidad_corte', '1e-320'),
                             ('velocidad_corte', '1e308'), ('tiempo_setup', '-1'),
                             ('tiempo_setup', '1e308'), ('tiempo_cambio_herramienta', 'nan'),
                             ('tiempo_cambio_herramienta', 'inf'), ('tiempo_setup', 'lento')):
            with self.subTest(campo=campo, valor=valor):
                self.assertEqual(self.client.post(self.url, {campo: valor}).status_code, 400)
