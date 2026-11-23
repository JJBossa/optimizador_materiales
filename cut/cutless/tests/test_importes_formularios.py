from datetime import timedelta
from decimal import Decimal, localcontext

from django import forms
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from cutless.formatos_numericos import preparar_importe
from cutless.forms.materials import MaterialAdminForm, MaterialForm
from cutless.forms.numeros import ImporteDecimalField, ImporteEntradaField
from cutless.models import Material, Optimizacion, Presupuesto


class PresentacionImportesTests(SimpleTestCase):
    def test_quita_solo_ceros_decimales_sin_redondear(self):
        casos = (
            ('10000.00', '10000'), ('5500.00', '5500'), ('12500.50', '12500.5'),
            ('12500.25', '12500.25'), ('0.00', '0'), ('-0.00', '0'),
            ('1E+5', '100000'), ('-12.00', '-12'), ('123456789.1234500', '123456789.12345'),
        )
        with localcontext() as contexto:
            contexto.prec = 6
            for original, esperado in casos:
                with self.subTest(original=original):
                    valor = Decimal(original)
                    importe = preparar_importe(valor)
                    self.assertIsInstance(importe, Decimal)
                    self.assertEqual(importe, valor)
                    self.assertEqual(format(importe, 'f'), esperado)

    def test_bound_fields_conservan_texto_y_sintaxis_de_cada_campo(self):
        class ImportesForm(forms.Form):
            numero = ImporteDecimalField(max_digits=10, decimal_places=2, required=False)
            texto = ImporteEntradaField(max_digits=10, decimal_places=2, required=False)

        form = ImportesForm({'numero': '10000.00', 'texto': '12500,50'})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data, {'numero': Decimal('10000'), 'texto': Decimal('12500.50')})
        self.assertEqual(form['numero'].value(), '10000.00')
        self.assertEqual(form['texto'].value(), '12500,50')

        form = ImportesForm({'numero': '12500,50', 'texto': '1,000'})
        self.assertFalse(form.is_valid())
        for campo, valor in (('numero', '12500,50'), ('texto', '1,000')):
            self.assertTrue(form.has_error(campo, 'invalid'))
            self.assertEqual(form[campo].value(), valor)

        form = ImportesForm(initial={'numero': None, 'texto': Decimal('12.3450')})
        self.assertIsNone(form['numero'].value())
        self.assertEqual(form['texto'].value(), '12.3450')


class OperacionesConImportesTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_superuser('vis05')
        self.client.force_login(self.usuario)

    def test_materiales_permiten_editar_metadatos_sin_marcar_precio_como_cambiado(self):
        material = Material.objects.create(usuario=self.usuario, nombre='Material VIS-05',
                                           ancho=122.1234, alto=244, precio=Decimal('10000.00'))
        datos = {'nombre': material.nombre, 'ancho': '122.1234', 'alto': '244', 'unidad_medida': 'cm',
                 'precio': '10000', 'descripcion': 'Descripción actualizada', 'usuario': self.usuario.pk}
        for formulario in (MaterialForm, MaterialAdminForm):
            with self.subTest(formulario=formulario.__name__):
                instancia = Material.objects.get(pk=material.pk)
                form = formulario(instance=instancia)
                self.assertEqual(str(form['precio'].value()), '10000')
                self.assertEqual(form['ancho'].value(), 122.1234)
                envio = formulario(datos, instance=instancia)
                self.assertTrue(envio.is_valid(), envio.errors)
                self.assertEqual(envio.cleaned_data['precio'], Decimal('10000.00'))
                self.assertEqual(envio.campos_actualizacion(), {'descripcion', 'fecha_actualizacion'})
        material.refresh_from_db()
        self.assertEqual((material.precio, material.ancho), (Decimal('10000.00'), 122.1234))

    def test_presupuesto_conserva_el_total_exactamente_al_reenviar_el_importe_visible(self):
        plan = Optimizacion.objects.create(usuario=self.usuario, ancho_tablero=122, alto_tablero=244,
                                            piezas='Pieza,40,50,1', num_tableros=2)
        datos = {'precio_tablero': '12500.50', 'mano_obra': '12500.25', 'optimizaciones': [plan.pk],
                 'fecha_validez': timezone.localdate() + timedelta(days=2), 'estado': 'borrador'}
        respuesta = self.client.post(reverse('cutless:crear_presupuesto'), datos)
        self.assertEqual(respuesta.status_code, 302)
        presupuesto = Presupuesto.objects.get()
        ruta = reverse('cutless:editar_presupuesto', args=[presupuesto.pk])
        form = self.client.get(ruta).context['form']
        self.assertEqual(str(form['precio_tablero'].value()), '12500.5')
        self.assertEqual(str(form['mano_obra'].value()), '12500.25')
        respuesta = self.client.post(ruta, {**datos, 'precio_tablero': '12500.5', 'notas': 'Revisado'})
        self.assertEqual(respuesta.status_code, 302)
        presupuesto.refresh_from_db()
        self.assertEqual((presupuesto.precio_tablero, presupuesto.mano_obra, presupuesto.costo_total),
                         (Decimal('12500.50'), Decimal('12500.25'), Decimal('37501.25')))

    def test_alta_y_edicion_de_optimizacion_preservan_centavos_y_calculo(self):
        alta = reverse('cutless:index')
        form = self.client.get(alta).context['tablero_form']
        for campo in ('precio_tablero', 'mano_obra'):
            self.assertIsNone(form[campo].value())
            self.assertEqual(form[campo].field.widget.attrs['placeholder'], '0')
        datos = {
            'nombre_optimizacion': 'Vis 05', 'unidad_medida': 'cm', 'ancho': '122', 'alto': '244',
            'margen_corte': '1.25', 'precio_tablero': '12500,50', 'mano_obra': '12500.25',
            'form-TOTAL_FORMS': 1, 'form-INITIAL_FORMS': 0, 'form-0-nombre': 'Pieza',
            'form-0-ancho': '20', 'form-0-alto': '30', 'form-0-cantidad': '1',
        }
        self.assertEqual(self.client.post(alta, {**datos, 'mano_obra': ''}).status_code, 302)
        plan = Optimizacion.objects.get()
        ruta = reverse('cutless:editar_optimizacion', args=[plan.pk])
        form = self.client.get(ruta).context['tablero_form']
        self.assertEqual(str(form['precio_tablero'].value()), '12500.5')
        self.assertEqual(str(form['mano_obra'].value()), '0')
        self.assertEqual(plan.get_costo_total(), Decimal('12500.50'))
        self.assertEqual(self.client.post(ruta, {**datos, 'precio_tablero': '12500.5', 'mano_obra': '12500,25'}).status_code, 302)
        plan.refresh_from_db()
        self.assertEqual((plan.precio_tablero, plan.mano_obra, plan.get_costo_total()),
                         (Decimal('12500.50'), Decimal('12500.25'), Decimal('25000.75')))
        self.assertEqual(str(self.client.get(ruta).context['tablero_form']['mano_obra'].value()), '12500.25')
        self.assertEqual(self.client.post(ruta, {**datos, 'mano_obra': ''}).status_code, 302)
        plan.refresh_from_db()
        self.assertEqual((plan.mano_obra, plan.get_costo_total()), (Decimal('0'), Decimal('12500.50')))
