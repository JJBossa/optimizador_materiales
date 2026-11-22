from base64 import b64decode
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from cutless.models import Optimizacion
from cutless.views import analytics


class EstadisticasHdTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user('estadisticas-hd')
        cls.otro = User.objects.create_user('estadisticas-hd-otro')
        campos = {'ancho_tablero': 122, 'alto_tablero': 244, 'piezas': 'Puerta,40,50,1'}
        cls.reciente = Optimizacion.objects.create(usuario=cls.usuario, aprovechamiento_total=82, **campos)
        antiguo = Optimizacion.objects.create(usuario=cls.usuario, aprovechamiento_total=60, **campos)
        Optimizacion.objects.filter(pk=antiguo.pk).update(fecha=timezone.now() - timedelta(days=15))
        Optimizacion.objects.create(usuario=cls.otro, aprovechamiento_total=99, **campos)

    def setUp(self):
        self.client.force_login(self.usuario)
        self.url = reverse('cutless:grafico_estadisticas_hd')

    def test_pagina_inicial_solo_genera_miniaturas_y_conserva_resumen(self):
        with (
            patch.object(analytics, 'generar_grafico_aprovechamiento', return_value='YWJj') as aprovechar,
            patch.object(analytics, 'generar_grafico_desperdicio', return_value='ZGVm') as desperdiciar,
        ):
            respuesta = self.client.get(reverse('cutless:estadisticas'), {'periodo': 'semanal'})
        for generar in (aprovechar, desperdiciar):
            generar.assert_called_once()
            consulta, periodo = generar.call_args.args
            self.assertEqual(list(consulta), [self.reciente])
            self.assertEqual(periodo, 'semanal')
            self.assertEqual(generar.call_args.kwargs, {'alta_resolucion': False})
        self.assertContains(respuesta, 'data:image/png;base64,', count=2)
        self.assertContains(respuesta, f'data-grafico-url="{self.url}" data-periodo="semanal"')
        self.assertEqual(respuesta.context['total_optimizaciones'], 1)
        self.assertEqual(respuesta.context['promedio_aprovechamiento'], 82)
        self.assertEqual(respuesta.context['promedio_desperdicio'], 18)
        self.assertEqual(respuesta.context['top_optimizaciones'][0]['optimizacion'], self.reciente)

    def test_endpoint_genera_solo_el_tipo_solicitado_y_respeta_permisos_y_periodo(self):
        with (
            patch.object(analytics, 'generar_grafico_aprovechamiento', return_value='YWJj') as aprovechar,
            patch.object(analytics, 'generar_grafico_desperdicio', return_value='ZGVm') as desperdiciar,
        ):
            respuesta = self.client.get(self.url, {
                'tipo': 'aprovechamiento', 'periodo': 'semanal', 'usuario': self.otro.pk,
            })
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta['Content-Type'], 'image/png')
        self.assertEqual(respuesta.content, b'abc')
        self.assertIn('private', respuesta['Cache-Control'])
        self.assertIn('no-store', respuesta['Cache-Control'])
        desperdiciar.assert_not_called()
        aprovechar.assert_called_once()
        consulta, periodo = aprovechar.call_args.args
        self.assertEqual(list(consulta), [self.reciente])
        self.assertEqual(periodo, 'semanal')
        self.assertEqual(aprovechar.call_args.kwargs, {'alta_resolucion': True})

    def test_png_equivale_al_hd_del_renderizador_original(self):
        for tipo, generar in (
            ('aprovechamiento', analytics.generar_grafico_aprovechamiento),
            ('desperdicio', analytics.generar_grafico_desperdicio),
        ):
            with self.subTest(tipo=tipo):
                planes = Optimizacion.objects.filter(usuario=self.usuario).order_by('fecha')
                esperado = b64decode(generar(planes, 'mensual', alta_resolucion=True))
                respuesta = self.client.get(self.url, {'tipo': tipo, 'periodo': 'mensual'})
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(respuesta.content, esperado)
                with Image.open(BytesIO(respuesta.content)) as png:
                    self.assertEqual(png.format, 'PNG')
                    self.assertGreater(png.width, 2000)

    def test_autenticacion_y_permiso_se_verifican_antes_de_generar(self):
        params = {'tipo': 'aprovechamiento', 'periodo': 'todos'}
        with patch.object(analytics, 'generar_grafico_aprovechamiento') as generar:
            self.client.logout()
            self.assertEqual(self.client.get(self.url, params).status_code, 302)
            perfil = self.otro.perfil
            perfil.puede_ver_estadisticas = False
            perfil.save(update_fields=['puede_ver_estadisticas'])
            self.client.force_login(self.otro)
            self.assertRedirects(self.client.get(self.url, params), reverse('cutless:index'),
                                 fetch_redirect_response=False)
            generar.assert_not_called()

    def test_parametros_invalidos_y_post_no_generan_graficos(self):
        with patch.object(analytics, 'generar_grafico_aprovechamiento') as generar:
            for parametros in (
                {}, {'tipo': 'importe', 'periodo': 'todos'}, {'tipo': 'aprovechamiento', 'periodo': 'diario'},
            ):
                self.assertEqual(self.client.get(self.url, parametros).status_code, 400)
            self.assertEqual(self.client.post(self.url, {'tipo': 'aprovechamiento', 'periodo': 'todos'}).status_code, 405)
            generar.assert_not_called()

    def test_sin_datos_y_error_del_renderizador_son_respuestas_recuperables(self):
        params = {'tipo': 'desperdicio', 'periodo': 'todos'}
        with patch.object(analytics, 'generar_grafico_desperdicio', return_value=None):
            self.assertEqual(self.client.get(self.url, params).status_code, 404)
        with (
            patch.object(analytics, 'generar_grafico_desperdicio', side_effect=RuntimeError('detalle privado')),
            self.assertLogs(analytics.logger, level='ERROR'),
        ):
            respuesta = self.client.get(self.url, params)
        self.assertContains(respuesta, 'No se pudo generar el gráfico.', status_code=503)
        self.assertNotContains(respuesta, 'detalle privado', status_code=503)
