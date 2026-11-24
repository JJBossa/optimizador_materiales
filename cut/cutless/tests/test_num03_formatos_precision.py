from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from cutless.forms import PiezaForm, PlantillaForm, TableroForm
from cutless.models import Cliente, Material, Optimizacion, Plantilla, Proyecto
from cutless.pieces import parsear_piezas_desde_texto


def ruta(nombre, *args):
    return reverse('cutless:' + nombre, args=args)


class FormatosPrecisionTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user('num03')
        self.client.force_login(self.usuario)
        self.datos_opt = {
            'nombre_optimizacion': 'Ensayo', 'ancho': '122', 'alto': '244', 'unidad_medida': 'cm',
            'margen_corte': '2.15', 'precio_tablero': '37.25', 'mano_obra': '15.75',
            'permitir_rotacion': 'on',
            'form-TOTAL_FORMS': 1, 'form-INITIAL_FORMS': 0,
            'form-0-nombre': 'Pieza sintética', 'form-0-ancho': '20',
            'form-0-alto': '30', 'form-0-cantidad': '1',
        }
        self.datos_plantilla = {
            'nombre': 'Ensayo', 'descripcion': 'Descripción', 'categoria': 'otros',
            'ancho_tablero': '122', 'alto_tablero': '244', 'unidad_medida': 'cm',
            'permitir_rotacion': 'on', 'margen_corte': '2.15', 'piezas': 'Pieza sintética,20,30,1',
        }

    def test_coma_y_punto_en_alta_y_edicion_de_optimizacion(self):
        for ancho, pieza, margen, precio, vista in (
            ('12,5', '2,5', '0,5', '12,5', 'index'),
            ('12.5', '2.5', '0.01', '12.50', 'editar_optimizacion'),
        ):
            anteriores = list(Optimizacion.objects.all())
            args = [anteriores[0].pk] if anteriores else []
            datos = {**self.datos_opt, 'ancho': ancho, 'form-0-ancho': pieza,
                     'margen_corte': margen, 'precio_tablero': precio}
            self.assertEqual(self.client.post(ruta(vista, *args), datos).status_code, 302)
            plan = Optimizacion.objects.get()
            self.assertEqual(plan.ancho_tablero, 12.5)
            self.assertEqual(plan.margen_corte, .05 if vista == 'index' else .001)
            self.assertEqual(plan.precio_tablero, Decimal('12.50'))
            self.assertEqual(parsear_piezas_desde_texto(plan.piezas)[0]['ancho'], 2.5)

    def test_coma_y_punto_en_alta_y_edicion_de_plantilla(self):
        self.assertEqual(self.client.post(ruta('crear_plantilla'), {
            **self.datos_plantilla, 'ancho_tablero': '12,5', 'piezas': 'P,2.5,30,1', 'margen_corte': '2,15',
        }).status_code, 302)
        item = Plantilla.objects.get()
        self.assertEqual((item.ancho_tablero, item.margen_corte), (12.5, .215))
        self.assertEqual(self.client.post(ruta('editar_plantilla', item.pk), {
            **self.datos_plantilla, 'ancho_tablero': '12.5', 'piezas': 'P,2.5,30,1', 'margen_corte': '2.15',
        }).status_code, 302)
        item.refresh_from_db()
        self.assertEqual((item.ancho_tablero, item.margen_corte), (12.5, .215))

    def test_rechaza_formatos_ambiguos_no_finitos_y_sintaxis_extrana(self):
        for valor in ('1.000', '1,000', '1e2', '1_22', 'Infinity', 'NaN'):
            with self.subTest(valor=valor):
                for clase, campos, base in (
                    (TableroForm, ('ancho', 'margen_corte', 'precio_tablero'), self.datos_opt),
                    (PiezaForm, ('ancho',), {'ancho': '12', 'alto': '30', 'cantidad': '1'}),
                    (PlantillaForm, ('ancho_tablero', 'margen_corte'), self.datos_plantilla),
                ):
                    form = clase({**base, **dict.fromkeys(campos, valor)})
                    self.assertFalse(form.is_valid())
                    for campo in campos:
                        self.assertIn(campo, form.errors)
                        self.assertEqual(form[campo].value(), valor)

    def test_cantidad_estricta_y_limites(self):
        for valor in ('1.000', '1,000', '1.0', '1e1', '1_0', '-1', '0', '101', '+1', '１'):
            with self.subTest(valor=valor):
                self.assertIn('cantidad', PiezaForm({'ancho': '20', 'alto': '30', 'cantidad': valor}).errors)
        for valor, esperado in (('1', 1), ('100', 100), ('', 1)):
            form = PiezaForm({'ancho': '20', 'alto': '30', 'cantidad': valor})
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data['cantidad'], esperado)

    def test_convierte_tableros_y_piezas_en_cinco_unidades(self):
        for unidad, lado, pieza, esperado in (
            ('cm', '122', '40', 122), ('mm', '1220', '400', 122),
            ('m', '1.22', '.4', 122), ('in', '48.08', '8', 122.1232), ('ft', '4', '1', 121.92),
        ):
            with self.subTest(unidad=unidad):
                base = {'unidad_medida': unidad, 'margen_corte': '2,15'}
                tablero = TableroForm({**base, 'ancho': lado, 'alto': lado})
                fila = PiezaForm({**base, 'ancho': pieza, 'alto': pieza, 'cantidad': '1'})
                plantilla = PlantillaForm({
                    **self.datos_plantilla, **base, 'ancho_tablero': lado, 'alto_tablero': lado,
                    'piezas': f'P,{pieza},{pieza},1',
                })
                for form in (tablero, fila, plantilla):
                    self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(tablero.cleaned_data['ancho_cm'], esperado)
                self.assertEqual(plantilla.cleaned_data['ancho_tablero'], esperado)
                self.assertEqual(tablero.cleaned_data['margen_corte_cm'], .215)
                self.assertEqual(plantilla.cleaned_data['margen_corte'], .215)
                p = parsear_piezas_desde_texto(plantilla.cleaned_data['piezas'], unidad)[0]
                self.assertEqual(fila.cleaned_data['ancho_cm'], p['ancho_cm'])

    def test_plantilla_preserva_historico_al_editar_y_cargar(self):
        original = 'piezas:v1:Panel, norte,.5,1,2'
        item = Plantilla.objects.create(
            usuario=self.usuario, nombre='Histórica', unidad_medida='ft', ancho_tablero=122.1234567,
            alto_tablero=300, margen_corte=.215, piezas=original,
        )
        editar = ruta('editar_plantilla', item.pk)
        inicial = self.client.get(editar).context['form']
        datos = {campo: inicial[campo].value() for campo in self.datos_plantilla}
        datos['descripcion'] = 'Solo descripción'
        self.assertEqual(self.client.post(editar, datos).status_code, 302)
        item.refresh_from_db()
        self.assertEqual((item.ancho_tablero, item.alto_tablero, item.margen_corte, item.piezas),
                         (122.1234567, 300.0, .215, original))
        cargar = self.client.get(ruta('usar_plantilla', item.pk))
        self.assertEqual(cargar.status_code, 200)
        self.assertEqual(cargar.context['pieza_formset'].initial[0]['nombre'], 'piezas:v1:Panel, norte')
        self.guardar_desde_precarga(cargar, (122.1234567, 300, .215))

    def guardar_desde_precarga(self, respuesta, esperado):
        form = respuesta.context['tablero_form']
        campos = ('ancho', 'alto', 'unidad_medida', 'margen_corte', 'origen_medidas')
        datos = {**self.datos_opt, **{campo: form[campo].value() for campo in campos},
                 'form-0-ancho': '.5', 'form-0-alto': '1'}
        self.assertEqual(self.client.post(ruta('index'), datos).status_code, 302)
        opt = Optimizacion.objects.latest('pk')
        self.assertEqual((opt.ancho_tablero, opt.alto_tablero, opt.margen_corte), esperado)

    def test_optimizacion_preserva_geometria_y_texto_historico_en_edicion_y_duplicado(self):
        original = Optimizacion.objects.create(
            usuario=self.usuario, ancho_tablero=122.1234567, alto_tablero=300,
            unidad_medida='ft', margen_corte=.215, piezas='Panel,.5,1,1',
        )
        editar = ruta('editar_optimizacion', original.pk)
        form = self.client.get(editar).context['tablero_form']
        datos = {**self.datos_opt, **{k: form[k].value() for k in ('ancho','alto','unidad_medida','margen_corte')},
                 'form-0-nombre': 'Panel', 'form-0-ancho': '.5', 'form-0-alto': '1'}
        self.assertEqual(self.client.post(editar, datos).status_code, 302)
        original.refresh_from_db()
        self.assertEqual((original.ancho_tablero, original.alto_tablero, original.margen_corte, original.piezas),
                         (122.1234567, 300, .215, 'Panel,.5,1,1'))
        self.guardar_desde_precarga(self.client.get(ruta('duplicar_optimizacion', original.pk)),
                                    (122.1234567, 300, .215))

    def test_origen_de_otra_cuenta_o_modificado_se_rechaza(self):
        original = Optimizacion.objects.create(usuario=self.usuario, ancho_tablero=122, alto_tablero=244,
                                               piezas='Panel,20,30,1')
        token = TableroForm.firmar_origen(original, self.usuario)
        otro = User.objects.create_user('num03_otro')
        for origen, cuenta in ((token + 'X', self.usuario), (token, otro)):
            form = TableroForm({**self.datos_opt, 'origen_medidas': origen}, user=cuenta)
            self.assertIn('origen_medidas', form.errors)
        self.client.force_login(otro)
        self.assertEqual(self.client.get(ruta('duplicar_optimizacion', original.pk)).status_code, 404)

    def test_csv_reversible_con_nombre_complejo_y_punto_decimal(self):
        nombre = 'Puerta, "norte" Ω\nNivel 2'
        datos = {**self.datos_plantilla, 'piezas': '"Puerta, ""norte"" Ω\r\nNivel 2",12.1250,30,1'}
        form = PlantillaForm(datos)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.filas_editor[0][0].replace('\r\n', '\n'), nombre)
        self.assertEqual(parsear_piezas_desde_texto(form.cleaned_data['piezas'])[0]['nombre'], nombre)
        for csv in ('P,"12,5",30,1', 'P,12,5,30,1', 'P,12.5,30,1.000', 'P,12.5,30,1_0'):
            form = PlantillaForm({**datos, 'piezas': csv})
            self.assertIn('piezas', form.errors)
            self.assertEqual(form['piezas'].value(), csv)

    def test_reintento_conserva_tablero_costos_y_asociaciones(self):
        material = Material.objects.create(usuario=self.usuario, nombre='Catálogo', ancho=142, alto=210, precio='12.50')
        cliente = Cliente.objects.create(usuario=self.usuario, nombre='Cliente')
        proyecto = Proyecto.objects.create(usuario=self.usuario, nombre='Proyecto')
        datos = {**self.datos_opt, 'ancho': '132.1250', 'alto': '242.25', 'precio_tablero': '37,25',
                 'form-0-ancho': '200', 'form-0-alto': '240', 'material': material.pk,
                 'cliente': cliente.pk, 'proyecto': proyecto.pk}
        error = self.client.post(ruta('index'), datos)
        self.assertEqual(error.status_code, 200)
        form = error.context['tablero_form']
        for campo in ('ancho','alto','precio_tablero','mano_obra','margen_corte','material','cliente','proyecto'):
            self.assertEqual(form[campo].value(), str(datos[campo]))
        self.assertFalse(Optimizacion.objects.exists())
        self.assertEqual(self.client.post(ruta('index'), {
            **datos, 'form-0-ancho': '20', 'form-0-alto': '30',
        }).status_code, 302)
        opt = Optimizacion.objects.get()
        self.assertEqual((opt.ancho_tablero, opt.alto_tablero, opt.margen_corte), (132.125, 242.25, .215))
        self.assertEqual((opt.precio_tablero, opt.mano_obra), (Decimal('37.25'), Decimal('15.75')))
        self.assertEqual((opt.material_id, opt.cliente_id, opt.proyecto_id, opt.permitir_rotacion),
                         (material.pk, cliente.pk, proyecto.pk, True))
