from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import close_old_connections
from django.test import Client, SimpleTestCase, TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from reportlab import rl_config

from cutless.forms import ClienteForm
from cutless.models import Cliente, Optimizacion, Presupuesto, Proyecto


class ContactoClienteFormTests(SimpleTestCase):
    def formulario(self, **campos):
        return ClienteForm({'nombre': 'Cliente sintético', **campos})

    def test_chile_por_defecto_y_campo_telefonico(self):
        formulario = ClienteForm()
        self.assertEqual(formulario['telefono_pais'].value(), 'CL')
        self.assertIn('Chile (+56)', formulario['telefono_pais'].as_widget())
        self.assertIn('type="tel"', formulario['telefono'].as_widget())
        self.assertIn('inputmode="tel"', formulario['telefono'].as_widget())

    def test_telefonos_movil_y_fijo_chilenos(self):
        for entrada, esperado in (
            ('9 8765 4321', '+56987654321'),
            ('(2) 2345-6789', '+56223456789'),
            ('+56\u202f9.8765.4321', '+56987654321'),
        ):
            with self.subTest(entrada=entrada):
                formulario = self.formulario(telefono=entrada, telefono_pais='CL')
                self.assertTrue(formulario.is_valid(), formulario.errors)
                self.assertEqual(formulario.cleaned_data['telefono'], esperado)

    def test_telefono_extranjero_nacional_o_prefijo_explicito(self):
        for pais, entrada, esperado in (
            ('GB', '0121 234 5678', '+441212345678'),
            ('CL', '+44 (121) 234 5678', '+441212345678'),
            ('US', '(201) 555-0123', '+12015550123'),
        ):
            with self.subTest(pais=pais, entrada=entrada):
                formulario = self.formulario(telefono=entrada, telefono_pais=pais)
                self.assertTrue(formulario.is_valid(), formulario.errors)
                self.assertEqual(formulario.cleaned_data['telefono'], esperado)

    def test_rechaza_letras_extensiones_y_caracteres_ajenos(self):
        valores = ('9 ABCD 4321', '9 8765 4321 x123', '9 8765 4321#123', '9/8765/4321',
                   '9 8765 4321;ext=123', '++56987654321', '9\t87654321')
        for entrada in valores:
            with self.subTest(entrada=entrada):
                formulario = self.formulario(telefono=entrada)
                self.assertTrue(formulario.has_error('telefono', 'formato'), formulario.errors)
                self.assertEqual(formulario['telefono'].value(), entrada)

    def test_rechaza_largo_prefijos_incorrectos_y_region_invalida(self):
        for pais, entrada in (('CL', '9' * 20), ('CL', '+999987654321'), ('CL', '+56'),
                              ('CL', '0121 234 5678'), ('CA', '(201) 555-0123')):
            with self.subTest(pais=pais, entrada=entrada):
                formulario = self.formulario(telefono=entrada, telefono_pais=pais)
                self.assertTrue(formulario.has_error('telefono', 'telefono_invalido'), formulario.errors)
        formulario = self.formulario(telefono='9' * 65)
        self.assertTrue(formulario.has_error('telefono', 'max_length'), formulario.errors)
        formulario = self.formulario(telefono='+56987654321', telefono_pais='XX')
        self.assertTrue(formulario.has_error('telefono_pais', 'invalid_choice'), formulario.errors)

    def test_rut_acepta_normalizacion_y_verificadores_numericos_o_k(self):
        for valor, esperado in (('12.345.678-5', '12345678-5'), ('123456785', '12345678-5'),
                                (' 1.000.005-k ', '1000005-K'), ('3-5', '3-5'), ('14-0', '14-0')):
            with self.subTest(valor=valor):
                formulario = self.formulario(rut=valor)
                self.assertTrue(formulario.is_valid(), formulario.errors)
                self.assertEqual(formulario.cleaned_data['rut'], esperado)

    def test_rut_rechaza_verificador_y_formato_incorrectos(self):
        for valor in ('12.345.678-9', '1.000.005-0', '12345678-K'):
            with self.subTest(valor=valor):
                formulario = self.formulario(rut=valor)
                self.assertTrue(formulario.has_error('rut', 'digito_verificador'), formulario.errors)
        for valor in ('0-0', 'RUT extranjero', '12..345.678-5', '123--4', '123.456.789-0'):
            with self.subTest(valor=valor):
                formulario = self.formulario(rut=valor)
                self.assertTrue(formulario.has_error('rut', 'formato'), formulario.errors)

    def test_campos_de_contacto_opcionales(self):
        formulario = self.formulario(telefono='', rut='', telefono_pais='ES')
        self.assertTrue(formulario.is_valid(), formulario.errors)
        self.assertEqual(formulario.cleaned_data['rut'], '')
        self.assertEqual(formulario.cleaned_data['telefono'], '')


class ContactoClienteVistasTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user('contacto-auditoria')
        self.usuario.perfil.rol = 'admin'
        self.usuario.perfil.save()
        self.client.force_login(self.usuario)
        self.alta = reverse('cutless:crear_cliente')
        self.cliente = Cliente.objects.create(usuario=self.usuario, nombre='Cliente histórico',
                                              telefono='Tel de prueba', rut='FISCAL-ANTERIOR')
        self.edicion = reverse('cutless:editar_cliente', args=[self.cliente.pk])

    def test_alta_guarda_datos_normalizados_y_permite_buscar(self):
        respuesta = self.client.post(self.alta, {'nombre': 'Cliente nuevo', 'telefono_pais': 'GB',
                                                 'telefono': '0121 234 5678', 'rut': '12.345.678-5'})
        self.assertEqual(respuesta.status_code, 302)
        nuevo = Cliente.objects.get(usuario=self.usuario, nombre='Cliente nuevo')
        self.assertEqual((nuevo.telefono, nuevo.rut), ('+441212345678', '12345678-5'))
        ficha = self.client.get(reverse('cutless:editar_cliente', args=[nuevo.pk]))
        self.assertEqual(ficha.context['form']['telefono_pais'].value(), 'GB')
        listado = self.client.get(reverse('cutless:lista_clientes'), {'busqueda': '12345678-5'})
        self.assertEqual(list(listado.context['clientes']), [nuevo])
        self.assertContains(listado, nuevo.telefono)

    def test_rechaza_rut_repetido_en_sus_grafias_y_conserva_borrador(self):
        casos = (
            ('12345678-5', '12.345.678-5'),
            ('1.000.005-k', '1000005-K'),
            ('  00000014-0  ', '14-0'),
        )
        for indice, (guardado, entrada) in enumerate(casos):
            with self.subTest(indice=indice):
                Cliente.objects.create(usuario=self.usuario, rut=guardado, nombre=f'Histórico {indice}')
                respuesta = self.client.post(self.alta, {
                    'nombre': 'Borrador', 'rut': entrada, 'email': 'borrador@example.test',
                    'direccion_pais': 'CL', 'direccion_region': '08', 'direccion_comuna': '08109',
                    'direccion_calle': 'Calle sintética', 'direccion_numero': 'S/N',
                })
                form = respuesta.context['form']
                self.assertTrue(form.has_error('rut', 'duplicado'))
                self.assertEqual((form['rut'].value(), form['email'].value()), (entrada, 'borrador@example.test'))
                self.assertEqual(form.direccion_estructurada['direccion_comuna'].value(), '08109')
                self.assertContains(respuesta, 'Ya tienes un cliente registrado con este RUT.')
                self.assertContains(respuesta, 'aria-describedby="id_rut_helptext id_rut_error"')
                self.assertFalse(Cliente.objects.filter(usuario=self.usuario, nombre='Borrador').exists())

    def test_mismo_rut_en_cuentas_distintas_y_varios_rut_vacios(self):
        otro = User.objects.create_user('rut-otra-cuenta')
        otro.perfil.puede_crear_clientes = True
        otro.perfil.save(update_fields=['puede_crear_clientes'])
        self.assertEqual(self.client.post(self.alta, {'nombre': 'Primer RUT', 'rut': '1.000.005-k'}).status_code, 302)
        self.client.force_login(otro)
        for nombre, rut in (('Mismo RUT', '1000005-K'), ('Vacío A', ''), ('Vacío B', '')):
            self.assertEqual(self.client.post(self.alta, {'nombre': nombre, 'rut': rut}).status_code, 302)
        self.assertEqual(Cliente.objects.filter(rut='1000005-K').count(), 2)
        self.assertEqual(Cliente.objects.filter(usuario=otro, rut='').count(), 2)

    def test_edicion_excluye_ficha_actual_y_respeta_duplicados_historicos_intactos(self):
        self.cliente.rut = '12.345.678-5'
        self.cliente.save(update_fields=['rut'])
        self.assertEqual(self.client.post(self.edicion, {'nombre': self.cliente.nombre, 'rut': '12345678-5'}).status_code,
                         302)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.rut, '12345678-5')
        repetido = Cliente.objects.create(usuario=self.usuario, nombre='Duplicado histórico', rut='12.345.678-5')
        self.assertEqual(self.client.post(self.edicion, {
            'nombre': self.cliente.nombre, 'rut': '12345678-5', 'notas': 'Nota permitida',
        }).status_code, 302)
        self.cliente.refresh_from_db()
        repetido.refresh_from_db()
        self.assertEqual((self.cliente.rut, self.cliente.notas, repetido.rut),
                         ('12345678-5', 'Nota permitida', '12.345.678-5'))
        respuesta = self.client.post(self.edicion, {'nombre': self.cliente.nombre, 'rut': '12.345.678-5'})
        self.assertTrue(respuesta.context['form'].has_error('rut', 'duplicado'))

    def test_editar_otros_datos_conserva_identificadores_historicos(self):
        respuesta = self.client.post(self.edicion, {'nombre': 'Otro nombre', 'telefono_pais': 'CL',
                                                    'telefono': 'Tel de prueba', 'rut': 'FISCAL-ANTERIOR'})
        self.assertEqual(respuesta.status_code, 302)
        self.cliente.refresh_from_db()
        self.assertEqual((self.cliente.nombre, self.cliente.telefono, self.cliente.rut),
                         ('Otro nombre', 'Tel de prueba', 'FISCAL-ANTERIOR'))
        self.assertEqual(self.client.post(self.edicion, {'nombre': 'Tercer nombre'}).status_code, 302)
        self.cliente.refresh_from_db()
        self.assertEqual((self.cliente.telefono, self.cliente.rut), ('Tel de prueba', 'FISCAL-ANTERIOR'))
        listado = self.client.get(reverse('cutless:lista_clientes'), {'busqueda': 'fiscal-anterior'})
        self.assertEqual(list(listado.context['clientes']), [self.cliente])

    def test_edicion_no_normaliza_datos_historicos_validos_si_siguen_iguales(self):
        self.cliente.telefono, self.cliente.rut = '(2) 2345-6789', '12.345.678-5'
        self.cliente.save(update_fields=['telefono', 'rut'])
        datos = {'nombre': self.cliente.nombre, 'telefono_pais': 'CL', 'telefono': self.cliente.telefono,
                 'rut': self.cliente.rut, 'direccion': 'Dirección sintética'}
        self.assertEqual(self.client.post(self.edicion, datos).status_code, 302)
        self.cliente.refresh_from_db()
        self.assertEqual((self.cliente.telefono, self.cliente.rut), ('(2) 2345-6789', '12.345.678-5'))

    def test_error_de_edicion_conserva_valores_en_formulario_y_bd(self):
        entrada = {'nombre': 'Nombre sin guardar', 'telefono_pais': 'GB', 'telefono': 'llamar luego',
                   'rut': '12.345.678-9', 'notas': 'Borrador de notas'}
        respuesta = self.client.post(self.edicion, entrada)
        self.assertEqual(respuesta.status_code, 200)
        formulario = respuesta.context['form']
        self.assertTrue(formulario.has_error('telefono', 'formato'))
        self.assertTrue(formulario.has_error('rut', 'digito_verificador'))
        for campo, valor in entrada.items():
            self.assertEqual(formulario[campo].value(), valor)
        self.assertContains(respuesta, 'aria-describedby="id_telefono_helptext id_telefono_error"')
        self.assertContains(respuesta, 'id="id_telefono_error"')
        self.cliente.refresh_from_db()
        self.assertEqual((self.cliente.nombre, self.cliente.telefono, self.cliente.rut),
                         ('Cliente histórico', 'Tel de prueba', 'FISCAL-ANTERIOR'))

    def test_reemplazar_y_luego_borrar_los_datos_opcionales(self):
        base = {'nombre': self.cliente.nombre, 'telefono_pais': 'CL'}
        respuesta = self.client.post(self.edicion, {**base, 'telefono': '9 8765 4321', 'rut': '1000005-k'})
        self.assertEqual(respuesta.status_code, 302)
        self.cliente.refresh_from_db()
        self.assertEqual((self.cliente.telefono, self.cliente.rut), ('+56987654321', '1000005-K'))
        respuesta = self.client.post(self.edicion, {**base, 'telefono': '', 'rut': ''})
        self.assertEqual(respuesta.status_code, 302)
        self.cliente.refresh_from_db()
        self.assertEqual((self.cliente.telefono, self.cliente.rut), ('', ''))

    def test_edicion_requiere_propietario(self):
        ajeno = User.objects.create_user('contacto-ajeno')
        ajeno.perfil.rol = 'admin'
        ajeno.perfil.save()
        self.client.force_login(ajeno)
        for respuesta in (self.client.get(self.edicion), self.client.post(self.edicion, {'nombre': 'Ajeno'})):
            self.assertRedirects(respuesta, reverse('cutless:lista_clientes'), fetch_redirect_response=False)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.nombre, 'Cliente histórico')

    def test_asociaciones_y_pdf_conservan_instantanea_tras_editar_contacto(self):
        proyecto = Proyecto.objects.create(usuario=self.usuario, cliente=self.cliente, nombre='Proyecto de prueba')
        plan = Optimizacion.objects.create(usuario=self.usuario, cliente=self.cliente, proyecto=proyecto,
                                           ancho_tablero=122, alto_tablero=244, piezas='Pieza,20,30,1', num_tableros=1)
        entrada = {'cliente': self.cliente.pk, 'proyecto': proyecto.pk, 'optimizaciones': [plan.pk],
                   'precio_tablero': '100', 'mano_obra': '0', 'fecha_validez': date.today().isoformat()}
        crear_presupuesto = reverse('cutless:crear_presupuesto')
        self.assertEqual(self.client.post(crear_presupuesto, {**entrada, 'estado': 'enviado'}).status_code, 302)
        emitido = Presupuesto.objects.get(usuario=self.usuario, estado='enviado')
        instantanea = emitido.detalle_emitido
        self.assertEqual(instantanea['cliente']['telefono'], 'Tel de prueba')
        self.assertEqual(instantanea['cliente']['rut'], 'FISCAL-ANTERIOR')

        Cliente.objects.create(usuario=self.usuario, nombre='Otra ficha con RUT', rut='1000005-K')
        respuesta = self.client.post(self.edicion, {
            'nombre': 'Cambio inválido', 'rut': '1.000.005-k', 'email': 'sin-guardar@example.test',
            'direccion_pais': 'CL', 'direccion_region': '08', 'direccion_comuna': '08109',
            'direccion_calle': 'Calle sintética', 'direccion_numero': '12-B',
        })
        self.assertTrue(respuesta.context['form'].has_error('rut', 'duplicado'))
        self.cliente.refresh_from_db()
        self.assertEqual((self.cliente.rut, self.cliente.nombre, self.cliente.email, self.cliente.direccion_modo),
                         ('FISCAL-ANTERIOR', 'Cliente histórico', '', None))

        respuesta = self.client.post(self.edicion, {'nombre': self.cliente.nombre, 'telefono': '9 8765 4321',
                                                    'rut': '12.345.678-5'})
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(self.client.post(crear_presupuesto, {**entrada, 'estado': 'borrador'}).status_code, 302)
        borrador = Presupuesto.objects.get(usuario=self.usuario, estado='borrador')
        for registro in (proyecto, plan, emitido, borrador):
            registro.refresh_from_db()
            self.assertEqual(registro.cliente_id, self.cliente.pk)
        self.assertEqual(plan.proyecto_id, proyecto.pk)
        self.assertEqual(list(emitido.optimizaciones.all()), [plan])
        self.assertEqual(list(borrador.optimizaciones.all()), [plan])
        self.assertEqual(emitido.detalle_emitido, instantanea)
        with patch.object(rl_config, 'pageCompression', 0):
            for presupuesto, telefono, rut in ((emitido, b'Tel de prueba', b'FISCAL-ANTERIOR'),
                                                (borrador, b'+56987654321', b'12345678-5')):
                respuesta = self.client.get(reverse('cutless:generar_pdf_presupuesto', args=[presupuesto.pk]))
                self.assertEqual(respuesta['Content-Type'], 'application/pdf')
                pdf = b''.join(respuesta.streaming_content)
                self.assertIn(telefono, pdf)
                self.assertIn(rut, pdf)


@skipUnlessDBFeature('has_select_for_update')
class RutClientesConcurrentesTests(TransactionTestCase):
    def setUp(self):
        self.usuario = User.objects.create_user('rut-concurrencia')
        self.usuario.perfil.puede_crear_clientes = True
        self.usuario.perfil.save(update_fields=['puede_crear_clientes'])
        self.alta = reverse('cutless:crear_cliente')

    def comprobar_competencia(self, solicitudes):
        sesiones = [Client(), Client()]
        for sesion in sesiones:
            sesion.force_login(self.usuario)
        inicio = Barrier(2, timeout=10)

        def enviar(solicitud):
            sesion, (ruta, datos) = solicitud
            close_old_connections()
            try:
                inicio.wait()
                respuesta = sesion.post(ruta, datos)
                if respuesta.status_code == 200:
                    self.assertTrue(respuesta.context['form'].has_error('rut', 'duplicado'))
                return respuesta.status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as equipo:
            estados = list(equipo.map(enviar, zip(sesiones, solicitudes)))
        self.assertCountEqual(estados, [200, 302])
        self.assertEqual(Cliente.objects.filter(usuario=self.usuario, rut='1000005-K').count(), 1)

    def test_dos_altas_simultaneas_para_el_mismo_rut(self):
        self.comprobar_competencia([
            (self.alta, {'nombre': 'Alta A', 'rut': '1000005-K'}),
            (self.alta, {'nombre': 'Alta B', 'rut': '1.000.005-k'}),
        ])
        self.assertEqual(Cliente.objects.filter(usuario=self.usuario).count(), 1)

    def test_alta_y_edicion_simultaneas_para_el_mismo_rut(self):
        ficha = Cliente.objects.create(usuario=self.usuario, nombre='Ficha previa')
        self.comprobar_competencia([
            (self.alta, {'nombre': 'Alta simultánea', 'rut': '1000005-K'}),
            (reverse('cutless:editar_cliente', args=[ficha.pk]), {'nombre': ficha.nombre, 'rut': '1.000.005-k'}),
        ])
        self.assertTrue(Cliente.objects.filter(pk=ficha.pk).exists())
