from datetime import date, timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.db import DatabaseError, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from reportlab import rl_config

from cutless.direcciones import DPA_CHILE
from cutless.models import Cliente, Optimizacion, Presupuesto, Proyecto
from usuarios.models import PerfilUsuario


LEGADO = '  Pasaje legado 12-B\r\nUnidad S/N\n  Referencia <original>  '
ESTRUCTURADA = {
    'direccion_pais': 'CL',
    'direccion_calle': 'Avenida de prueba',
    'direccion_numero': 'S/N',
    'direccion_unidad': 'Unidad 4B',
    'direccion_region': '08',
    'direccion_comuna': '08109',
    'direccion_referencia': 'Referencia interna',
}


class DireccionesClientesTests(TestCase):
    def setUp(self):
        self.propietario = User.objects.create_user('direccion_propietario')
        self.propietario.perfil.puede_crear_clientes = True
        self.propietario.perfil.puede_crear_presupuestos = True
        self.propietario.perfil.save(update_fields=['puede_crear_clientes', 'puede_crear_presupuestos'])
        self.client.force_login(self.propietario)
        self.ficha = Cliente.objects.create(
            usuario=self.propietario, nombre='Ficha histórica sintética', direccion=LEGADO,
            telefono='Contacto legado', rut='FISCAL-HISTORICO', notas='Texto anterior',
        )
        self.alta = reverse('cutless:crear_cliente')
        self.edicion = reverse('cutless:editar_cliente', args=[self.ficha.pk])
        self.historial = reverse('cutless:historial_cliente', args=[self.ficha.pk])

    def editar(self, **datos):
        return self.client.post(self.edicion, {'nombre': self.ficha.nombre, **datos})

    def cerrar_direccion(self):
        respuesta = self.editar(**ESTRUCTURADA)
        self.assertEqual(respuesta.status_code, 302)
        self.ficha.refresh_from_db()

    def pdf(self, presupuesto):
        ruta = reverse('cutless:generar_pdf_presupuesto', args=[presupuesto.pk])
        with patch.object(rl_config, 'pageCompression', 0):
            respuesta = self.client.get(ruta)
            self.assertEqual((respuesta.status_code, respuesta['Content-Type']), (200, 'application/pdf'))
            return b''.join(respuesta.streaming_content)

    def asociar(self):
        proyecto = Proyecto.objects.create(usuario=self.propietario, cliente=self.ficha, nombre='Proyecto sintético')
        plan = Optimizacion.objects.create(
            usuario=self.propietario, cliente=self.ficha, proyecto=proyecto, ancho_tablero=122,
            alto_tablero=244, piezas='Pieza,20,30,1', num_tableros=1,
        )
        return proyecto, plan

    def cotizar(self, proyecto, plan, estado='borrador'):
        respuesta = self.client.post(reverse('cutless:crear_presupuesto'), {
            'cliente': self.ficha.pk, 'proyecto': proyecto.pk, 'optimizaciones': [plan.pk],
            'precio_tablero': '1500.50', 'mano_obra': '43.20',
            'fecha_validez': (timezone.localdate() + timedelta(days=1)).isoformat(),
            **({'accion': 'emitir'} if estado == 'enviado' else {}),
        })
        self.assertEqual(respuesta.status_code, 302)
        return Presupuesto.objects.filter(usuario=self.propietario).latest('pk')

    def test_alta_estructurada_opcional_y_numero_como_texto(self):
        for indice, numero in enumerate(('S/N', '0012-B')):
            nombre = f'Cliente de prueba {indice}'
            self.assertEqual(self.client.post(self.alta, {
                'nombre': nombre, **ESTRUCTURADA, 'direccion_numero': numero,
            }).status_code, 302)
            guardado = Cliente.objects.get(nombre=nombre)
            self.assertEqual((guardado.direccion_modo, guardado.direccion, guardado.direccion_numero),
                             ('estructurada', '', numero))
            self.assertEqual(guardado.direccion_activa,
                             f'Avenida de prueba {numero}, Unidad 4B\nSanta Juana, Región del Biobío\nChile')
            self.assertEqual(guardado.direccion_referencia, 'Referencia interna')

        self.assertEqual(self.client.post(self.alta, {'nombre': 'Sin dirección'}).status_code, 302)
        vacio = Cliente.objects.get(nombre='Sin dirección')
        self.assertEqual((vacio.direccion_activa, vacio.direccion_modo, vacio.direccion_pais), ('', None, None))

    def test_direccion_internacional_y_escape_en_interfaz(self):
        self.assertEqual(self.editar(
            direccion_pais='JP', direccion_calle='通り <literal>',
            direccion_comuna='Ciudad de prueba', direccion_unidad='Árvore', direccion_numero='8-A',
        ).status_code, 302)
        self.ficha.refresh_from_db()
        self.assertIsNone(self.ficha.direccion_region)
        self.assertIsNone(self.ficha.direccion_comuna)
        self.assertEqual(self.ficha.direccion_activa, '通り <literal> 8-A, Árvore\nCiudad de prueba\nJapón')
        res = self.client.get(self.historial)
        self.assertContains(res, '通り &lt;literal&gt;')
        self.assertNotContains(res, '通り <literal>')

    def test_legado_exige_direccion_antes_de_guardar_y_conserva_contacto(self):
        antes = Cliente.objects.filter(pk=self.ficha.pk).values().get()
        res = self.client.get(self.edicion)
        self.assertContains(res, 'data-mostrar-aviso')
        self.assertContains(res, 'Referencia &lt;original&gt;')
        self.assertContains(res, 'Volver al listado')
        self.assertNotContains(res, 'direccion_accion')
        self.assertEqual(self.client.get(reverse('cutless:lista_clientes')).status_code, 200)
        res = self.editar(email='correo@example.test', direccion_legada='Intento de sustituir el original')
        self.assertContains(res, 'Actualiza la dirección histórica para guardar')
        self.assertContains(res, 'correo@example.test')
        self.assertNotContains(res, 'data-mostrar-aviso')
        self.assertEqual(Cliente.objects.filter(pk=self.ficha.pk).values().get(), antes)

        self.assertEqual(self.editar(email='correo@example.test', **ESTRUCTURADA).status_code, 302)
        self.ficha.refresh_from_db()
        self.assertEqual((self.ficha.direccion, self.ficha.direccion_modo, self.ficha.email, self.ficha.rut,
                          self.ficha.telefono, self.ficha.notas, self.ficha.fecha_creacion),
                         (LEGADO, 'estructurada', 'correo@example.test', 'FISCAL-HISTORICO',
                          'Contacto legado', 'Texto anterior', antes['fecha_creacion']))
        self.assertNotContains(self.client.get(self.edicion), 'Referencia &lt;original&gt;')

        self.assertEqual(self.editar(telefono_pais='CL', telefono='9 8765 4321').status_code, 302)
        self.ficha.refresh_from_db()
        self.assertEqual((self.ficha.direccion, self.ficha.telefono), (LEGADO, '+56987654321'))

    def test_compatibilidad_cli01_y_cliente_sin_direccion(self):
        Cliente.objects.filter(pk=self.ficha.pk).update(
            direccion_modo='estructurada', direccion_pais='CL', direccion_region='Región del Bío-Bío',
            direccion_comuna='Santa Juana', direccion_localidad='Sector sintético', direccion_calle='Pasaje',
        )
        pagina = self.client.get(self.edicion)
        self.assertNotContains(pagina, 'data-aviso-direccion')
        campos = pagina.context['form'].direccion_estructurada
        self.assertEqual((campos['direccion_region'].value(), campos['direccion_comuna'].value()), ('08', '08109'))
        self.assertEqual(self.editar(email='segundo@example.test').status_code, 302)
        self.ficha.refresh_from_db()
        self.assertEqual((self.ficha.direccion_region, self.ficha.direccion_localidad),
                         ('Región del Bío-Bío', 'Sector sintético'))
        self.assertEqual(self.editar(direccion_numero='12-B', direccion_codigo_postal='0001234').status_code, 302)
        self.ficha.refresh_from_db()
        self.assertEqual(self.ficha.direccion_localidad, 'Sector sintético')

        sin_direccion = Cliente.objects.create(usuario=self.propietario, nombre='Ficha sin dirección')
        editar = reverse('cutless:editar_cliente', args=[sin_direccion.pk])
        self.assertNotContains(self.client.get(editar), 'data-aviso-direccion')
        self.assertEqual(self.client.post(editar, {'nombre': sin_direccion.nombre}).status_code, 302)

    def test_catalogo_y_refresco_de_ubicacion_sin_escritura(self):
        self.assertEqual(len(DPA_CHILE), 16)
        comunas = [codigo for region in DPA_CHILE.values() for codigo in region['comunas']]
        self.assertEqual(len(comunas), 346)
        self.assertEqual(len(set(comunas)), 346)
        for codigo, region in DPA_CHILE.items():
            self.assertTrue(all(comuna.startswith(codigo) for comuna in region['comunas']))
        res = self.editar(actualizar_ubicacion='1', ubicacion_pais='CL', direccion_pais='CL',
                          direccion_region='08', direccion_calle='Dato retenido', email='borrador@example.test')
        self.assertContains(res, 'Santa Juana')
        campo = res.context['form'].direccion_estructurada
        self.assertIn(('08109', 'Santa Juana'), campo.fields['direccion_comuna'].widget.choices)
        self.assertNotIn('13101', dict(campo.fields['direccion_comuna'].widget.choices))
        self.assertEqual(campo['direccion_calle'].value(), 'Dato retenido')
        self.assertEqual(res.context['form']['email'].value(), 'borrador@example.test')
        self.assertFalse(res.context['form'].is_bound)
        self.ficha.refresh_from_db()
        self.assertEqual((self.ficha.email, self.ficha.direccion), ('', LEGADO))

        res = self.editar(**{**ESTRUCTURADA, 'direccion_region': '13'})
        self.assertContains(res, 'Selecciona una comuna de la región elegida.')
        res = self.editar(**ESTRUCTURADA, direccion_codigo_postal='1234')
        self.assertContains(res, 'El código postal chileno debe tener siete dígitos.')
        res = self.editar(ubicacion_pais='CL', direccion_pais='PT', direccion_region='08',
                          direccion_comuna='08109', direccion_calle='Rua de teste', direccion_numero='7')
        self.assertContains(res, 'Confirma la ubicación para el país seleccionado.')

    def test_extranjero_sin_division_chilena_y_validacion_sin_escrituras(self):
        antes = Cliente.objects.filter(pk=self.ficha.pk).values().get()
        entradas_invalidas = [
            (dict(direccion_calle='A' * 161), 'direccion_calle'),
            (dict(direccion_calle='Calle con\ncorte'), 'direccion_calle'),
            (dict(direccion_pais='ZZ', direccion_calle='Pasaje'), 'direccion_pais'),
            (dict(direccion_numero='8-A', direccion_referencia='Solo referencia'), None),
        ]
        for datos, campo in entradas_invalidas:
            with self.subTest(datos=datos):
                res = self.editar(email='cambio@example.test', **datos)
                self.assertEqual(res.status_code, 200)
                self.assertTrue(res.context['form'].non_field_errors())
                self.assertContains(res, 'data-cliente-direccion')
                if campo:
                    direccion = res.context['form'].direccion_estructurada
                    self.assertTrue(direccion.has_error(campo))
                    self.assertEqual(direccion[campo].value(), datos[campo])
                    self.assertContains(res, f'id="id_{campo}_error"')
                self.assertEqual(Cliente.objects.filter(pk=self.ficha.pk).values().get(), antes)

        res = self.editar(direccion_legada='Dato forzado')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(Cliente.objects.filter(pk=self.ficha.pk).values().get(), antes)

        res = self.editar(**ESTRUCTURADA, email='correo sin arroba')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['form'].direccion_estructurada['direccion_numero'].value(), 'S/N')
        self.assertEqual(Cliente.objects.filter(pk=self.ficha.pk).values().get(), antes)

    def test_propietario_y_csrf_en_edicion(self):
        datos = {'nombre': self.ficha.nombre, **ESTRUCTURADA}
        otro = User.objects.create_user('direccion_otro')
        otro.perfil.puede_crear_clientes = True
        otro.perfil.save(update_fields=['puede_crear_clientes'])
        otra_sesion = Client()
        otra_sesion.force_login(otro)
        self.assertRedirects(otra_sesion.post(self.edicion, datos), reverse('cutless:lista_clientes'),
                             fetch_redirect_response=False)
        self.assertEqual(otra_sesion.get(self.historial).status_code, 404)
        segura = Client(enforce_csrf_checks=True)
        segura.force_login(self.propietario)
        self.assertEqual(segura.get(self.edicion).status_code, 200)
        self.assertEqual(segura.post(self.edicion, datos).status_code, 403)
        self.assertEqual(Cliente.objects.get(pk=self.ficha.pk).direccion_activa, LEGADO)
        datos['csrfmiddlewaretoken'] = segura.cookies['csrftoken'].value
        self.assertEqual(segura.post(self.edicion, datos).status_code, 302)
        self.assertEqual(Cliente.objects.get(pk=self.ficha.pk).direccion_modo, 'estructurada')

    def test_snapshot_de_alta_y_emision_de_borrador_queda_inmutable(self):
        proyecto, plan = self.asociar()
        borrador = self.cotizar(proyecto, plan)
        emitido_legado = self.cotizar(proyecto, plan, 'enviado')
        json_legado = emitido_legado.detalle_emitido
        self.cerrar_direccion()
        self.assertIn(b'Avenida de prueba S/N', self.pdf(borrador))
        self.assertNotIn(b'Referencia interna', self.pdf(borrador))
        nuevo = self.cotizar(proyecto, plan, 'enviado')
        self.assertEqual(nuevo.detalle_emitido['cliente']['direccion'], self.ficha.direccion_activa)

        res = self.client.post(reverse('cutless:editar_presupuesto', args=[borrador.pk]), {
            'cliente': self.ficha.pk, 'proyecto': proyecto.pk, 'optimizaciones': [plan.pk],
            'precio_tablero': '1500.50', 'mano_obra': '43.20', 'fecha_validez': date.today().isoformat(),
            'accion': 'emitir', 'revision': borrador.fecha_actualizacion.isoformat(),
        })
        self.assertEqual(res.status_code, 302)
        borrador.refresh_from_db()
        instantanea = borrador.detalle_emitido
        self.assertEqual(instantanea['cliente']['direccion'], self.ficha.direccion_activa)
        self.assertEqual(self.editar(direccion_numero='20-A').status_code, 302)

        emitido_legado.refresh_from_db()
        self.assertEqual(emitido_legado.detalle_emitido, json_legado)
        self.assertEqual(json_legado['cliente']['direccion'], LEGADO)
        self.assertIn(b'Pasaje legado', self.pdf(emitido_legado))
        self.assertIn(b'Avenida de prueba S/N', self.pdf(borrador))
        borrador.refresh_from_db()
        borrador.cerrar_detalle()
        self.assertEqual(borrador.detalle_emitido, instantanea)

        for registro in (proyecto, plan, borrador, nuevo):
            registro.refresh_from_db()
            self.assertEqual(registro.cliente_id, self.ficha.pk)
        self.assertEqual((plan.proyecto_id, borrador.proyecto_id), (proyecto.pk, proyecto.pk))
        self.assertEqual(list(borrador.optimizaciones.values_list('pk', flat=True)), [plan.pk])
        Presupuesto.objects.filter(pk=nuevo.pk).update(cliente=None)
        nuevo.refresh_from_db()
        self.assertIn(b'Avenida de prueba S/N', self.pdf(nuevo))

    def test_historico_sin_snapshot_pdf_archivado_y_regeneracion_legada(self):
        proyecto, plan = self.asociar()
        antiguo = self.cotizar(proyecto, plan)
        antiguo.estado = 'enviado'
        antiguo.save(update_fields=['estado'])
        self.cerrar_direccion()
        guardado = '%PDF-1.4\n% Archivo sintético CLI-01\n'.encode('utf-8')
        with TemporaryDirectory() as medios, self.settings(MEDIA_ROOT=Path(medios)):
            antiguo.pdf.save('historico-cli01.pdf', ContentFile(guardado))
            self.assertEqual(self.pdf(antiguo), guardado)
            antiguo.pdf.storage.delete(antiguo.pdf.name)
            pdf = self.pdf(antiguo)
            self.assertIn(b'Pasaje legado', pdf)
            self.assertNotIn(b'Avenida de prueba', pdf)
        antiguo.refresh_from_db()
        self.assertIsNone(antiguo.detalle_emitido)


class MigracionDireccionesClientesTests(TransactionTestCase):
    origen = [('cutless', '0009_cliente_direcciones_estructuradas')]
    destino = '0010_cliente_codigo_postal'

    def restaurar_esquema(self):
        ejecutor = MigrationExecutor(connection)
        ejecutor.migrate(ejecutor.loader.graph.leaf_nodes())

    def test_esquema_antiguo_migracion_expansiva_y_reejecucion_idempotente(self):
        self.addCleanup(self.restaurar_esquema)
        ejecutor = MigrationExecutor(connection)
        ejecutor.migrate(self.origen)
        historico = ejecutor.loader.project_state(self.origen).apps
        persona = historico.get_model('auth', 'User').objects.create(username='migracion-direccion')
        ClienteAnterior = historico.get_model('cutless', 'Cliente')
        ficha = ClienteAnterior.objects.create(usuario_id=persona.pk, nombre='Histórico de migración', direccion=LEGADO)
        vacio = ClienteAnterior.objects.create(usuario_id=persona.pk, nombre='Opcional de migración')
        proyecto = historico.get_model('cutless', 'Proyecto').objects.create(
            usuario_id=persona.pk, cliente_id=ficha.pk, nombre='Proyecto de migración',
        )
        opt = historico.get_model('cutless', 'Optimizacion').objects.create(
            usuario_id=persona.pk, cliente_id=ficha.pk, proyecto_id=proyecto.pk, correlativo=1,
            ancho_tablero=122, alto_tablero=244, piezas='Pieza,20,30,1',
        )
        ppto = historico.get_model('cutless', 'Presupuesto').objects.create(
            usuario_id=persona.pk, cliente_id=ficha.pk, proyecto_id=proyecto.pk,
            numero='PRE-CLI01', precio_tablero=25, costo_total=25, fecha_validez=date.today(), estado='enviado',
            detalle_emitido={'cliente': {'direccion': LEGADO}, 'optimizaciones': []},
        )
        ppto.optimizaciones.add(opt)
        campos_originales = [campo.attname for campo in ClienteAnterior._meta.concrete_fields]
        esperado = list(ClienteAnterior.objects.order_by('pk').values(*campos_originales))

        self.assertEqual(self.client.get(reverse('usuarios:login')).status_code, 200)
        session = Client(raise_request_exception=False)
        usuario = User.objects.get(pk=persona.pk)
        PerfilUsuario.objects.create(usuario=usuario, puede_crear_clientes=True)
        session.force_login(usuario)
        lista = reverse('cutless:lista_clientes')
        res = session.get(lista)
        self.assertEqual(res.status_code, 500)
        self.assertIsInstance(res.exc_info[1], DatabaseError)

        for intento in (1, 2):
            salida = StringIO()
            call_command('migrate', interactive=False, stdout=salida)
            self.assertIn(self.destino if intento == 1 else 'No migrations to apply', salida.getvalue())
            self.assertEqual(list(Cliente.objects.order_by('pk').values(*campos_originales)), esperado)
            self.assertEqual(Cliente.objects.get(pk=ficha.pk).direccion_activa, LEGADO)
            self.assertEqual(Cliente.objects.get(pk=vacio.pk).direccion_activa, '')
            columnas_nuevas = [campo.attname for campo in Cliente._meta.concrete_fields
                               if campo.attname not in campos_originales]
            self.assertTrue(all(valor is None for fila in Cliente.objects.values_list(*columnas_nuevas)
                                for valor in fila))
            presupuesto = Presupuesto.objects.get(pk=ppto.pk)
            self.assertEqual(presupuesto.detalle_emitido, ppto.detalle_emitido)
            self.assertEqual((presupuesto.cliente_id, presupuesto.proyecto_id, presupuesto.fecha_actualizacion),
                             (ficha.pk, proyecto.pk, ppto.fecha_actualizacion))
            self.assertEqual(list(presupuesto.optimizaciones.values_list('pk', flat=True)), [opt.pk])
            plan = Optimizacion.objects.get(pk=opt.pk)
            self.assertEqual((plan.cliente_id, plan.proyecto_id, plan.correlativo, plan.fecha),
                             (ficha.pk, proyecto.pk, 1, opt.fecha))
            self.assertEqual(Proyecto.objects.get(pk=proyecto.pk).fecha_actualizacion, proyecto.fecha_actualizacion)
            self.assertEqual(session.get(lista).status_code, 200)

        Cliente.objects.filter(pk=ficha.pk).update(direccion_modo='estructurada', direccion_calle='Pasaje nuevo', direccion_codigo_postal='0000100')
        ClienteAnterior.objects.filter(pk=ficha.pk).update(email='edicion-anterior@example.test')
        actual = Cliente.objects.get(pk=ficha.pk)
        self.assertEqual((actual.direccion, actual.direccion_activa, actual.email),
                         (LEGADO, 'Pasaje nuevo\n0000100', 'edicion-anterior@example.test'))
        self.assertEqual(actual.direccion_codigo_postal, '0000100')
