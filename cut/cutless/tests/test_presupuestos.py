from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from cutless.exports.pdf import generar_pdf_presupuesto
from cutless.models import Cliente, Optimizacion, Presupuesto, Proyecto


class PresupuestoNumeroTests(TestCase):
    def setUp(self):
        self.usuario_a = User.objects.create_user('usuario_a', password='test12345')
        self.usuario_b = User.objects.create_user('usuario_b', password='test12345')
        self.fecha_validez = date.today()

    def _crear_presupuesto(self, usuario, numero):
        return Presupuesto.objects.create(
            usuario=usuario,
            numero=numero,
            precio_tablero=Decimal('10000'),
            mano_obra=Decimal('0'),
            costo_total=Decimal('10000'),
            fecha_validez=self.fecha_validez,
        )

    def test_mismo_numero_en_distintos_usuarios(self):
        numero = Presupuesto.generar_numero_presupuesto(usuario=self.usuario_a)
        self._crear_presupuesto(self.usuario_a, numero)
        self._crear_presupuesto(self.usuario_b, numero)

        self.assertEqual(
            Presupuesto.objects.filter(numero=numero).count(),
            2,
        )

    def test_numero_duplicado_mismo_usuario_falla(self):
        numero = Presupuesto.generar_numero_presupuesto(usuario=self.usuario_a)
        self._crear_presupuesto(self.usuario_a, numero)

        with self.assertRaises(IntegrityError):
            self._crear_presupuesto(self.usuario_a, numero)

    def test_generador_incrementa_por_usuario(self):
        primero = Presupuesto.generar_numero_presupuesto(usuario=self.usuario_a)
        self._crear_presupuesto(self.usuario_a, primero)
        segundo = Presupuesto.generar_numero_presupuesto(usuario=self.usuario_a)

        self.assertNotEqual(primero, segundo)

    def test_numeracion_incrementa_de_9999_y_10000(self):
        from django.utils import timezone

        prefijo = f'PRE-{timezone.localdate().year}-'
        self._crear_presupuesto(self.usuario_a, prefijo + '9999')
        self._crear_presupuesto(self.usuario_a, prefijo + 'anterior')
        self.assertEqual(Presupuesto.generar_numero_presupuesto(self.usuario_a), prefijo + '10000')
        self._crear_presupuesto(self.usuario_a, prefijo + '10000')
        self.assertEqual(Presupuesto.generar_numero_presupuesto(self.usuario_a), prefijo + '10001')


class PresupuestoVigenciaTests(TestCase):
    def setUp(self):
        from cutless.models import Optimizacion

        self.usuario = User.objects.create_user('cotizaciones')
        self.client.force_login(self.usuario)
        self.opt = Optimizacion.objects.create(usuario=self.usuario, nombre='Plan original',
            ancho_tablero=122, alto_tablero=244, piezas='Puerta,40,50,1', num_tableros=2)
        self.otro = Optimizacion.objects.create(usuario=self.usuario, nombre='Plan adicional',
            ancho_tablero=122, alto_tablero=244, piezas='Cajón,10,20,1', num_tableros=3)
        self.presupuesto = Presupuesto.objects.create(usuario=self.usuario, numero='PRE-LOCAL-0001',
            precio_tablero=10, mano_obra=7, costo_total=57, fecha_validez=date.today())
        self.presupuesto.optimizaciones.set([self.opt, self.otro])

    def test_borrador_usa_planes_vigentes_al_editar_y_eliminar(self):
        from django.urls import reverse

        self.opt.num_tableros = 4
        self.opt.save(update_fields=['num_tableros'])
        url = reverse('cutless:detalle_presupuesto', args=[self.presupuesto.pk])
        detalle = self.client.get(url)
        self.assertEqual(detalle.context['presupuesto'].total_vigente, 77)
        self.otro.delete()
        detalle = self.client.get(url)
        self.assertEqual(detalle.context['presupuesto'].total_vigente, 47)
        self.assertEqual(detalle.context['total_tableros'], 4)

    def test_emision_congela_el_detalle_aunque_el_plan_cambie_o_desaparezca(self):
        from django.urls import reverse

        editar = reverse('cutless:editar_presupuesto', args=[self.presupuesto.pk])
        datos = {'estado': 'enviado', 'optimizaciones': [self.opt.pk, self.otro.pk],
                 'precio_tablero': 10, 'mano_obra': 7, 'fecha_validez': date.today().isoformat()}
        self.assertEqual(self.client.post(editar, datos).status_code, 302)
        self.presupuesto.refresh_from_db()
        self.assertIsNotNone(self.presupuesto.detalle_emitido)
        self.opt.num_tableros = 10
        self.opt.save(update_fields=['num_tableros'])
        self.otro.delete()
        url = reverse('cutless:detalle_presupuesto', args=[self.presupuesto.pk])
        respuesta = self.client.get(url)
        self.assertEqual(respuesta.context['presupuesto'].total_vigente, 57)
        self.assertEqual(respuesta.context['total_tableros'], 5)
        self.assertContains(respuesta, 'Plan adicional')
        self.assertEqual(self.client.post(editar, {'estado': 'aceptado', 'precio_tablero': 1}).status_code, 302)
        self.presupuesto.refresh_from_db()
        self.assertEqual(self.presupuesto.precio_tablero, 10)
        self.assertEqual(self.presupuesto.estado, 'aceptado')

    def test_emitido_historico_conserva_total_sin_reconstruir_desglose(self):
        from django.urls import reverse

        self.presupuesto.estado = 'enviado'
        self.presupuesto.save(update_fields=['estado'])
        self.opt.delete()
        url = reverse('cutless:detalle_presupuesto', args=[self.presupuesto.pk])
        respuesta = self.client.get(url)
        self.assertContains(respuesta, 'Cotización histórica')
        self.assertEqual(respuesta.context['presupuesto'].total_vigente, 57)
        self.presupuesto.refresh_from_db()
        self.assertIsNone(self.presupuesto.detalle_emitido)


class PresupuestoFechaCreacionTests(TestCase):
    def setUp(self):
        self.instante = datetime(2026, 7, 15, 3, 59, tzinfo=UTC)
        self.reloj = self.enterContext(patch('django.utils.timezone.now', return_value=self.instante))
        self.hoy = self.instante.astimezone(ZoneInfo('America/Santiago')).date()
        self.ayer = self.hoy - timedelta(days=1)
        self.usuario = User.objects.create_user('pre01')
        self.usuario.perfil.puede_crear_presupuestos = True
        self.usuario.perfil.save(update_fields=['puede_crear_presupuestos'])
        self.client.force_login(self.usuario)
        self.ficha = Cliente.objects.create(usuario=self.usuario, nombre='Cliente PRE-01')
        self.proyecto = Proyecto.objects.create(usuario=self.usuario, cliente=self.ficha, nombre='Proyecto PRE-01')
        self.plan = Optimizacion.objects.create(
            usuario=self.usuario, cliente=self.ficha, proyecto=self.proyecto, nombre='Plan PRE-01',
            ancho_tablero=122, alto_tablero=244, piezas='Puerta,40,50,1', num_tableros=2,
        )
        self.alta = reverse('cutless:crear_presupuesto')
        self.datos = {
            'fecha_validez': self.hoy.isoformat(), 'cliente': str(self.ficha.pk),
            'optimizaciones': [str(self.plan.pk)], 'precio_tablero': '150.50', 'mano_obra': '25.25',
            'estado': 'borrador', 'proyecto': str(self.proyecto.pk), 'notas': 'Conservar estas notas',
        }

    def test_fecha_pasada_en_post_directo_conserva_datos_y_error_accesible(self):
        datos = {**self.datos, 'fecha_validez': self.ayer.isoformat(), 'estado': 'enviado'}
        respuesta = self.client.post(self.alta, datos)
        self.assertContains(respuesta,
                            'La fecha de validez no puede ser anterior a hoy. Selecciona la fecha actual o una posterior.')
        self.assertContains(respuesta, 'aria-invalid="true"')
        self.assertContains(respuesta, 'aria-describedby="id_fecha_validez_helptext id_fecha_validez_error"')
        self.assertContains(respuesta, 'id="id_fecha_validez_error"')
        self.assertContains(respuesta, 'id="id_fecha_validez_helptext"')
        form = respuesta.context['form']
        self.assertTrue(form.has_error('fecha_validez', 'fecha_pasada'))
        for campo, valor in datos.items():
            with self.subTest(campo=campo):
                self.assertEqual(form[campo].value(), valor)
        self.assertTrue(respuesta.context['optimizaciones_info'][0]['seleccionada'])
        self.assertFalse(Presupuesto.objects.exists())

    def test_fecha_invalida_no_crea_cliente_ni_asigna_numero_ni_notifica(self):
        datos = {**self.datos, 'fecha_validez': self.ayer.isoformat(),
                 'cliente': '', 'nombre_cliente_nuevo': 'Cliente automático'}
        with patch.object(Presupuesto, 'generar_numero_presupuesto') as numero, \
                patch('cutless.views.budgets.enviar_notificacion') as notificar:
            respuesta = self.client.post(self.alta, datos)
            numero.assert_not_called()
            notificar.assert_not_called()
        form = respuesta.context['form']
        self.assertTrue(form.has_error('fecha_validez', 'fecha_pasada'))
        self.assertEqual(form['nombre_cliente_nuevo'].value(), 'Cliente automático')
        self.assertEqual(list(Cliente.objects.all()), [self.ficha])
        self.assertFalse(Presupuesto.objects.exists())

        respuesta = self.client.post(self.alta, {**datos, 'fecha_validez': self.hoy.isoformat()})
        self.assertEqual(respuesta.status_code, 302)
        presupuesto = Presupuesto.objects.get(usuario=self.usuario)
        self.assertEqual(presupuesto.numero, f'PRE-{self.hoy.year}-0001')
        self.assertEqual(presupuesto.cliente.nombre, 'Cliente automático')

    def test_fecha_vacia_o_mal_formada_conserva_validacion_de_django(self):
        for fecha, codigo in (('', 'required'), ('fecha imposible', 'invalid')):
            with self.subTest(fecha=fecha):
                respuesta = self.client.post(self.alta, {**self.datos, 'fecha_validez': fecha})
                self.assertEqual(respuesta.status_code, 200)
                form = respuesta.context['form']
                self.assertTrue(form.has_error('fecha_validez', codigo))
                self.assertEqual(form['fecha_validez'].value(), fecha)
        self.assertFalse(Presupuesto.objects.exists())

    def test_hoy_y_manana_desde_una_optimizacion_en_borrador_y_enviado(self):
        ruta = f'{self.alta}?optimizacion={self.plan.pk}'
        inicial = self.client.get(ruta)
        self.assertContains(inicial, 'type="date"')
        self.assertContains(inicial, f'min="{self.hoy.isoformat()}"')
        self.assertEqual(inicial.context['form']['fecha_validez'].value(), self.hoy)
        self.assertTrue(inicial.context['optimizaciones_info'][0]['seleccionada'])
        self.assertEqual(inicial.context['form']['proyecto'].value(), self.proyecto.pk)

        for fecha in (self.hoy, self.hoy + timedelta(days=1)):
            for estado in ('borrador', 'enviado'):
                with self.subTest(fecha=fecha, estado=estado):
                    respuesta = self.client.post(ruta, {**self.datos, 'cliente': '',
                                                       'fecha_validez': fecha.isoformat(), 'estado': estado})
                    presupuesto = Presupuesto.objects.get(usuario=self.usuario, fecha_validez=fecha, estado=estado)
                    self.assertRedirects(respuesta, reverse('cutless:detalle_presupuesto', args=[presupuesto.pk]),
                                         fetch_redirect_response=False)
                    self.assertEqual(presupuesto.cliente, self.ficha)
                    self.assertEqual(presupuesto.proyecto, self.proyecto)
                    self.assertEqual(list(presupuesto.optimizaciones.all()), [self.plan])
                    self.assertEqual(presupuesto.costo_total, Decimal('326.25'))
                    self.assertEqual(presupuesto.detalle_emitido is not None, estado == 'enviado')

    def test_recalcula_fecha_en_post_al_cruzar_medianoche_en_santiago(self):
        # Los dos instantes UTC corresponden a las 23:59 en Chile, con y sin horario de verano.
        instantes = (self.instante, datetime(2026, 1, 15, 2, 59, tzinfo=UTC))
        with timezone.override('UTC'):
            for instante in instantes:
                with self.subTest(instante=instante):
                    self.reloj.return_value = instante
                    dia_chile = instante.date() - timedelta(days=1)
                    apertura = self.client.get(self.alta)
                    self.assertEqual(apertura.context['form']['fecha_validez'].value(), dia_chile)
                    self.assertContains(apertura, f'min="{dia_chile.isoformat()}"')

                    self.reloj.return_value += timedelta(minutes=1)
                    envio = self.client.post(self.alta, {**self.datos, 'fecha_validez': dia_chile.isoformat()})
                    self.assertTrue(envio.context['form'].has_error('fecha_validez', 'fecha_pasada'))
                    self.assertContains(envio, f'min="{instante.date().isoformat()}"')
        self.assertFalse(Presupuesto.objects.exists())

    def test_borrador_historico_con_fecha_pasada_se_puede_editar(self):
        presupuesto = Presupuesto.objects.create(
            usuario=self.usuario, cliente=self.ficha, proyecto=self.proyecto, numero='PRE-BORRADOR',
            precio_tablero=100, mano_obra=20, costo_total=220, fecha_validez=self.ayer,
        )
        presupuesto.optimizaciones.add(self.plan)
        ruta = reverse('cutless:editar_presupuesto', args=[presupuesto.pk])
        form = self.client.get(ruta).context['form']
        self.assertEqual(form['fecha_validez'].value(), self.ayer)
        self.assertNotIn('min', form.fields['fecha_validez'].widget.attrs)
        respuesta = self.client.post(ruta, {**self.datos, 'fecha_validez': self.ayer.isoformat()})
        self.assertEqual(respuesta.status_code, 302)
        presupuesto.refresh_from_db()
        self.assertEqual(presupuesto.fecha_validez, self.ayer)
        self.assertEqual(presupuesto.notas, self.datos['notas'])
        self.assertEqual(list(presupuesto.optimizaciones.all()), [self.plan])

    def test_vencido_historico_consultable_y_pdf_guardado_intacto(self):
        with TemporaryDirectory() as media, self.settings(MEDIA_ROOT=media):
            presupuesto = Presupuesto.objects.create(
                usuario=self.usuario, cliente=self.ficha, numero='PRE-HISTORICO', estado='vencido',
                precio_tablero=100, costo_total=200, fecha_validez=self.ayer,
            )
            presupuesto.optimizaciones.add(self.plan)
            archivo = Path(media) / 'historico.pdf'
            generar_pdf_presupuesto(presupuesto, archivo_salida=str(archivo))
            original = archivo.read_bytes()
            presupuesto.pdf = archivo.name
            presupuesto.save(update_fields=['pdf'])

            resumen = self.client.get(reverse('cutless:lista_presupuestos'))
            self.assertContains(resumen, presupuesto.numero)
            detalle = self.client.get(reverse('cutless:detalle_presupuesto', args=[presupuesto.pk]))
            self.assertContains(detalle, 'Cotización histórica')
            self.assertEqual(detalle.context['presupuesto'].fecha_validez, self.ayer)
            respuesta = self.client.get(reverse('cutless:generar_pdf_presupuesto', args=[presupuesto.pk]))
            self.assertEqual(respuesta.status_code, 200)
            self.assertEqual(respuesta['Content-Type'], 'application/pdf')
            self.assertEqual(b''.join(respuesta.streaming_content), original)
            presupuesto.refresh_from_db()
            self.assertEqual((presupuesto.estado, presupuesto.fecha_validez), ('vencido', self.ayer))
            self.assertIsNone(presupuesto.detalle_emitido)

    def test_alta_con_fecha_valida_respeta_permisos_y_propiedad(self):
        otra_cuenta = User.objects.create_user('pre01-ajeno')
        cliente = Cliente.objects.create(usuario=otra_cuenta, nombre='Cliente ajeno')
        proyecto = Proyecto.objects.create(usuario=otra_cuenta, nombre='Proyecto ajeno')
        plan = Optimizacion.objects.create(usuario=otra_cuenta, ancho_tablero=122, alto_tablero=244,
                                           piezas='Pieza,20,20,1', num_tableros=1)
        ruta = f'{self.alta}?optimizacion={plan.pk}'
        self.assertEqual(self.client.post(ruta, self.datos).status_code, 404)
        respuesta = self.client.post(self.alta, {**self.datos, 'cliente': cliente.pk,
                                                'proyecto': proyecto.pk, 'optimizaciones': [plan.pk]})
        form = respuesta.context['form']
        for campo in ('cliente', 'proyecto', 'optimizaciones'):
            self.assertTrue(form.has_error(campo, 'invalid_choice'))
        self.assertFalse(form.has_error('fecha_validez'))

        self.usuario.perfil.puede_crear_presupuestos = False
        self.usuario.perfil.save(update_fields=['puede_crear_presupuestos'])
        self.assertRedirects(self.client.post(self.alta, self.datos), reverse('cutless:index'))
        self.assertFalse(Presupuesto.objects.exists())


class PresupuestoConcurrenciaTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_dos_altas_simultaneas_sin_presupuestos_previos(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from django.db import close_old_connections
        from django.test import Client
        from django.urls import reverse
        from cutless.models import Optimizacion

        usuario = User.objects.create_user('numeracion_concurrente')
        plan = Optimizacion.objects.create(usuario=usuario, ancho_tablero=122, alto_tablero=244,
                                          piezas='Puerta,40,50,1', num_tableros=1)
        url = reverse('cutless:crear_presupuesto')
        datos = {'optimizaciones': [plan.pk], 'precio_tablero': 10, 'mano_obra': 0,
                 'fecha_validez': (timezone.localdate() + timedelta(days=1)).isoformat(), 'estado': 'borrador'}
        clientes = [Client(), Client()]
        for cliente in clientes:
            cliente.force_login(usuario)
        inicio = Barrier(2, timeout=10)

        def alta(cliente):
            close_old_connections()
            try:
                inicio.wait()
                return cliente.post(url, datos).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(alta, clientes)), [302, 302])
        prefijo = f'PRE-{timezone.localdate().year}-'
        self.assertEqual(
            set(Presupuesto.objects.filter(usuario=usuario).values_list('numero', flat=True)),
            {prefijo + '0001', prefijo + '0002'},
        )
