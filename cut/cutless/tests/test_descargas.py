from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.http import FileResponse, HttpResponse
from django.test import Client, TestCase
from django.urls import reverse

from cutless.models import Optimizacion


class DescargasObservablesTests(TestCase):
    token = '352554041d7b42f1af6455940d177589'
    cookie = 'cutless_descarga_' + token

    def setUp(self):
        self.usuario = User.objects.create_user('descargas')
        self.plan = Optimizacion.objects.create(usuario=self.usuario, ancho_tablero=122, alto_tablero=244,
                                                piezas='Puerta,40,50,2')
        self.pdf = reverse('cutless:descargar_pdf', args=[self.plan.pk])
        self.client.force_login(self.usuario)

    def solicitar(self, ruta, **kwargs):
        return self.client.get(ruta, {'_cutless_download': self.token}, **kwargs)

    def test_observar_no_cambia_nombre_cuerpo_ni_streaming(self):
        def archivo(*args, **kwargs):
            return FileResponse(BytesIO(b'%PDF-1.4\n'), as_attachment=True, filename='plano ñ.pdf')

        with patch('cutless.views.exports.respuesta_pdf_optimizacion', side_effect=archivo):
            normal = self.client.get(self.pdf)
            observada = self.solicitar(self.pdf, secure=True)
            self.assertNotIn(self.cookie, normal.cookies)
            self.assertEqual(observada.cookies[self.cookie].value, 'preparado')
            self.assertTrue(observada.cookies[self.cookie]['secure'])
            self.assertIn('no-store', observada['Cache-Control'])
            self.assertEqual(normal['Content-Disposition'], observada['Content-Disposition'])
            self.assertEqual(normal['Content-Type'], observada['Content-Type'])
            self.assertTrue(observada.streaming)
            self.assertEqual(b''.join(normal.streaming_content), b''.join(observada.streaming_content))

    def test_indica_sesion_permiso_y_propiedad_sin_cambiar_respuestas(self):
        costos = reverse('cutless:historial_costos') + '?export=excel&_cutless_download=' + self.token
        self.usuario.perfil.puede_ver_historial_costos = False
        self.usuario.perfil.save(update_fields=['puede_ver_historial_costos'])
        respuesta = self.client.get(costos)
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.cookies[self.cookie].value, '403')
        ajeno = User.objects.create_user('otra-cuenta')
        self.client.force_login(ajeno)
        respuesta = self.solicitar(self.pdf)
        self.assertEqual(respuesta.status_code, 404)
        self.assertEqual(respuesta.cookies[self.cookie].value, '404')
        self.client.logout()
        respuesta = self.solicitar(self.pdf)
        self.assertIn(reverse('usuarios:login'), respuesta['Location'])
        self.assertEqual(respuesta.cookies[self.cookie].value, '401')

    def test_rechaza_html_y_senaliza_fallo_de_servidor(self):
        with patch('cutless.views.exports.respuesta_pdf_optimizacion', return_value=HttpResponse('HTML')):
            respuesta = self.solicitar(self.pdf)
            self.assertEqual(respuesta.cookies[self.cookie].value, 'inesperado')
        self.client = Client(raise_request_exception=False)
        self.client.force_login(self.usuario)
        with patch('cutless.views.exports.respuesta_pdf_optimizacion', side_effect=RuntimeError('fallo simulado')):
            respuesta = self.solicitar(self.pdf)
            self.assertEqual(respuesta.status_code, 500)
            self.assertEqual(respuesta.cookies[self.cookie].value, '500')

    def test_no_marca_paginas_ni_tokens_invalidos(self):
        for vista in ('cutless:historial', 'cutless:historial_costos'):
            respuesta = self.solicitar(reverse(vista))
            self.assertNotIn(self.cookie, respuesta.cookies)
        with patch('cutless.views.exports.respuesta_pdf_optimizacion', return_value=HttpResponse()):
            respuesta = self.client.get(self.pdf, {'_cutless_download': 'inválido'})
            self.assertFalse(any(nombre.startswith('cutless_descarga_') for nombre in respuesta.cookies))
