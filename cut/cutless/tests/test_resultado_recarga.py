"""La página final debe ser un GET seguro para recargar, sin repetir el POST."""
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from cutless.models import Optimizacion

class ResultadoRecargaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('resultado_recarga')
        self.user.perfil.rol = 'usuario'
        self.user.perfil.preferencias_menu = {'_inicio_completado': True}
        self.user.perfil.save()
        self.client.force_login(self.user)
        self.data = {'unidad_medida':'cm', 'ancho':122, 'alto':244, 'margen_corte':3,
            'permitir_rotacion':'on', 'form-TOTAL_FORMS':1, 'form-INITIAL_FORMS':0,
            'form-0-nombre':'Puerta', 'form-0-ancho':40, 'form-0-alto':50, 'form-0-cantidad':2}

    def test_create_redirects_and_refreshes_never_create_or_recalculate(self):
        response = self.client.post(reverse('cutless:index'), self.data)
        opt = Optimizacion.objects.get(usuario=self.user)
        url = reverse('cutless:resultado', args=[opt.pk])
        self.assertRedirects(response, url, fetch_redirect_response=False)
        before = Optimizacion.objects.values().get(pk=opt.pk)
        with patch('cutless.services.optimization._regenerar_grafico', side_effect=AssertionError('No recalcular')):
            with patch('cutless.exports.board_png.generar_png_tablero', side_effect=AssertionError('El SVG no necesita PNG')):
                for _ in range(3):
                    result = self.client.get(url, HTTP_CACHE_CONTROL='no-cache', HTTP_PRAGMA='no-cache')
                    self.assertEqual(result.status_code, 200)
                    self.assertTemplateUsed(result, 'cutless/resultado.html')
        self.assertEqual(Optimizacion.objects.filter(usuario=self.user).count(), 1)
        self.assertEqual(Optimizacion.objects.values().get(pk=opt.pk), before)

    def test_edit_redirects_to_same_record_and_invalid_submission_stays_on_form(self):
        self.client.post(reverse('cutless:index'), self.data)
        opt = Optimizacion.objects.get(usuario=self.user)
        url = reverse('cutless:editar_optimizacion', args=[opt.pk])
        response = self.client.post(url, {**self.data, 'form-0-cantidad':3})
        self.assertRedirects(response, reverse('cutless:resultado', args=[opt.pk]), fetch_redirect_response=False)
        self.assertEqual(Optimizacion.objects.filter(usuario=self.user).count(), 1)
        opt.refresh_from_db()
        self.assertIn(',3', opt.piezas)
        invalid = self.client.post(url, {**self.data, 'ancho':99999})
        self.assertEqual(invalid.status_code, 200)
        self.assertTemplateUsed(invalid, 'cutless/editar_optimizacion.html')
        self.assertEqual(Optimizacion.objects.filter(usuario=self.user).count(), 1)

    def test_another_user_cannot_read_result(self):
        self.client.post(reverse('cutless:index'), self.data)
        opt = Optimizacion.objects.get(usuario=self.user)
        other = User.objects.create_user('otro_resultado')
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('cutless:resultado', args=[opt.pk])).status_code, 404)

    def test_piezas_con_comas_y_unicode_se_conservan_al_editar_duplicar_y_exportar(self):
        from io import BytesIO
        from openpyxl import load_workbook
        from cutless.pieces import parsear_piezas_desde_texto

        nombre = 'Frente, sección ñ'
        self.client.post(reverse('cutless:index'), {**self.data, 'form-0-nombre': nombre})
        opt = Optimizacion.objects.get(usuario=self.user)
        for ruta in ('editar_optimizacion', 'duplicar_optimizacion'):
            respuesta = self.client.get(reverse('cutless:' + ruta, args=[opt.pk]))
            self.assertEqual(respuesta.context['pieza_formset'].initial[0]['nombre'], nombre)
        url = reverse('cutless:editar_optimizacion', args=[opt.pk])
        self.client.post(url, {**self.data, 'form-0-nombre': nombre, 'form-0-cantidad': 3})
        opt.refresh_from_db()
        self.assertEqual(parsear_piezas_desde_texto(opt.piezas)[0]['cantidad'], 3)
        xlsx = self.client.get(reverse('cutless:descargar_excel', args=[opt.pk]))
        cuerpo = b''.join(xlsx.streaming_content) if xlsx.streaming else xlsx.content
        libro = load_workbook(BytesIO(cuerpo))
        self.assertEqual(libro['Piezas']['A2'].value, nombre)

    def test_edicion_valida_propietarios_y_respeta_permiso_de_costos(self):
        from cutless.models import Cliente, Material, Proyecto

        otra = User.objects.create_user('otra_cuenta')
        predefinido = Material.objects.create(nombre='Común', ancho=122, alto=244, precio=250, es_predefinido=True)
        ajeno = Material.objects.create(nombre='Privado', ancho=122, alto=244, usuario=otra)
        cliente = Cliente.objects.create(nombre='Cuenta', usuario=self.user)
        cliente_ajeno = Cliente.objects.create(nombre='Otra cuenta', usuario=otra)
        proyecto = Proyecto.objects.create(nombre='Propio', usuario=self.user)
        proyecto_ajeno = Proyecto.objects.create(nombre='Ajeno', usuario=otra)
        self.client.post(reverse('cutless:index'), self.data)
        opt = Optimizacion.objects.get(usuario=self.user)
        url = reverse('cutless:editar_optimizacion', args=[opt.pk])
        respuesta = self.client.post(url, {
            **self.data, 'material': ajeno.pk, 'cliente': cliente_ajeno.pk, 'proyecto': proyecto_ajeno.pk,
        })
        self.assertEqual(set(respuesta.context['tablero_form'].errors), {'material', 'cliente', 'proyecto'})
        respuesta = self.client.post(url, {
            **self.data, 'material': predefinido.pk, 'cliente': cliente.pk, 'proyecto': proyecto.pk,
        })
        self.assertEqual(respuesta.status_code, 302)
        opt.refresh_from_db()
        self.assertEqual((opt.material, opt.cliente, opt.proyecto, opt.precio_tablero), (predefinido, cliente, proyecto, 250))

        self.user.perfil.puede_ver_historial_costos = False
        self.user.perfil.save(update_fields=['puede_ver_historial_costos'])
        self.assertNotIn('precio_tablero', self.client.get(url).context['tablero_form'].fields)
        self.assertEqual(self.client.post(url, {**self.data, 'precio_tablero': 1, 'material': ajeno.pk}).status_code, 302)
        opt.refresh_from_db()
        self.assertEqual((opt.material, opt.cliente, opt.proyecto, opt.precio_tablero), (predefinido, cliente, proyecto, 250))

    def test_alta_edicion_y_pdf_vectorial_omiten_png_innecesarios(self):
        with patch('cutless.render.plt.figure', side_effect=AssertionError('No crear PNG transitorio')):
            self.assertEqual(self.client.post(reverse('cutless:index'), self.data).status_code, 302)
            opt = Optimizacion.objects.get(usuario=self.user)
            url = reverse('cutless:editar_optimizacion', args=[opt.pk])
            self.assertEqual(self.client.post(url, self.data).status_code, 302)
        opt.refresh_from_db()
        self.assertTrue(opt.resultado_extra['vistas_web'])

        with patch('cutless.exports.board_png.generar_png_tablero') as generar_png:
            pdf = self.client.get(reverse('cutless:descargar_pdf', args=[opt.pk]))
            self.assertTrue(b''.join(pdf.streaming_content).startswith(b'%PDF'))
            generar_png.assert_not_called()

    def test_formset_limita_datos_antes_de_calcular(self):
        datos = {**self.data, 'form-TOTAL_FORMS': 1000000}
        with patch('cutless.views.optimization.generar_grafico') as calcular:
            respuesta = self.client.post(reverse('cutless:index'), datos)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context['pieza_formset'].forms), 20)
        self.assertTrue(respuesta.context['pieza_formset'].non_form_errors())
        calcular.assert_not_called()

    def test_piezas_historicas_y_json_con_prefijos_se_conservan_en_flujos_y_exportaciones(self):
        from io import BytesIO
        from openpyxl import load_workbook
        from reportlab import rl_config
        from cutless.pieces import parsear_piezas_desde_texto

        variantes = (
            ('piezas:v1:Puerta, norte', 'Cajón sur'),
            ('piezas:v1:Puerta, norte\nNivel superior', 'piezas:v2:Cajón sur'),
        )
        existente = Optimizacion.objects.create(
            usuario=self.user, ancho_tablero=122, alto_tablero=244,
            piezas=f'{variantes[0][0]},40,50,2\n{variantes[0][1]},20,30,3',
        )
        campos = ('nombre', 'ancho', 'alto', 'cantidad')
        for nombres, opt in ((variantes[0], existente), (variantes[1], None)):
            with self.subTest(nombres=nombres):
                esperado = [
                    dict(nombre=nombres[0], ancho=40, alto=50, cantidad=2),
                    dict(nombre=nombres[1], ancho=20, alto=30, cantidad=3),
                ]
                if opt is not None:
                    for ruta in ('editar_optimizacion', 'duplicar_optimizacion'):
                        respuesta = self.client.get(reverse('cutless:' + ruta, args=[opt.pk]))
                        self.assertEqual([p['nombre'] for p in respuesta.context['pieza_formset'].initial], list(nombres))
                    self.assertEqual(self.client.get(reverse('cutless:descargar_excel', args=[opt.pk])).status_code, 200)
                datos = {**self.data, 'form-TOTAL_FORMS': 2}
                for i, pieza in enumerate(esperado):
                    datos.update({f'form-{i}-{campo}': pieza[campo] for campo in campos})
                if opt is None:
                    self.assertEqual(self.client.post(reverse('cutless:index'), datos).status_code, 302)
                    opt = Optimizacion.objects.latest('pk')
                editar = reverse('cutless:editar_optimizacion', args=[opt.pk])
                self.assertEqual(self.client.post(editar, datos).status_code, 302)
                opt.refresh_from_db()
                leidas = parsear_piezas_desde_texto(opt.piezas, estricto=True)
                self.assertEqual([{campo: pieza[campo] for campo in campos} for pieza in leidas], esperado)

                duplicado = self.client.get(reverse('cutless:duplicar_optimizacion', args=[opt.pk]))
                iniciales = duplicado.context['pieza_formset'].initial
                self.assertEqual([{campo: pieza[campo] for campo in campos} for pieza in iniciales], esperado)
                self.assertContains(duplicado, '<textarea', count=2)
                excel = self.client.get(reverse('cutless:descargar_excel', args=[opt.pk]))
                hoja = load_workbook(BytesIO(excel.content))['Piezas']
                self.assertEqual([hoja.cell(i, 1).value for i in (2, 3)], list(nombres))
                with patch.object(rl_config, 'pageCompression', 0):
                    pdf = self.client.get(reverse('cutless:descargar_pdf', args=[opt.pk]))
                    contenido = b''.join(pdf.streaming_content)
                self.assertIn(b'piezas:v1:Puerta, norte', contenido)
                self.assertIn(rb'Caj\363n sur', contenido)
                if '\n' in nombres[0]:
                    self.assertIn(b'Nivel superior', contenido)

    def test_ambiguedad_se_muestra_y_bloquea_edicion_duplicacion_y_exportacion(self):
        original = 'piezas:v1:Puerta,40,50,2\ntexto sin dimensiones\n20,30,3'
        opt = Optimizacion.objects.create(
            usuario=self.user, ancho_tablero=122, alto_tablero=244, piezas=original,
        )
        for ruta in ('editar_optimizacion', 'duplicar_optimizacion', 'descargar_excel', 'descargar_pdf'):
            with self.subTest(ruta=ruta):
                url = reverse('cutless:' + ruta, args=[opt.pk])
                self.assertContains(self.client.get(url), 'Se conservó el registro original', status_code=422)
        editar = reverse('cutless:editar_optimizacion', args=[opt.pk])
        self.assertEqual(self.client.post(editar, self.data).status_code, 422)
        opt.refresh_from_db()
        self.assertEqual(opt.piezas, original)
        self.assertFalse(opt.resultado_generado)
