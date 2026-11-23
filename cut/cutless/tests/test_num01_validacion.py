from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from cutless.models import Material, Optimizacion, Plantilla, Presupuesto


class ReferenciasNumericasTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_superuser('num01_propietario')
        otro = User.objects.create_user('num01_otro')
        self.plan = self.crear_plan(self.usuario)
        self.ajeno = self.crear_plan(otro)
        self.ajeno.nombre = 'Referencia privada NUM-01'
        self.ajeno.save(update_fields=['nombre'])
        self.client.force_login(self.usuario)
        self.historial = reverse('cutless:historial')
        self.borrar = reverse('cutless:borrar_seleccion')

    @staticmethod
    def crear_plan(usuario):
        return Optimizacion.objects.create(usuario=usuario, ancho_tablero=122, alto_tablero=244,
                                           piezas='Pieza de prueba,20,30,1', num_tableros=1)

    def test_fecha_final_maxima_se_incluye_sin_sumar_un_dia(self):
        respuesta = self.client.get(self.historial, {'fecha_hasta': '9999-12-31'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(list(respuesta.context['page_obj']), [self.plan])

    def test_filtro_por_dia_local_incluye_ultimo_instante_y_excluye_medianoche(self):
        santiago = ZoneInfo('America/Santiago')
        siguiente = self.crear_plan(self.usuario)
        Optimizacion.objects.filter(pk=self.plan.pk).update(fecha=datetime(2026, 11, 22, 23, 59, 59, tzinfo=santiago))
        Optimizacion.objects.filter(pk=siguiente.pk).update(fecha=datetime(2026, 11, 23, tzinfo=santiago))
        with timezone.override(santiago):
            respuesta = self.client.get(self.historial, {'fecha_desde': '2026-11-22', 'fecha_hasta': '2026-11-22'})
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(list(respuesta.context['page_obj']), [self.plan])

    def test_fechas_invalidas_o_invertidas_no_muestran_historial_sin_filtrar(self):
        for filtro in ({'fecha_hasta': '2026-02-30'}, {'fecha_desde': '2026-11-23', 'fecha_hasta': '2026-11-22'}):
            with self.subTest(filtro=filtro):
                respuesta = self.client.get(self.historial, filtro)
                self.assertContains(respuesta, 'Fecha no válida' if len(filtro) == 1 else 'no puede ser posterior',
                                    status_code=400)
                self.assertEqual(list(respuesta.context['page_obj']), [])
                self.assertEqual(respuesta.context['fecha_hasta'], filtro['fecha_hasta'])

    def test_borrado_rechaza_lote_con_formato_invalido_sin_borrar_plan_propio(self):
        for valor in ('abc', '1.5', '', '0', '-1', '1_2', '１２', str(2**63)):
            with self.subTest(valor=valor):
                respuesta = self.client.post(self.borrar, {'seleccion': [self.plan.pk, valor]})
                self.assertContains(respuesta, 'identificadores de optimización inválidos', status_code=400)
                self.assertTrue(Optimizacion.objects.filter(pk=self.plan.pk).exists())
                self.assertTrue(Optimizacion.objects.filter(pk=self.ajeno.pk).exists())

    def test_borrado_no_aplica_parcialmente_si_hay_un_plan_ajeno_o_inexistente(self):
        presupuesto = Presupuesto.objects.create(usuario=self.usuario, numero='PRE-NUM01', precio_tablero=1,
                                                  costo_total=1, fecha_validez='2026-11-23')
        presupuesto.optimizaciones.set([self.plan])
        for referencia in (self.ajeno.pk, 2**63 - 1):
            with self.subTest(referencia=referencia):
                respuesta = self.client.post(self.borrar, {'seleccion': [self.plan.pk, referencia]})
                self.assertEqual(respuesta.status_code, 404)
                self.assertEqual(list(presupuesto.optimizaciones.all()), [self.plan])
                self.assertTrue(Optimizacion.objects.filter(pk=self.ajeno.pk).exists())

    def test_borrado_valido_admite_repetidos_y_requiere_post(self):
        self.assertEqual(self.client.get(self.borrar).status_code, 405)
        self.assertRedirects(self.client.post(self.borrar), self.historial, fetch_redirect_response=False)
        self.assertTrue(Optimizacion.objects.filter(pk=self.plan.pk).exists())
        respuesta = self.client.post(self.borrar, {'seleccion': [self.plan.pk, self.plan.pk]})
        self.assertRedirects(respuesta, self.historial, fetch_redirect_response=False)
        self.assertFalse(Optimizacion.objects.filter(pk=self.plan.pk).exists())
        self.assertTrue(Optimizacion.objects.filter(pk=self.ajeno.pk).exists())

    def test_preselecciones_invalidas_se_rechazan_antes_de_crear(self):
        for vista in ('crear_presupuesto', 'crear_plantilla'):
            url = reverse(f'cutless:{vista}')
            for valor in ('abc', '12abc', '1.5', '1e1', '0', '1_2', str(2**63)):
                with self.subTest(vista=vista, valor=valor):
                    respuesta = self.client.get(url, {'optimizacion': valor})
                    self.assertContains(respuesta, 'identificador inválido', status_code=400)
                    respuesta = self.client.post(url, {'nombre': 'Sin guardar'}, query_params={'optimizacion': valor})
                    self.assertContains(respuesta, 'identificador inválido', status_code=400)
        self.assertFalse(Presupuesto.objects.exists())
        self.assertFalse(Plantilla.objects.exists())

    def test_preseleccion_respeta_propietario_y_sigue_siendo_opcional(self):
        for vista in ('crear_presupuesto', 'crear_plantilla'):
            url = reverse(f'cutless:{vista}')
            for referencia in (self.ajeno.pk, 2**63 - 1):
                with self.subTest(vista=vista, referencia=referencia):
                    self.assertEqual(self.client.get(url, {'optimizacion': referencia}).status_code, 404)
            respuesta = self.client.get(url, {'optimizacion': self.plan.pk})
            self.assertEqual(respuesta.status_code, 200)
            self.assertEqual(respuesta.context['optimizacion'], self.plan)
            respuesta = self.client.get(url, {'optimizacion': ''})
            self.assertEqual(respuesta.status_code, 200)
            self.assertIsNone(respuesta.context['optimizacion'])

    @override_settings(DEBUG=False)
    def test_errores_no_revelan_la_existencia_del_plan_ajeno(self):
        for vista in ('crear_presupuesto', 'crear_plantilla'):
            url = reverse(f'cutless:{vista}')
            for referencia in (self.ajeno.pk, 2**63 - 1):
                respuesta = self.client.get(url, {'optimizacion': referencia})
                self.assertTemplateUsed(respuesta, 'cutless/404.html')
                self.assertContains(respuesta, 'Página no encontrada', status_code=404)
                self.assertNotContains(respuesta, self.ajeno.nombre, status_code=404)

        respuestas_400 = []
        for referencia in (self.ajeno.pk, 2**63 - 1):
            respuesta = self.client.post(self.borrar, {'seleccion': [self.plan.pk, referencia]})
            self.assertTemplateUsed(respuesta, 'cutless/404.html')
            self.assertContains(respuesta, 'Página no encontrada', status_code=404)
            self.assertNotContains(respuesta, self.ajeno.nombre, status_code=404)
            error = self.client.post(self.borrar, {'seleccion': [referencia, 'abc']})
            self.assertEqual(error.status_code, 400)
            respuestas_400.append(error.content)
        self.assertEqual(*respuestas_400)
        self.assertNotIn(self.ajeno.nombre.encode(), respuestas_400[0])
        self.assertTrue(Optimizacion.objects.filter(pk=self.plan.pk).exists())
        self.assertTrue(Optimizacion.objects.filter(pk=self.ajeno.pk).exists())


class DecimalesMaterialTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_superuser('num01_material')
        self.client.force_login(self.usuario)
        self.material = Material.objects.create(usuario=self.usuario, nombre='Material original', ancho=100, alto=200,
                                                unidad_medida='cm', precio=Decimal('20.00'))
        self.alta = reverse('cutless:crear_material')
        self.edicion = reverse('cutless:editar_material', args=[self.material.pk])
        self.datos = {'nombre': 'Material sintético', 'ancho': '122,1250', 'alto': '244.25', 'unidad_medida': 'cm',
                      'precio': '12,5', 'descripcion': 'Descripción conservada'}

    def test_alta_con_coma_y_punto_guarda_dimensiones_y_precio_exacto(self):
        self.assertEqual(self.client.post(self.alta, self.datos).status_code, 302)
        material = Material.objects.get(nombre=self.datos['nombre'], usuario=self.usuario)
        self.assertEqual((material.ancho, material.alto, material.precio), (122.125, 244.25, Decimal('12.50')))

    def test_edicion_con_coma_y_punto_conserva_conversion_de_unidad(self):
        datos = {**self.datos, 'ancho': '1,22125', 'alto': '2.4425', 'unidad_medida': 'm', 'precio': '12.5'}
        self.assertEqual(self.client.post(self.edicion, datos).status_code, 302)
        self.material.refresh_from_db()
        self.assertEqual((self.material.ancho, self.material.alto, self.material.precio), (122.125, 244.25, Decimal('12.50')))

    def test_formatos_invalidos_no_guardan_y_conservan_todos_los_campos(self):
        for url in (self.alta, self.edicion):
            for campo, valor in (('precio', '1_2'), ('precio', '1.234,56'), ('precio', '1e1'),
                                 ('precio', '12,345'), ('precio', '100000000'), ('precio', '-0,01'),
                                 ('ancho', 'NaN'), ('alto', '12 5'), ('ancho', '300,01'),
                                 ('ancho', '1.000'), ('ancho', '1,000'), ('alto', '100.000')):
                with self.subTest(url=url, campo=campo):
                    entrada = {**self.datos, campo: valor}
                    if valor in ('1.000', '1,000'):
                        # En metros, interpretar el texto como 1 daría una medida válida.
                        entrada.update(unidad_medida='m', alto='2.44')
                    respuesta = self.client.post(url, entrada)
                    self.assertEqual(respuesta.status_code, 200)
                    form = respuesta.context['form']
                    self.assertTrue(form.has_error(campo), form.errors)
                    for nombre, dato in entrada.items():
                        self.assertEqual(form[nombre].value(), dato)
                    self.assertEqual(Material.objects.filter(usuario=self.usuario).count(), 1)
                    self.material.refresh_from_db()
                    self.assertEqual((self.material.nombre, self.material.precio), ('Material original', Decimal('20.00')))

    def test_edicion_preserva_medidas_historicas_y_material_asociado(self):
        self.material.ancho = 122.125
        self.material.alto = 244.125
        self.material.save(update_fields=['ancho', 'alto'])
        plan = Optimizacion.objects.create(usuario=self.usuario, material=self.material, ancho_tablero=122.125,
                                           alto_tablero=244.125, piezas='Pieza,20,30,1', precio_tablero=Decimal('20.00'))
        form = self.client.get(self.edicion).context['form']
        self.assertEqual(form['ancho'].value(), '122.1250')
        self.assertEqual(form['alto'].value(), '244.1250')
        datos = {**self.datos, 'ancho': form['ancho'].value(), 'alto': form['alto'].value(), 'precio': '12,5'}
        self.assertEqual(self.client.post(self.edicion, datos).status_code, 302)
        self.material.refresh_from_db()
        plan.refresh_from_db()
        self.assertEqual((self.material.ancho, self.material.alto), (122.125, 244.125))
        self.assertEqual(plan.material_id, self.material.pk)
        self.assertEqual(plan.precio_tablero, Decimal('20.00'))

    def test_precio_opcional_cero_y_maximo_se_distinguen(self):
        for valor, esperado in (('', None), ('0', Decimal('0')), ('99999999,99', Decimal('99999999.99'))):
            with self.subTest(valor=valor):
                self.assertEqual(self.client.post(self.edicion, {**self.datos, 'precio': valor}).status_code, 302)
                self.material.refresh_from_db()
                self.assertEqual(self.material.precio, esperado)

    def test_edicion_ajena_no_cambia_datos(self):
        ajeno = User.objects.create_superuser('num01_material_ajeno')
        self.client.force_login(ajeno)
        self.assertRedirects(self.client.post(self.edicion, self.datos), reverse('cutless:lista_materiales'),
                             fetch_redirect_response=False)
        self.material.refresh_from_db()
        self.assertEqual(self.material.precio, Decimal('20.00'))
