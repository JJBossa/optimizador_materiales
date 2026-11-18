from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature

from cutless.models import Presupuesto


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


class PresupuestoConcurrenciaTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_dos_altas_simultaneas_sin_presupuestos_previos(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from django.db import close_old_connections
        from django.test import Client
        from django.urls import reverse
        from django.utils import timezone

        from cutless.models import Optimizacion

        usuario = User.objects.create_user('numeracion_concurrente')
        plan = Optimizacion.objects.create(usuario=usuario, ancho_tablero=122, alto_tablero=244,
                                          piezas='Puerta,40,50,1', num_tableros=1)
        url = reverse('cutless:crear_presupuesto')
        datos = {'optimizaciones': [plan.pk], 'precio_tablero': 10, 'mano_obra': 0,
                 'fecha_validez': date.today().isoformat(), 'estado': 'borrador'}
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
