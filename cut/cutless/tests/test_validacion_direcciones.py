from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cutless.models import Cliente, Optimizacion, Presupuesto


class ValidacionDireccionesTests(TestCase):
    datos_chile = {
        'direccion_pais': 'CL', 'direccion_region': '08', 'direccion_comuna': '08109',
        'direccion_calle': 'Camino a Santa Juana', 'direccion_numero': '100A',
    }
    datos_extranjero = {
        'direccion_pais': 'PT', 'direccion_region': 'Lisboa', 'direccion_comuna': 'São João das Lampas',
        'direccion_calle': 'Rua d’Água', 'direccion_numero': '12-B',
    }

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user('direcciones_cli03')
        cls.usuario.perfil.puede_crear_clientes = True
        cls.usuario.perfil.puede_crear_presupuestos = True
        cls.usuario.perfil.save(update_fields=['puede_crear_clientes', 'puede_crear_presupuestos'])

    def setUp(self):
        self.client.force_login(self.usuario)
        self.alta = reverse('cutless:crear_cliente')

    def probar_error(self, datos, campo, codigo=None, url=None):
        respuesta = self.client.post(url or self.alta, {'nombre': 'Ficha sintética CLI-03', **datos})
        self.assertEqual(respuesta.status_code, 200)
        formulario = respuesta.context['form'].direccion_estructurada
        self.assertTrue(formulario.has_error(campo, codigo), formulario.errors)
        self.assertContains(respuesta, f'id="id_{campo}_error"')
        self.assertContains(respuesta, 'aria-invalid="true"')
        if campo in datos:
            self.assertEqual(formulario[campo].value(), datos[campo])
        return respuesta

    def test_alta_sin_direccion_y_direccion_incompleta(self):
        self.assertEqual(self.client.post(self.alta, {'nombre': 'Sin domicilio'}).status_code, 302)
        self.assertEqual(self.client.post(self.alta, {
            'nombre': 'Sin domicilio con espacios', 'direccion_calle': '   ', 'direccion_numero': '  ',
        }).status_code, 302)
        self.assertTrue(all(not c.direccion_activa and c.direccion_modo is None for c in Cliente.objects.all()))
        respuesta = self.probar_error({'direccion_referencia': 'Junto a la plaza'}, 'direccion_pais')
        direccion = respuesta.context['form'].direccion_estructurada
        for campo in ('direccion_comuna', 'direccion_calle', 'direccion_numero'):
            self.assertTrue(direccion.has_error(campo))
        self.assertEqual(Cliente.objects.count(), 2)

    def test_chile_valida_pais_region_comuna_postal_y_campos_faltantes_en_post(self):
        casos = (
            ('direccion_pais', 'ZZ', 'invalid_choice'),
            ('direccion_region', 'Región del Biobío', None),
            ('direccion_region', '', None),
            ('direccion_comuna', '13101', None),
            ('direccion_comuna', '  ', None),
            ('direccion_calle', '', None),
            ('direccion_numero', '', None),
            ('direccion_codigo_postal', '123456', None),
            ('direccion_codigo_postal', '１２３４５６７', None),
        )
        for campo, valor, codigo in casos:
            with self.subTest(campo=campo, valor=valor):
                self.probar_error({**self.datos_chile, campo: valor}, campo, codigo)
        self.assertFalse(Cliente.objects.exists())
        respuesta = self.client.post(self.alta, {
            'nombre': 'Biobío sintético', **self.datos_chile, 'direccion_codigo_postal': '0001234',
        })
        self.assertEqual(respuesta.status_code, 302)
        cliente = Cliente.objects.get()
        self.assertEqual((cliente.direccion_region, cliente.direccion_comuna),
                         ('Región del Biobío', 'Santa Juana'))
        self.assertEqual((cliente.direccion_numero, cliente.direccion_codigo_postal), ('100A', '0001234'))

    def test_reproduce_cadenas_repetitivas_y_rechaza_textos_sin_contenido(self):
        campos = ('direccion_region', 'direccion_comuna', 'direccion_calle', 'direccion_numero')
        datos = {'direccion_pais': 'PT', **dict.fromkeys(campos, 'aaaaaaaaaa')}
        respuesta = self.probar_error(datos, 'direccion_region', 'repeticion_direccion')
        direccion = respuesta.context['form'].direccion_estructurada
        self.assertTrue(direccion.has_error('direccion_comuna', 'repeticion_direccion'))
        self.assertTrue(direccion.has_error('direccion_calle', 'repeticion_direccion'))
        self.assertTrue(direccion.has_error('direccion_numero', 'numero_direccion'))
        self.assertContains(respuesta, 'Una sola letra repetida no es válida.')
        self.assertContains(respuesta, 'Escribe un número de dirección como 100')
        self.probar_error({**self.datos_chile, 'direccion_calle': 'ÁáÁáÁáÁá'}, 'direccion_calle',
                         'repeticion_direccion')
        self.probar_error({**self.datos_chile, 'direccion_calle': '....'}, 'direccion_calle', 'contenido_direccion')
        self.probar_error({**self.datos_extranjero, 'direccion_comuna': '1234'}, 'direccion_comuna',
                         'contenido_direccion')
        self.assertFalse(Cliente.objects.exists())

    def test_controles_y_numeros_invalidos_en_todos_los_campos_de_texto(self):
        for campo in ('direccion_region', 'direccion_comuna', 'direccion_calle', 'direccion_numero',
                      'direccion_unidad', 'direccion_referencia', 'direccion_codigo_postal'):
            with self.subTest(campo=campo):
                self.probar_error({**self.datos_extranjero, campo: 'Dato\nprueba'}, campo, 'control_direccion')
        self.probar_error({**self.datos_extranjero, 'direccion_calle': 'Rua\u2028Nova'}, 'direccion_calle',
                         'control_direccion')
        self.probar_error({**self.datos_extranjero, 'direccion_calle': 'Rua\u202eNova'}, 'direccion_calle',
                         'control_direccion')
        for numero in ('hola', 'NN', '12-hola', 'ABC12', '///', 'N/A'):
            with self.subTest(numero=numero):
                self.probar_error({**self.datos_extranjero, 'direccion_numero': numero}, 'direccion_numero',
                                 'numero_direccion')
        self.assertFalse(Cliente.objects.exists())

    def test_formatos_internacionales_sin_falsos_positivos(self):
        casos = (
            ('FR', 'Hauts-de-France', 'Y', 'Rue de l’Église', '12 bis'),
            ('FR', 'Île-de-France', 'L’Haÿ-les-Roses', 'Allée du Parc', '12–14'),
            ('JP', '東京都', '千代田区', '丸の内', '１－２'),
            ('QA', '', 'الدوحة', 'شارع السوق', '١٠٠ب'),
            ('IR', '', 'تهران', 'خیابان ولی‌عصر', '۱۰۰'),
            ('IN', 'ಕರ್ನಾಟಕ', 'ಬೆಂಗಳೂರು', 'ಮಲ್ಲೇಶ್ವರಂ 10ನೇ ರಸ್ತೆ', 'A-12'),
            ('ZA', 'Northern Cape', '!Kheis', 'R64', 'S/N'),
            ('NZ', 'Waikato', 'Tāupo', 'Avenue 5', '2/15'),
            ('PT', 'Lisboa', 'São João das Lampas', 'Rua d’Água', '100'),
            ('CO', 'Cundinamarca', 'Bogotá', '25', '0012-B'),
            ('CL', '08', '08109', 'Calle 3', 's / n'),
        )
        for indice, (pais, region, ciudad, calle, numero) in enumerate(casos):
            with self.subTest(pais=pais, ciudad=ciudad, numero=numero):
                nombre = f'Sintético {indice}'
                respuesta = self.client.post(self.alta, {
                    'nombre': nombre, 'direccion_pais': pais, 'direccion_region': region,
                    'direccion_comuna': ciudad, 'direccion_calle': calle, 'direccion_numero': numero,
                })
                self.assertEqual(respuesta.status_code, 302)
                cliente = Cliente.objects.get(nombre=nombre)
                self.assertEqual((cliente.direccion_calle, cliente.direccion_numero), (calle, numero))
                if pais != 'CL':
                    self.assertEqual((cliente.direccion_region, cliente.direccion_localidad), (region or None, ciudad))

    def test_estructurada_historica_invalida_se_conserva_literal_al_editar_contacto(self):
        cliente = Cliente.objects.create(
            usuario=self.usuario, nombre='Ficha histórica', direccion_modo='estructurada', direccion_pais='ZZ',
            direccion_region='AAaaaAAAAA', direccion_localidad='Lugar histórico',
            direccion_calle='  Texto\r\n guardado  ', direccion_numero='aaaaaaaaaa',
            direccion_codigo_postal='  texto  ', direccion_referencia='  No modificar  ',
        )
        editar = reverse('cutless:editar_cliente', args=[cliente.pk])
        pagina = self.client.get(editar)
        self.assertContains(pagina, 'ZZ (guardado anteriormente)')
        direccion = pagina.context['form'].direccion_estructurada
        datos_visibles = {campo.name: campo.value().replace('\r', '').replace('\n', '') for campo in direccion}
        antes = Cliente.objects.values().get(pk=cliente.pk)
        for datos in ({}, datos_visibles):
            with self.subTest(datos=datos):
                self.assertEqual(self.client.post(editar, {
                    **datos, 'email': 'otro@example.test', 'telefono': '9 8765 4321', 'telefono_pais': 'CL',
                }).status_code, 302)
                despues = Cliente.objects.values().get(pk=cliente.pk)
                self.assertEqual((despues['email'], despues['telefono']), ('otro@example.test', '+56987654321'))
                self.assertEqual({k: v for k, v in despues.items() if k.startswith('direccion')},
                                 {k: v for k, v in antes.items() if k.startswith('direccion')})
        # La opción del país se muestra para conservar el dato, pero no habilita modificarlo con un país inválido.
        self.probar_error({**datos_visibles, 'direccion_numero': '22'}, 'direccion_pais', 'invalid_choice', editar)
        cliente.refresh_from_db()
        self.assertEqual(cliente.direccion_numero, antes['direccion_numero'])

    def test_modificar_direccion_exige_contrato_completo_y_preserva_presupuesto_emitido(self):
        cliente = Cliente.objects.create(
            usuario=self.usuario, nombre='Histórica emitida', direccion='  Texto legado\r\n  ',
            direccion_modo='estructurada', direccion_pais='PT', direccion_region='aaaaaaaaaa',
            direccion_localidad='Cidade histórica', direccion_calle='Rua de teste', direccion_numero='borrar',
        )
        plan = Optimizacion.objects.create(usuario=self.usuario, cliente=cliente, ancho_tablero=122,
                                           alto_tablero=244, piezas='Puerta,40,50,1', num_tableros=1)
        respuesta = self.client.post(reverse('cutless:crear_presupuesto'), {
            'cliente': cliente.pk, 'optimizaciones': [plan.pk], 'precio_tablero': '200', 'mano_obra': '0',
            'fecha_validez': timezone.localdate() + timedelta(days=1), 'accion': 'emitir',
        })
        self.assertEqual(respuesta.status_code, 302)
        presupuesto = Presupuesto.objects.get()
        detalle = presupuesto.detalle_emitido
        self.assertEqual(detalle['cliente']['direccion'], cliente.direccion_activa)
        editar = reverse('cutless:editar_cliente', args=[cliente.pk])
        antes = Cliente.objects.values().get(pk=cliente.pk)
        self.probar_error({'direccion_numero': '100', 'email': 'rechazado@example.test'}, 'direccion_region',
                         'repeticion_direccion', editar)
        self.assertEqual(Cliente.objects.values().get(pk=cliente.pk), antes)
        self.assertEqual(self.client.post(editar, {**self.datos_extranjero, 'email': 'nuevo@example.test'}).status_code, 302)
        cliente.refresh_from_db()
        presupuesto.refresh_from_db()
        self.assertEqual((cliente.direccion, cliente.email), (antes['direccion'], 'nuevo@example.test'))
        self.assertEqual(presupuesto.cliente_id, cliente.pk)
        self.assertEqual(presupuesto.detalle_emitido, detalle)

    def test_texto_chileno_historico_y_sus_codigos_son_equivalentes_para_conservar(self):
        guardada = {
            **self.datos_chile, 'direccion_region': 'Región del Bío-Bío', 'direccion_comuna': 'Santa Juana',
            'direccion_numero': 'aaaaaaaaaa',
        }
        cliente = Cliente.objects.create(usuario=self.usuario, nombre='Histórica chilena',
                                         direccion_modo='estructurada', **guardada)
        editar = reverse('cutless:editar_cliente', args=[cliente.pk])
        pantalla = {**self.datos_chile, 'direccion_numero': guardada['direccion_numero']}
        for datos in (guardada, pantalla):
            with self.subTest(region=datos['direccion_region']):
                self.assertEqual(self.client.post(editar, {
                    **datos, 'notas': 'La dirección queda literal.',
                }).status_code, 302)
                cliente.refresh_from_db()
                self.assertEqual({campo: getattr(cliente, campo) for campo in guardada}, guardada)
        self.probar_error({**pantalla, 'direccion_calle': 'Calle nueva'}, 'direccion_numero',
                         'numero_direccion', editar)

    def test_post_ajeno_y_sin_permiso_no_guardan_direccion_ni_contacto(self):
        ajeno = User.objects.create_user('direcciones_cli03_ajeno')
        cliente = Cliente.objects.create(usuario=ajeno, nombre='De otro propietario', direccion='Legado')
        antes = Cliente.objects.values().get(pk=cliente.pk)
        editar = reverse('cutless:editar_cliente', args=[cliente.pk])
        datos = {'nombre': cliente.nombre, 'email': 'ajeno@example.test', **self.datos_extranjero}
        self.assertRedirects(self.client.post(editar, datos), reverse('cutless:lista_clientes'), fetch_redirect_response=False)
        self.usuario.perfil.puede_crear_clientes = False
        self.usuario.perfil.save(update_fields=['puede_crear_clientes'])
        self.assertRedirects(self.client.post(self.alta, datos), reverse('cutless:index'), fetch_redirect_response=False)
        self.assertEqual(Cliente.objects.count(), 1)
        self.assertEqual(Cliente.objects.values().get(pk=cliente.pk), antes)
