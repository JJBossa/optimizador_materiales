from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, Event
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import close_old_connections, connection, transaction
from django.test import Client, TestCase, TransactionTestCase, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from cutless.models import Cliente, Optimizacion, Presupuesto, Proyecto
from cutless.services.calendario import fecha_comercial
from cutless.services.proyectos import (
    con_estado_efectivo, finales_planificados, inicios_planificados, proyectos_atrasados,
)


class CicloProyectosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user('pro03_propietario')
        cls.otro = User.objects.create_user('pro03_ajeno')
        cls.cliente = Cliente.objects.create(usuario=cls.usuario, nombre='Cliente sintético')

    def setUp(self):
        self.client.force_login(self.usuario)
        self.hoy = fecha_comercial()
        self.ayer = self.hoy - timedelta(days=1)
        self.manana = self.hoy + timedelta(days=1)
        self.alta = reverse('cutless:crear_proyecto')
        self.lista = reverse('cutless:lista_proyectos')

    def nuevo(self, **datos):
        return Proyecto.objects.create(**{
            'usuario': self.usuario, 'cliente': self.cliente, 'nombre': 'Proyecto sintético', **datos,
        })

    def plan(self, **datos):
        return Optimizacion.objects.create(ancho_tablero=122, alto_tablero=244, piezas='Frente,20,30,1',
                                           **{'usuario': self.usuario, **datos})

    def ruta(self, accion, proyecto):
        return reverse(f'cutless:{accion}_proyecto', args=[proyecto.pk])

    def estado(self, proyecto, accion, origen):
        return self.client.post(self.ruta('cambiar_estado', proyecto), {'accion': accion, 'estado_origen': origen})

    def test_alta_comienza_en_planificacion_y_solo_asocia_planes_propios(self):
        self.assertNotContains(self.client.get(self.alta), 'name="estado"')
        plan = self.plan()
        ajeno = self.plan(usuario=self.otro)
        datos = {'nombre': 'Alta sintética', 'fecha_inicio': self.hoy.isoformat(), 'optimizaciones': [plan.pk]}
        for estado in ('en_proceso', 'atrasado', 'completado', 'cancelado', 'inexistente', ['planificacion'] * 2):
            with self.subTest(estado=estado):
                self.assertContains(self.client.post(self.alta, {**datos, 'estado': estado}),
                                    'El estado se cambia con las acciones')
                self.assertFalse(Proyecto.objects.exists())
                plan.refresh_from_db()
                self.assertIsNone(plan.proyecto_id)
        respuesta = self.client.post(self.alta, {**datos, 'optimizaciones': [plan.pk, ajeno.pk]})
        self.assertTrue(respuesta.context['form'].has_error('optimizaciones', 'invalid_choice'))
        self.assertFalse(Proyecto.objects.exists())
        self.assertEqual(self.client.post(self.alta, datos).status_code, 302)
        proyecto = Proyecto.objects.get()
        self.assertEqual((proyecto.estado, proyecto.fecha_inicio, proyecto.fecha_fin, proyecto.cliente_id),
                         ('planificacion', self.hoy, None, None))
        self.assertEqual(list(proyecto.optimizacion_set.all()), [plan])
        self.assertEqual(self.client.post(self.alta, {'nombre': 'Sin asociaciones'}).status_code, 302)
        self.assertEqual(Proyecto.objects.latest('pk').estado, 'planificacion')

    def test_acciones_permitidas_preservan_fechas_optimizaciones_y_presupuesto_emitido(self):
        for origen, accion, destino in (
            ('planificacion', 'iniciar', 'en_proceso'), ('planificacion', 'cancelar', 'cancelado'),
            ('en_proceso', 'completar', 'completado'), ('en_proceso', 'cancelar', 'cancelado'),
        ):
            with self.subTest(origen=origen, accion=accion):
                proyecto = self.nuevo(estado=origen, fecha_inicio=self.ayer, fecha_fin=self.ayer,
                                      descripcion='  Descripción ñ\r\n' * 20)
                plan = self.plan(proyecto=proyecto, cliente=self.cliente, num_tableros=2, precio_tablero=30)
                presupuesto = Presupuesto.objects.create(
                    usuario=self.usuario, proyecto=proyecto, cliente=self.cliente, numero=f'PRE-PRO-{proyecto.pk}',
                    precio_tablero=30, costo_total=60, estado='emitido', fecha_validez=self.hoy,
                    detalle_emitido={'cliente': None, 'optimizaciones': []},
                )
                presupuesto.optimizaciones.add(plan)
                antes = Proyecto.objects.values().get(pk=proyecto.pk)
                plan_antes = Optimizacion.objects.values().get(pk=plan.pk)
                cotizado = Presupuesto.objects.values().get(pk=presupuesto.pk)
                self.assertContains(self.client.get(self.ruta('detalle', proyecto)), 'data-proyecto-estado="atrasado"')
                self.assertRedirects(self.estado(proyecto, accion, origen), self.ruta('detalle', proyecto))
                despues = Proyecto.objects.values().get(pk=proyecto.pk)
                self.assertEqual(despues, {**antes, 'estado': destino, 'fecha_actualizacion': despues['fecha_actualizacion']})
                self.assertEqual(Optimizacion.objects.values().get(pk=plan.pk), plan_antes)
                self.assertEqual(Presupuesto.objects.values().get(pk=presupuesto.pk), cotizado)
                self.assertEqual(list(presupuesto.optimizaciones.all()), [plan])

    def test_inicio_manual_sin_fecha_y_advertencia_si_es_futura(self):
        for fecha in (None, self.manana):
            with self.subTest(fecha=fecha):
                proyecto = self.nuevo(fecha_inicio=fecha)
                detalle = self.client.get(self.ruta('detalle', proyecto))
                if fecha:
                    self.assertContains(detalle, 'El inicio está previsto para el')
                else:
                    self.assertNotContains(detalle, 'El inicio está previsto para el')
                self.assertContains(detalle, 'Iniciar proyecto')
                self.assertEqual(self.estado(proyecto, 'iniciar', 'planificacion').status_code, 302)
                proyecto.refresh_from_db()
                self.assertEqual((proyecto.estado, proyecto.fecha_inicio), ('en_proceso', fecha))
                self.assertIsNone(proyecto.fecha_fin)

    def test_post_csrf_propiedad_y_rechazo_de_transiciones_invalidas(self):
        proyecto = self.nuevo()
        ruta = self.ruta('cambiar_estado', proyecto)
        self.assertEqual(self.client.get(ruta, {'accion': 'iniciar', 'estado_origen': 'planificacion'}).status_code, 405)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.usuario)
        self.assertEqual(csrf.post(ruta, {'accion': 'iniciar', 'estado_origen': 'planificacion'}).status_code, 403)
        ajeno = self.nuevo(usuario=self.otro)
        for accion in ('iniciar', 'completar', 'cancelar'):
            self.assertEqual(self.estado(ajeno, accion, 'planificacion').status_code, 404)
        self.assertEqual(self.estado(proyecto, 'completar', 'planificacion').status_code, 302)
        self.assertEqual(self.estado(proyecto, ['iniciar', 'cancelar'], 'planificacion').status_code, 400)
        self.assertEqual(self.estado(proyecto, 'desconocida', 'planificacion').status_code, 400)
        self.assertEqual(self.estado(proyecto, 'iniciar', ['planificacion'] * 2).status_code, 302)
        proyecto.refresh_from_db()
        self.assertEqual(proyecto.estado, 'planificacion')
        for estado in ('completado', 'cancelado'):
            final = self.nuevo(estado=estado, fecha_fin=self.ayer)
            detalle = self.client.get(self.ruta('detalle', final))
            self.assertNotContains(detalle, 'Confirmar inicio')
            self.assertNotContains(detalle, 'Cancelar proyecto')
            self.assertEqual(self.estado(final, 'iniciar', estado).status_code, 302)
            self.assertEqual(Proyecto.objects.get(pk=final.pk).estado, estado)
        self.usuario.perfil.puede_crear_proyectos = False
        self.usuario.perfil.save(update_fields=['puede_crear_proyectos'])
        self.assertRedirects(self.estado(proyecto, 'iniciar', 'planificacion'), reverse('cutless:index'))

    def test_edicion_rechaza_estado_y_revierte_formulario_obsoleto(self):
        proyecto = self.nuevo()
        ruta = self.ruta('editar', proyecto)
        revision = self.client.get(ruta).context['form']['revision'].value()
        antes = Proyecto.objects.values().get(pk=proyecto.pk)
        for estado in ('en_proceso', 'atrasado', 'cancelado'):
            respuesta = self.client.post(ruta, {'estado': estado, 'nombre': 'Nombre alterado'})
            self.assertContains(respuesta, 'El estado se cambia con las acciones')
            self.assertEqual(Proyecto.objects.values().get(pk=proyecto.pk), antes)
        self.assertEqual(self.estado(proyecto, 'iniciar', 'planificacion').status_code, 302)
        self.assertEqual(self.estado(proyecto, 'cancelar', 'planificacion').status_code, 302)
        respuesta = self.client.post(ruta, {'revision': revision, 'nombre': 'Nombre alterado'})
        self.assertContains(respuesta, 'El proyecto cambió')
        proyecto.refresh_from_db()
        self.assertEqual((proyecto.estado, proyecto.nombre), ('en_proceso', antes['nombre']))

    def test_atraso_por_fecha_filtros_y_historial_del_mismo_propietario(self):
        casos = {
            self.nuevo(nombre='Atrasado plan', fecha_fin=self.ayer): 'atrasado',
            self.nuevo(nombre='Atrasado activo', estado='en_proceso', fecha_fin=self.ayer): 'atrasado',
            self.nuevo(nombre='Hoy', fecha_inicio=self.hoy, fecha_fin=self.hoy): 'planificacion',
            self.nuevo(nombre='Sin final', estado='en_proceso'): 'en_proceso',
            self.nuevo(nombre='Mañana', estado='en_proceso', fecha_fin=self.manana): 'en_proceso',
            self.nuevo(nombre='Completado ayer', estado='completado', fecha_fin=self.ayer): 'completado',
            self.nuevo(nombre='Cancelado ayer', estado='cancelado', fecha_fin=self.ayer): 'cancelado',
        }
        self.nuevo(usuario=self.otro, nombre='Ajeno', fecha_fin=self.ayer)
        antes = list(Proyecto.objects.order_by('pk').values())
        for estado in set(casos.values()):
            with self.subTest(estado=estado):
                respuesta = self.client.get(self.lista, {'estado': estado})
                self.assertEqual({p.pk for p in respuesta.context['proyectos']},
                                 {p.pk for p, efectivo in casos.items() if efectivo == estado})
        filtrado = self.client.get(self.lista, {'estado': 'atrasado', 'busqueda': 'activo'})
        self.assertEqual([p.nombre for p in filtrado.context['proyectos']], ['Atrasado activo'])
        historial = reverse('cutless:historial_cliente', args=[self.cliente.pk])
        for ruta in (self.lista, historial):
            with CaptureQueriesContext(connection) as consultas:
                respuesta = self.client.get(ruta)
            self.assertEqual({p.pk: p.estado_efectivo for p in respuesta.context['proyectos']},
                             {p.pk: estado for p, estado in casos.items()})
            self.assertContains(respuesta, 'data-proyecto-estado="atrasado"', count=2)
            self.assertFalse(any(q['sql'].startswith('UPDATE') for q in consultas))
        self.assertEqual(list(Proyecto.objects.order_by('pk').values()), antes)
        queryset = Proyecto.objects.filter(usuario=self.usuario)
        with self.assertNumQueries(1):
            self.assertEqual(len(list(con_estado_efectivo(queryset, hoy=self.hoy))), len(casos))
        self.assertEqual(proyectos_atrasados(queryset, hoy=self.hoy).count(), 2)
        self.assertEqual(inicios_planificados(queryset, desde=self.hoy, hasta=self.hoy).count(), 1)
        self.assertEqual(finales_planificados(queryset, desde=self.hoy, hasta=self.manana).count(), 2)

    def test_reprogramacion_devuelve_estado_operativo_y_preserva_historia(self):
        inicio = self.ayer - timedelta(days=2)
        descripcion = '  Trabajo ñ\r\n' * 25
        nombre = 'Proyecto histórico ' * 3
        for estado in ('planificacion', 'en_proceso', 'completado', 'cancelado'):
            with self.subTest(estado=estado):
                proyecto = self.nuevo(estado=estado, nombre=nombre, descripcion=descripcion,
                                      fecha_inicio=inicio, fecha_fin=self.ayer)
                plan = self.plan(proyecto=proyecto)
                editar = self.ruta('editar', proyecto)
                inicial = self.client.get(editar)
                if estado in ('planificacion', 'en_proceso'):
                    self.assertContains(inicial, 'Estado operativo')
                visible = descripcion.replace('\r\n', '\n')
                self.assertEqual(self.client.post(editar, {'descripcion': visible, 'fecha_fin': self.hoy}).status_code, 302)
                self.assertContains(self.client.get(self.ruta('detalle', proyecto)), f'data-proyecto-estado="{estado}"')
                proyecto.refresh_from_db()
                self.assertEqual((proyecto.nombre, proyecto.descripcion, proyecto.cliente_id, proyecto.estado,
                                  proyecto.fecha_inicio, proyecto.fecha_fin),
                                 (nombre, descripcion, self.cliente.pk, estado, inicio, self.hoy))
                self.assertEqual(self.client.post(editar, {'fecha_fin': ''}).status_code, 302)
                proyecto.refresh_from_db()
                self.assertIsNone(proyecto.fecha_fin)
                self.assertEqual(list(proyecto.optimizacion_set.all()), [plan])
        invertido = self.nuevo(fecha_inicio=self.ayer, fecha_fin=inicio)
        self.assertEqual(self.client.post(self.ruta('editar', invertido), {'descripcion': 'Dato nuevo'}).status_code, 302)
        invertido.refresh_from_db()
        self.assertEqual((invertido.fecha_inicio, invertido.fecha_fin), (self.ayer, inicio))

    def test_limite_de_dia_en_chile_en_invierno_verano_y_cambio_de_hora(self):
        for instante in (datetime(2026, 1, 15, 3, tzinfo=UTC), datetime(2026, 7, 15, 4, tzinfo=UTC),
                         datetime(2026, 9, 6, 4, tzinfo=UTC)):
            with self.subTest(instante=instante), timezone.override('UTC'):
                fin = instante.date() - timedelta(days=1)
                proyecto = self.nuevo(fecha_fin=fin)
                detalle = self.ruta('detalle', proyecto)
                with patch('django.utils.timezone.now', return_value=instante - timedelta(seconds=1)) as reloj:
                    self.assertContains(self.client.get(detalle), 'data-proyecto-estado="planificacion"')
                    reloj.return_value = instante
                    self.assertContains(self.client.get(detalle), 'data-proyecto-estado="atrasado"')
                self.assertEqual(Proyecto.objects.get(pk=proyecto.pk).estado, 'planificacion')


class CicloProyectosConcurrenciaTests(TransactionTestCase):
    def setUp(self):
        self.usuario = User.objects.create_user('pro03_concurrencia')
        self.proyecto = Proyecto.objects.create(usuario=self.usuario, nombre='Proyecto concurrente')
        self.detalle = reverse('cutless:detalle_proyecto', args=[self.proyecto.pk])
        self.estado = reverse('cutless:cambiar_estado_proyecto', args=[self.proyecto.pk])
        self.editar = reverse('cutless:editar_proyecto', args=[self.proyecto.pk])
        self.otras_sesiones = [Client(), Client()]
        for cliente in (self.client, *self.otras_sesiones):
            cliente.force_login(self.usuario)

    @skipUnlessDBFeature('has_select_for_update')
    def test_inicio_y_cancelacion_o_finalizacion_y_cancelacion_se_serializan(self):
        for origen, accion, destino in (('planificacion', 'iniciar', 'en_proceso'),
                                        ('en_proceso', 'completar', 'completado')):
            with self.subTest(origen=origen):
                Proyecto.objects.filter(pk=self.proyecto.pk).update(estado=origen)
                inicio = Barrier(2, timeout=10)

                def registrar(cliente, solicitada):
                    close_old_connections()
                    try:
                        inicio.wait()
                        return cliente.post(
                            self.estado, {'accion': solicitada, 'estado_origen': origen}, follow=True,
                        ).content.decode()
                    finally:
                        close_old_connections()

                with ThreadPoolExecutor(max_workers=2) as grupo:
                    salidas = list(grupo.map(registrar, self.otras_sesiones, (accion, 'cancelar')))
                self.assertEqual(sum('Esa acción ya no está disponible' in salida for salida in salidas), 1)
                self.proyecto.refresh_from_db()
                self.assertIn(self.proyecto.estado, (destino, 'cancelado'))

    @skipUnlessDBFeature('has_select_for_update')
    def test_edicion_abierta_no_sobrescribe_transicion_ni_asignacion_concurrente(self):
        plan = Optimizacion.objects.create(usuario=self.usuario, ancho_tablero=122, alto_tablero=244,
                                          piezas='Frente,20,30,1')
        agregar = reverse('cutless:agregar_optimizaciones_proyecto', args=[self.proyecto.pk])
        for ruta, datos in (
            (agregar, {'optimizaciones': [plan.pk]}),
            (self.estado, {'accion': 'iniciar', 'estado_origen': 'planificacion'}),
        ):
            with self.subTest(ruta=ruta):
                revision = self.client.get(self.editar).context['form']['revision'].value()
                intentando = Event()

                def editar_obsoleto():
                    close_old_connections()
                    try:
                        intentando.set()
                        return self.otras_sesiones[0].post(self.editar, {
                            'revision': revision, 'nombre': 'Edición antigua', 'seleccion_optimizaciones': '1',
                        })
                    finally:
                        close_old_connections()

                with ThreadPoolExecutor(max_workers=1) as grupo:
                    with transaction.atomic():
                        self.assertEqual(self.client.post(ruta, datos).status_code, 302)
                        futuro = grupo.submit(editar_obsoleto)
                        self.assertTrue(intentando.wait(10))
                    self.assertContains(futuro.result(timeout=10), 'El proyecto cambió')
        self.proyecto.refresh_from_db()
        self.assertEqual((self.proyecto.estado, self.proyecto.nombre), ('en_proceso', 'Proyecto concurrente'))
        self.assertEqual(list(self.proyecto.optimizacion_set.all()), [plan])
