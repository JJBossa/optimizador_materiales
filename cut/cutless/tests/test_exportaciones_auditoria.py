import re
from datetime import date
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from openpyxl import load_workbook
from reportlab import rl_config

from cutless.exports.excel import (
    generar_excel, generar_excel_historial_costos, generar_excel_resumen_desperdicio,
)
from cutless.exports.pdf import generar_pdf_presupuesto
from cutless.models import Material, Optimizacion, Presupuesto


class ExportacionesAuditoriaTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user('exportaciones')

    def test_excel_conserva_literales_en_los_tres_exportadores(self):
        textos = ('=1+1', '+2', '-3', '@texto', '#N/A', 'Ñ, «pieza»')
        material = Material.objects.create(nombre=textos[0], ancho=122, alto=244, usuario=self.usuario)
        opt = Optimizacion.objects.create(usuario=self.usuario, nombre=textos[0], material=material,
                                         ancho_tablero=122, alto_tablero=244, piezas='10,20,1',
                                         precio_tablero=10, num_tableros=1)
        piezas = [dict(nombre=nombre, ancho=10, alto=20, cantidad=1) for nombre in textos]
        libro = load_workbook(generar_excel(opt, {}, piezas))
        for fila, texto in enumerate(textos, start=2):
            celda = libro['Piezas'].cell(fila, 1)
            self.assertEqual((celda.value, celda.data_type), (texto, 's'))
        celdas = [celda for fila in libro['Resumen'] for celda in fila if celda.value == textos[0]]
        self.assertEqual(len(celdas), 2)
        self.assertTrue(all(celda.data_type == 's' for celda in celdas))

        costos = [dict(optimizacion=opt, costo_material=10, costo_mano_obra=0, costo_total=10)]
        historial = load_workbook(generar_excel_historial_costos(costos, {}))
        celda = historial['Detalle de Costos']['D2']
        self.assertEqual((celda.value, celda.data_type), (textos[0], 's'))

        desperdicio = load_workbook(generar_excel_resumen_desperdicio(Optimizacion.objects.all(), {}))
        self.assertFalse(any(celda.data_type == 'f' for hoja in desperdicio for fila in hoja for celda in fila))

    def test_pdf_pagina_lista_de_piezas_tabla_y_notas(self):
        presupuesto = Presupuesto.objects.create(usuario=self.usuario, numero='PRE-PDF-1', precio_tablero=10,
                                                 mano_obra=7, costo_total=17, fecha_validez=date.today())
        with BytesIO() as simple:
            generar_pdf_presupuesto(presupuesto, simple)
            self.assertEqual(len(re.findall(rb'/Type\s*/Page\b', simple.getvalue())), 1)

        planes = [
            Optimizacion(usuario=self.usuario, nombre=f'Plan & conjunto {i}',
                         ancho_tablero=122, alto_tablero=244, piezas='Pieza <b>,10,20,1',
                         num_tableros=1)
            for i in range(65)
        ]
        presupuesto.optimizaciones.set(Optimizacion.objects.bulk_create(planes))
        presupuesto = Presupuesto.objects.get(pk=presupuesto.pk)
        presupuesto.notas = 'Información de prueba <literal>\n' * 100
        with BytesIO() as largo, patch.object(rl_config, 'pageCompression', 0):
            generar_pdf_presupuesto(presupuesto, largo)
            pdf = largo.getvalue()
            self.assertGreater(len(re.findall(rb'/Type\s*/Page\b', pdf)), 5)
            self.assertGreater(pdf.count(b'Precio unitario'), 1)
            self.assertIn(b'Plan & conjunto 64', pdf)
            self.assertIn(b'TOTAL: $657.00', pdf)
