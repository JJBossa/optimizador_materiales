from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from io import StringIO
from threading import Barrier, Event
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import close_old_connections, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from cutless.models import Cliente, Material, Optimizacion, Presupuesto, Proyecto
from cutless.services.presupuestos import (
    fecha_comercial, presupuestos_por_vencer, registrar_transicion, sincronizar_vencimientos,
)


def datos_de_cotizacion(plan, **cambios):
    return {
        'optimizaciones': [plan.pk], 'precio_tablero': '25', 'mano_obra': '5',
        'fecha_validez': fecha_comercial().isoformat(), 'notas': 'Presupuesto sintético',
        **cambios,
    }


class EstadosPresupuestosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user('pre03_local')
        cls.ajeno = User.objects.create_user('pre03_otro')
        cls.cliente = Cliente.objects.create(usuario=cls.usuario, nombre='Cliente sintético')
        material = Material.objects.create(usuario=cls.usuario, nombre='Tablero sintético', ancho=122, alto=244)
        cls.plan = Optimizacion.objects.create(
            usuario=cls.usuario, ancho_tablero=122, alto_tablero=244, material=material, num_tableros=3,
            piezas='Frente,20,30,1',
        )

    def setUp(self):
        self.client.force_login(self.usuario)
        self.alta = reverse('cutless:crear_presupuesto')
        self.lista = reverse('cutless:lista_presupuestos')
        self.hoy = fecha_comercial()
        self.ayer = self.hoy - timedelta(days=1)
        self.manana = self.hoy + timedelta(days=1)

    def nuevo(self, estado='borrador', *, fecha=None, usuario=None):
        return Presupuesto.objects.create(
            usuario=usuario or self.usuario, numero=f'PRE-PRUEBA-{Presupuesto.objects.count()}',
            precio_tablero=25, mano_obra=5, costo_total=80, fecha_validez=fecha or self.hoy, estado=estado,
        )

    def editar(self, presupuesto):
        return reverse('cutless:editar_presupuesto', args=[presupuesto.pk])

    def detalle(self, presupuesto):
        return reverse('cutless:detalle_presupuesto', args=[presupuesto.pk])

    def test_alta_distingue_borrador_emision_y_solicitudes_invalidas(self):
        datos = datos_de_cotizacion(self.plan)
        for cambios in (
            {'accion': 'desconocida'}, {'accion': ['emitir', 'emitir']},
            {'accion': ['guardar_borrador', 'emitir']}, {'accion': ''},
            {'estado': 'enviado'}, {'estado': 'aceptado'}, {'estado': 'rechazado'}, {'estado': 'vencido'},
            {'accion': 'emitir', 'estado': 'emitido'},
        ):
            with self.subTest(cambios=cambios):
                respuesta = self.client.post(self.alta, {**datos, **cambios})
                self.assertContains(respuesta, 'Usa una sola acción')
                self.assertEqual(respuesta.context['form']['notas'].value(), datos['notas'])
                self.assertFalse(Presupuesto.objects.exists())
        for cambios in ({}, {'estado': 'borrador'}, {'accion': 'guardar_borrador'}, {'accion': 'emitir'}):
            respuesta = self.client.post(self.alta, {**datos, 'cliente': self.cliente.pk, **cambios})
            presupuesto = Presupuesto.objects.latest('pk')
            emitir = cambios.get('accion') == 'emitir'
            self.assertRedirects(respuesta, self.detalle(presupuesto), fetch_redirect_response=False)
            self.assertEqual(presupuesto.estado, 'emitido' if emitir else 'borrador')
            self.assertEqual(presupuesto.costo_total, 80)
            self.assertEqual(presupuesto.detalle_emitido is not None, emitir)
            if emitir:
                self.assertEqual(presupuesto.detalle_emitido['cliente']['nombre'], self.cliente.nombre)
                self.assertEqual(presupuesto.detalle_emitido['optimizaciones'][0]['material'], self.plan.material.nombre)
        self.assertEqual(Presupuesto.objects.values('numero').distinct().count(), 4)

    def test_emision_incompleta_o_ajena_no_crea_presupuesto_ni_cliente(self):
        datos = datos_de_cotizacion(self.plan, accion='emitir', nombre_cliente_nuevo='Cliente nuevo')
        respuesta = self.client.post(self.alta, {**datos, 'optimizaciones': []})
        self.assertTrue(respuesta.context['form'].has_error('optimizaciones', 'required'))
        ficha = Cliente.objects.create(usuario=self.ajeno, nombre='Cliente ajeno')
        proyecto = Proyecto.objects.create(usuario=self.ajeno, nombre='Proyecto ajeno')
        plan = Optimizacion.objects.create(
            usuario=self.ajeno, ancho_tablero=122, alto_tablero=244, piezas='Frente,20,30,1',
        )
        respuesta = self.client.post(self.alta, {
            **datos, 'cliente': ficha.pk, 'proyecto': proyecto.pk, 'optimizaciones': [plan.pk],
        })
        for campo in ('cliente', 'proyecto', 'optimizaciones'):
            self.assertTrue(respuesta.context['form'].has_error(campo, 'invalid_choice'))
        self.assertFalse(Cliente.objects.filter(nombre='Cliente nuevo').exists())
        self.assertFalse(Presupuesto.objects.exists())

    def test_edicion_de_borrador_vencido_y_emision_atomica_con_revision(self):
        presupuesto = self.nuevo(fecha=self.ayer)
        notas = '  Histórico\r\n' + 'ñ' * 160 + '  '
        Presupuesto.objects.filter(pk=presupuesto.pk).update(notas=notas)
        presupuesto.optimizaciones.add(self.plan)
        ruta = self.editar(presupuesto)
        revision = self.client.get(ruta).context['form']['revision'].value()
        datos = datos_de_cotizacion(self.plan, revision=revision, fecha_validez=self.ayer.isoformat())
        del datos['notas']
        respuesta = self.client.post(ruta, {**datos, 'accion': 'guardar_borrador', 'precio_tablero': '30'})
        self.assertEqual(respuesta.status_code, 302)
        presupuesto.refresh_from_db()
        self.assertEqual((presupuesto.estado, presupuesto.fecha_validez, presupuesto.notas),
                         ('borrador', self.ayer, notas))
        self.assertIsNone(presupuesto.detalle_emitido)
        for accion in ('guardar_borrador', 'emitir'):
            self.assertContains(self.client.post(ruta, {**datos, 'accion': accion}), 'Este borrador cambió')
        datos['revision'] = presupuesto.fecha_actualizacion.isoformat()
        antes = Presupuesto.objects.values().get(pk=presupuesto.pk)
        respuesta = self.client.post(ruta, {**datos, 'accion': 'emitir', 'nombre_cliente_nuevo': 'No guardar'})
        self.assertTrue(respuesta.context['form'].has_error('fecha_validez', 'emision_fecha_pasada'))
        self.assertContains(respuesta, 'id="id_fecha_validez_error"')
        self.assertEqual(respuesta.context['form']['nombre_cliente_nuevo'].value(), 'No guardar')
        self.assertEqual(Presupuesto.objects.values().get(pk=presupuesto.pk), antes)
        self.assertFalse(Cliente.objects.filter(nombre='No guardar').exists())
        datos.update(accion='emitir', fecha_validez=self.hoy.isoformat())
        self.assertEqual(self.client.post(ruta, datos).status_code, 302)
        presupuesto.refresh_from_db()
        self.assertEqual((presupuesto.numero, presupuesto.estado, presupuesto.notas),
                         (antes['numero'], 'emitido', notas))
        cerrado = Presupuesto.objects.values().get(pk=presupuesto.pk)
        self.assertEqual(self.client.post(ruta, datos).status_code, 200)
        self.assertEqual(Presupuesto.objects.values().get(pk=presupuesto.pk), cerrado)
        self.assertEqual(Presupuesto.objects.count(), 1)

    def test_transiciones_y_formulario_obsoleto_protegen_datos_cotizados(self):
        for origen, destino in (
            ('emitido', 'enviado'), ('emitido', 'aceptado'), ('emitido', 'rechazado'),
            ('enviado', 'aceptado'), ('enviado', 'rechazado'),
        ):
            with self.subTest(origen=origen, destino=destino):
                presupuesto = self.nuevo(origen)
                presupuesto.optimizaciones.add(self.plan)
                Presupuesto.objects.filter(pk=presupuesto.pk).update(
                    cliente=self.cliente, detalle_emitido={'cliente': None, 'optimizaciones': []}, notas='Cotizado',
                )
                antes = Presupuesto.objects.values().get(pk=presupuesto.pk)
                ruta = self.editar(presupuesto)
                datos = {
                    'estado_origen': origen, 'precio_tablero': '1000', 'mano_obra': '100',
                    'optimizaciones': [], 'cliente': '', 'notas': '', 'numero': 'falso', 'fecha_validez': self.ayer,
                }
                for invalido in ('borrador', 'desconocido', 'vencido', [destino, destino]):
                    respuesta = self.client.post(ruta, {**datos, 'estado': invalido})
                    self.assertIn('estado', respuesta.context['form'].errors)
                self.assertEqual(Presupuesto.objects.values().get(pk=presupuesto.pk), antes)
                self.assertEqual(self.client.post(ruta, {**datos, 'estado': destino}).status_code, 302)
                despues = Presupuesto.objects.values().get(pk=presupuesto.pk)
                self.assertEqual(despues, {**antes, 'estado': destino, 'fecha_actualizacion': despues['fecha_actualizacion']})
                if destino == 'enviado':
                    self.assertEqual(self.client.post(ruta, {**datos, 'estado': 'aceptado'}).status_code, 200)
                presupuesto.refresh_from_db()
                self.assertEqual(presupuesto.estado, destino)
                self.assertEqual(list(presupuesto.optimizaciones.all()), [self.plan])

        for estado in ('aceptado', 'rechazado', 'vencido'):
            presupuesto = self.nuevo(estado)
            ruta = self.editar(presupuesto)
            self.assertNotContains(self.client.get(self.detalle(presupuesto)), 'Registrar estado')
            self.assertEqual(self.client.post(ruta, {'estado_origen': estado, 'estado': 'aceptado'}).status_code, 200)
            presupuesto.refresh_from_db()
            self.assertEqual(presupuesto.estado, estado)

    def test_vencimiento_condicional_propietario_filtros_y_solo_cambia_estado(self):
        pendientes = [self.nuevo(estado, fecha=self.ayer) for estado in ('emitido', 'enviado')]
        intactos = [self.nuevo(estado, fecha=self.ayer) for estado in ('borrador', 'aceptado', 'rechazado', 'vencido')]
        intactos += [self.nuevo('emitido'), self.nuevo('enviado', fecha=self.manana)]
        ajeno = self.nuevo('emitido', fecha=self.ayer, usuario=self.ajeno)
        antes = {fila['id']: fila for fila in Presupuesto.objects.values()}
        self.assertContains(self.client.get(self.detalle(pendientes[0])), 'data-presupuesto-estado="vencido"')
        self.assertEqual(Presupuesto.objects.get(pk=pendientes[1].pk).estado, 'enviado')
        respuesta = self.client.get(self.lista, {'estado': 'emitido'})
        self.assertEqual(list(respuesta.context['presupuestos']), [intactos[-2]])
        vencidos = self.client.get(self.lista, {'estado': 'vencido'}).context['presupuestos']
        self.assertEqual({p.pk for p in vencidos}, {p.pk for p in [*pendientes, intactos[3]]})
        for pk, original in antes.items():
            actualizado = Presupuesto.objects.values().get(pk=pk)
            esperado = {**original, 'estado': 'vencido'} if pk in {p.pk for p in pendientes} else original
            self.assertEqual(actualizado, esperado)
        self.assertEqual(sincronizar_vencimientos(Presupuesto.objects.filter(usuario=self.usuario)), 0)
        self.assertEqual(list(presupuestos_por_vencer(Presupuesto.objects.all(), antes_de=self.hoy)), [ajeno])

    def test_post_vencido_sin_visita_previa_y_emision_o_transicion_ajenas(self):
        presupuesto = self.nuevo('enviado', fecha=self.ayer)
        ruta = self.editar(presupuesto)
        respuesta = self.client.post(ruta, {'estado_origen': 'enviado', 'estado': 'aceptado'})
        self.assertContains(respuesta, 'Este presupuesto está cerrado.')
        presupuesto.refresh_from_db()
        self.assertEqual(presupuesto.estado, 'vencido')
        ajeno = self.nuevo('emitido', fecha=self.ayer, usuario=self.ajeno)
        borrador = self.nuevo(usuario=self.ajeno)
        for objeto in (ajeno, borrador):
            self.assertEqual(self.client.get(self.detalle(objeto)).status_code, 302)
            self.assertEqual(self.client.get(reverse('cutless:generar_pdf_presupuesto', args=[objeto.pk])).status_code, 302)
            self.assertEqual(self.client.post(self.editar(objeto), {
                'estado_origen': 'emitido', 'estado': 'aceptado',
            }).status_code, 302)
            self.assertEqual(self.client.post(self.editar(objeto), datos_de_cotizacion(self.plan, accion='emitir',
                revision=objeto.fecha_actualizacion.isoformat())).status_code, 302)
            self.assertEqual(Presupuesto.objects.get(pk=objeto.pk).estado, objeto.estado)

    def test_transicion_get_csrf_y_asociaciones_cerradas(self):
        presupuesto = self.nuevo('emitido')
        ruta = self.editar(presupuesto)
        seguro = Client(enforce_csrf_checks=True)
        seguro.force_login(self.usuario)
        self.assertContains(seguro.get(ruta + '?estado=enviado'), 'Registrar envío')
        self.assertEqual(seguro.post(ruta, {'estado': 'enviado', 'estado_origen': 'emitido'}).status_code, 403)
        agregar = reverse('cutless:agregar_optimizaciones_presupuesto', args=[presupuesto.pk])
        self.assertRedirects(self.client.post(agregar, {'optimizaciones': [self.plan.pk]}), self.detalle(presupuesto))
        presupuesto.refresh_from_db()
        self.assertEqual(presupuesto.estado, 'emitido')
        self.assertFalse(presupuesto.optimizaciones.exists())

    def test_pdf_muestra_estado_efectivo_sin_escribir_en_base(self):
        for estado, fecha, etiqueta in (
            ('borrador', self.ayer, 'Borrador'), ('emitido', self.hoy, 'Emitido'), ('enviado', self.ayer, 'Vencido'),
        ):
            presupuesto = self.nuevo(estado, fecha=fecha)
            antes = Presupuesto.objects.values().get(pk=presupuesto.pk)
            # Desactivar compresión permite verificar la etiqueta real del PDF.
            with patch('reportlab.rl_config.pageCompression', 0):
                respuesta = self.client.get(reverse('cutless:generar_pdf_presupuesto', args=[presupuesto.pk]))
                contenido = b''.join(respuesta.streaming_content)
            self.assertIn(f'Estado: {etiqueta}'.encode(), contenido)
            self.assertEqual(Presupuesto.objects.values().get(pk=presupuesto.pk), antes)

    def test_comando_simula_y_repite_sin_escrituras_adicionales(self):
        presupuesto = self.nuevo('emitido', fecha=self.ayer)
        salida = StringIO()
        call_command('actualizar_presupuestos_vencidos', '--dry-run', stdout=salida)
        self.assertIn('Presupuestos elegibles: 1', salida.getvalue())
        self.assertEqual(Presupuesto.objects.get(pk=presupuesto.pk).estado, 'emitido')
        for cantidad in (1, 0):
            salida = StringIO()
            call_command('actualizar_presupuestos_vencidos', stdout=salida)
            self.assertIn(f'Presupuestos actualizados: {cantidad}', salida.getvalue())
            self.assertEqual(Presupuesto.objects.get(pk=presupuesto.pk).estado, 'vencido')

    def test_comienzo_del_horario_de_verano_salta_a_la_fecha_comercial_siguiente(self):
        instante = datetime(2026, 9, 6, 3, 59, tzinfo=UTC)
        presupuesto = self.nuevo('emitido', fecha=instante.date() - timedelta(days=1))
        with timezone.override('UTC'), patch('django.utils.timezone.now', return_value=instante) as reloj:
            self.assertEqual(fecha_comercial(), presupuesto.fecha_validez)
            self.assertEqual(sincronizar_vencimientos(Presupuesto.objects.all()), 0)
            reloj.return_value += timedelta(minutes=1)
            self.assertEqual(fecha_comercial(), instante.date())
            self.assertEqual(sincronizar_vencimientos(Presupuesto.objects.all()), 1)


class EstadosPresupuestosConcurrenciaTests(TransactionTestCase):
    def setUp(self):
        self.usuario = User.objects.create_user('pre03_concurrente')
        self.presupuesto = Presupuesto.objects.create(
            usuario=self.usuario, numero='PRE-C-1', precio_tablero=25, costo_total=80, fecha_validez=fecha_comercial(),
        )
        self.plan = Optimizacion.objects.create(
            usuario=self.usuario, ancho_tablero=122, alto_tablero=244, piezas='Frente,20,30,1', num_tableros=3,
        )

    @skipUnlessDBFeature('has_select_for_update')
    def test_dos_emisiones_simultaneas_cierran_el_detalle_una_vez(self):
        clientes = [Client(), Client()]
        for cliente in clientes:
            cliente.force_login(self.usuario)
        ruta = reverse('cutless:editar_presupuesto', args=[self.presupuesto.pk])
        revision = self.presupuesto.fecha_actualizacion.isoformat()
        inicio = Barrier(2, timeout=10)

        def emitir(cliente):
            close_old_connections()
            try:
                inicio.wait()
                return cliente.post(ruta, datos_de_cotizacion(self.plan, accion='emitir', revision=revision)).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as grupo:
            self.assertEqual(sorted(grupo.map(emitir, clientes)), [200, 302])
        self.presupuesto.refresh_from_db()
        self.assertEqual((self.presupuesto.estado, self.presupuesto.costo_total), ('emitido', 80))
        self.assertEqual(len(self.presupuesto.detalle_emitido['optimizaciones']), 1)
        self.assertEqual(Presupuesto.objects.count(), 1)

    @skipUnlessDBFeature('has_select_for_update')
    def test_update_que_espera_aceptacion_revalida_estado(self):
        self.presupuesto.estado = 'enviado'
        self.presupuesto.save(update_fields=['estado'])
        hoy = fecha_comercial()
        objetivo = Presupuesto.objects.filter(pk=self.presupuesto.pk)
        intentando = Event()

        def vencer():
            close_old_connections()
            try:
                def al_actualizar(execute, sql, params, many, context):
                    if sql.startswith('UPDATE'):
                        intentando.set()
                    return execute(sql, params, many, context)
                with connection.execute_wrapper(al_actualizar):
                    return sincronizar_vencimientos(objetivo, hoy=hoy + timedelta(days=1))
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=1) as grupo:
            with transaction.atomic():
                objetivo.select_for_update().get()
                futuro = grupo.submit(vencer)
                self.assertTrue(intentando.wait(10))
                self.assertEqual(registrar_transicion(objetivo, origen='enviado', destino='aceptado', hoy=hoy), 1)
            self.assertEqual(futuro.result(timeout=10), 0)
        self.presupuesto.refresh_from_db()
        self.assertEqual(self.presupuesto.estado, 'aceptado')


class MigracionEstadoEmitidoTests(TransactionTestCase):
    def test_instalar_estado_emitido_conserva_datos_y_relaciones(self):
        anterior = [('cutless', '0010_cliente_codigo_postal')]
        nuevo = [('cutless', '0011_presupuesto_estado_emitido')]
        ejecutor = MigrationExecutor(connection)
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(ejecutor.loader.graph.leaf_nodes()))
        ejecutor.migrate(anterior)
        apps = ejecutor.loader.project_state(anterior).apps
        persona = apps.get_model('auth', 'User').objects.create(username='pre03_migracion')
        ClienteAnterior = apps.get_model('cutless', 'Cliente')
        ficha = ClienteAnterior.objects.create(usuario_id=persona.pk, nombre='Cliente de migración')
        plan = apps.get_model('cutless', 'Optimizacion').objects.create(
            usuario_id=persona.pk, correlativo=1, ancho_tablero=122, alto_tablero=244, piezas='Frente,20,30,1',
        )
        presupuestos = apps.get_model('cutless', 'Presupuesto').objects
        for estado in ('borrador', 'enviado', 'aceptado', 'rechazado', 'vencido'):
            registro = presupuestos.create(
                usuario_id=persona.pk, cliente_id=ficha.pk, numero=f'PRE-M-{estado}', precio_tablero=23,
                mano_obra=12, costo_total=50, fecha_validez=fecha_comercial(), estado=estado,
                notas='  ñ\r\n' * 150, pdf=f'{estado}.pdf',
                detalle_emitido={'cliente': None, 'optimizaciones': []} if estado == 'enviado' else None,
            )
            registro.optimizaciones.add(plan)
        originales = list(presupuestos.order_by('pk').values())
        MigrationExecutor(connection).migrate(nuevo)
        self.assertEqual(list(Presupuesto.objects.order_by('pk').values()), originales)
        for presupuesto in Presupuesto.objects.all():
            self.assertEqual(list(presupuesto.optimizaciones.values_list('pk', flat=True)), [plan.pk])
        self.assertEqual(dict(Presupuesto.ESTADOS_CHOICES)['emitido'], 'Emitido')
        self.assertEqual(Presupuesto._meta.get_field('estado').get_default(), 'borrador')
