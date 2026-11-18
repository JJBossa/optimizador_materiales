from django.test import TestCase

from cutless.pieces import parsear_piezas_desde_texto


class ParsearPiezasTests(TestCase):
    def test_formato_con_nombre(self):
        texto = "Puerta,80,200,2\nCajon,40,50,4"
        piezas = parsear_piezas_desde_texto(texto, 'cm')

        self.assertEqual(len(piezas), 2)
        self.assertEqual(piezas[0]['nombre'], 'Puerta')
        self.assertEqual(piezas[0]['cantidad'], 2)
        self.assertEqual(piezas[0]['ancho_cm'], 80.0)

    def test_formato_legacy_tres_campos(self):
        texto = "80,200,2\n40,50,1"
        piezas = parsear_piezas_desde_texto(texto, 'cm')

        self.assertEqual(len(piezas), 2)
        self.assertEqual(piezas[0]['nombre'], 'Pieza 1')
        self.assertEqual(piezas[0]['ancho'], 80.0)
        self.assertEqual(piezas[0]['alto'], 200.0)
        self.assertEqual(piezas[0]['cantidad'], 2)
        self.assertEqual(piezas[1]['nombre'], 'Pieza 2')

    def test_lineas_invalidas_se_ignoran(self):
        texto = "malformado\n80,200,2"
        piezas = parsear_piezas_desde_texto(texto, 'cm')
        self.assertEqual(len(piezas), 1)

    def test_formato_versionado_conserva_nombre_multilinea(self):
        from cutless.pieces import serializar_piezas

        original = {'nombre': 'Repisas, «sur»\nNivel 2', 'ancho': 10.5, 'alto': 8, 'cantidad': 3}
        resultado, = parsear_piezas_desde_texto(serializar_piezas([original]), 'mm', estricto=True)
        self.assertEqual({campo: resultado[campo] for campo in original}, original)
        self.assertAlmostEqual(resultado['ancho_cm'], 1.05)

    def test_prefijo_reservado_puede_formar_parte_de_un_nombre_historico(self):
        texto = 'piezas:v1:[Frente, lado ñ,10,20,2\n5,8,3\n,7,9,4'
        piezas = parsear_piezas_desde_texto(texto, estricto=True)
        self.assertEqual([p['nombre'] for p in piezas], ['piezas:v1:[Frente, lado ñ', 'Pieza 2', 'Pieza 3'])
        self.assertEqual([p['cantidad'] for p in piezas], [2, 3, 4])

    def test_prefijo_ambiguo_o_json_incompleto_no_devuelve_resultados_parciales(self):
        from cutless.pieces import FormatoPiezasInvalido

        for texto in ('piezas:v1:[["Puerta",10,20,1],["otra",2]]',
                      'piezas:v1:[["Puerta",10,20,1]\n5,8,3',
                      'piezas:v1:Frente,10,20,2\nsin dimensiones\n5,8,3'):
            with self.subTest(texto=texto):
                with self.assertRaises(FormatoPiezasInvalido):
                    parsear_piezas_desde_texto(texto, estricto=True)
                with self.assertLogs('cutless.pieces', level='WARNING'):
                    self.assertEqual(parsear_piezas_desde_texto(texto), [])

    def test_csv_editable_conserva_nombres_con_prefijos_y_saltos(self):
        from cutless.pieces import piezas_como_csv, serializar_piezas

        original = [
            {'nombre': 'piezas:v1:Puerta', 'ancho': 10, 'alto': 20, 'cantidad': 2},
            {'nombre': 'piezas:v2:Cajón, sur\nNivel 2', 'ancho': 5, 'alto': 8, 'cantidad': 3},
        ]
        csv = piezas_como_csv(serializar_piezas(original))
        piezas = parsear_piezas_desde_texto(csv, estricto=True, csv_editable=True)
        self.assertEqual([{campo: p[campo] for campo in original[0]} for p in piezas], original)
