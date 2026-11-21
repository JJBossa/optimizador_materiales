import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import User
from django.core import mail
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from matplotlib import pyplot as plt
from openpyxl import load_workbook
from reportlab import rl_config

from cutless.exports.excel import generar_excel
from cutless.formato_clp import formatear_clp
from cutless.models import Material, Optimizacion, Presupuesto

NOTA_REDONDEO = 'Los importes se muestran redondeados al peso. El total se calcula utilizando los valores originales.'


class FormatoClpTests(SimpleTestCase):
    def test_casos_compartidos_del_filtro_y_formateador(self):
        casos = json.loads(Path(__file__).with_name('casos_formato_clp.json').read_text(encoding='utf-8'))
        plantilla = Template('{% load moneda %}{{ monto|clp:con_signo }}')
        for monto, esperado, *signo in casos:
            with self.subTest(monto=monto, signo=signo):
                con_signo = bool(signo)
                self.assertEqual(formatear_clp(monto, con_signo), esperado)
                self.assertEqual(plantilla.render(Context({'monto': monto, 'con_signo': con_signo})), esperado)
        self.assertEqual(formatear_clp(Decimal('9007199254740993.50')), '$9.007.199.254.740.994')
        self.assertEqual(formatear_clp(1e-8), 'Menos de $1')
        for valor in (True, float('inf'), Decimal('NaN')):
            self.assertEqual(formatear_clp(valor), '—')

    def test_administrador_formatea_columnas_y_orden_numerico(self):
        optimizacion = Optimizacion(num_tableros=1, precio_tablero=Decimal('0'), mano_obra=Decimal('0'))
        self.assertEqual(admin.site.get_model_admin(Optimizacion).costo_total_display(optimizacion), '$0')
        material_admin = admin.site.get_model_admin(Material)
        self.assertEqual(material_admin.precio_display(Material(precio=Decimal('40000.25'))), '$40.000')
        self.assertEqual(material_admin.precio_display.admin_order_field, 'precio')


class PresentacionClpTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_superuser('formato-clp', email='clp@example.test')
        self.client.force_login(self.usuario)
        self.plan = Optimizacion.objects.create(
            usuario=self.usuario, ancho_tablero=122, alto_tablero=244, piezas='Puerta,40,50,1',
            num_tableros=2, precio_tablero=Decimal('40000.25'), mano_obra=Decimal('15750.80'),
        )

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_presupuesto_conserva_decimales_en_formulario_datos_y_exportaciones(self):
        perfil = self.usuario.perfil
        perfil.notificaciones_email = True
        perfil.notificaciones_pantalla = True
        perfil.notificar_presupuesto_creado = True
        perfil.save()
        respuesta = self.client.post(reverse('cutless:crear_presupuesto'), {
            'optimizaciones': [self.plan.pk], 'precio_tablero': '40000.25', 'mano_obra': '15750.80',
            'fecha_validez': date.today().isoformat(), 'estado': 'borrador',
        }, follow=True)
        self.assertContains(respuesta, '$40.000')
        self.assertContains(respuesta, '$15.751')
        self.assertContains(respuesta, 'costo total de $95.751')
        self.assertContains(respuesta, NOTA_REDONDEO, count=1)
        self.assertNotContains(self.client.get(reverse('cutless:lista_presupuestos')), NOTA_REDONDEO)
        self.assertContains(respuesta, 'data-total-clp="95751.30"')
        self.assertIn('costo total de $95.751', mail.outbox[-1].body)

        presupuesto = Presupuesto.objects.get(usuario=self.usuario)
        editar = self.client.get(reverse('cutless:editar_presupuesto', args=[presupuesto.pk]))
        self.assertEqual(editar.context['form']['precio_tablero'].value(), Decimal('40000.25'))
        self.assertEqual(editar.context['form']['mano_obra'].value(), Decimal('15750.80'))
        self.assertEqual(editar.context['form'].fields['precio_tablero'].widget.attrs['step'], '0.01')
        self.assertEqual(presupuesto.costo_total, Decimal('95751.30'))

        with patch.object(rl_config, 'pageCompression', 0):
            pdf = self.client.get(reverse('cutless:generar_pdf_presupuesto', args=[presupuesto.pk]))
            self.assertEqual(pdf['Content-Type'], 'application/pdf')
            self.assertIn(b'TOTAL: $95,751.30', b''.join(pdf.streaming_content))
        excel = load_workbook(generar_excel(self.plan, {}, []))
        self.assertIn('$95,751', [celda.value for fila in excel['Resumen'] for celda in fila])

    def test_grafico_formatea_el_eje_sin_redondear_los_datos(self):
        etiquetas = []
        serie = []

        def capturar(*args, **kwargs):
            eje = plt.gca()
            etiquetas.extend(eje.yaxis.get_major_formatter()(valor) for valor in (40000, 96000))
            serie.extend(eje.lines[0].get_ydata())

        with patch('matplotlib.pyplot.savefig', side_effect=capturar):
            respuesta = self.client.get(reverse('cutless:historial_costos'))
        self.assertContains(respuesta, '$95.751')
        self.assertContains(respuesta, NOTA_REDONDEO, count=1)
        self.assertEqual(etiquetas, ['$40.000', '$96.000'])
        self.assertEqual(serie, [95751.3])
        self.assertEqual(respuesta.context['costo_total'], Decimal('95751.30'))

    def test_grafico_con_importe_menor_a_un_peso_no_repite_la_etiqueta(self):
        self.plan.precio_tablero = Decimal('0.10')
        self.plan.mano_obra = Decimal('0.05')
        self.plan.save(update_fields=['precio_tablero', 'mano_obra'])
        etiquetas = []

        def capturar(*args, **kwargs):
            eje = plt.gca()
            etiquetas.extend(txt.get_text() for txt in eje.get_yticklabels())

        with patch('matplotlib.pyplot.savefig', side_effect=capturar):
            respuesta = self.client.get(reverse('cutless:historial_costos'))
        self.assertContains(respuesta, 'Menos de $1')
        self.assertEqual(respuesta.context['costo_total'], Decimal('0.25'))
        self.assertEqual(etiquetas.count('Menos de $1'), 1)

    def test_comparacion_conserva_la_diferencia_inferior_a_un_peso(self):
        otro = Optimizacion.objects.create(
            usuario=self.usuario, ancho_tablero=122, alto_tablero=244, piezas=self.plan.piezas,
            num_tableros=2, precio_tablero=self.plan.precio_tablero, mano_obra=Decimal('15750.55'),
        )
        pagina = self.client.get(reverse('cutless:comparar_optimizaciones'), {'opt1': self.plan.pk, 'opt2': otro.pk})
        self.assertEqual(pagina.context['comparacion']['diferencia_costo'], Decimal('-0.25'))
        self.assertContains(pagina, '-(menos de $1)')
        self.assertContains(pagina, 'costo estimado menor en menos de $1')
        self.assertContains(pagina, 'm²')
        self.assertNotContains(pagina, NOTA_REDONDEO)
