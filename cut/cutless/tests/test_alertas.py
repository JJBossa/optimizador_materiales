from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.contrib.sessions.models import Session
from django.core import mail
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from cutless.models import Cliente, Presupuesto, Proyecto
from cutless.services.alertas import TAMANO_PAGINA, obtener_alertas


class AlertasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user('alertas_propietario')
        cls.otro = User.objects.create_user('alertas_otro')
        cls.cliente = Cliente.objects.create(
            usuario=cls.usuario, nombre='Cliente privado sintético', rut='12345678-9',
            email='cliente@example.test', telefono='+56912345678', direccion='Calle privada',
        )

    def setUp(self):
        self.hoy = date(2026, 11, 24)
        self.reloj = self.enterContext(patch('django.utils.timezone.now', return_value=datetime(2026, 11, 24, 12, tzinfo=UTC)))
        self.api = reverse('cutless:api_alertas')
        self.centro = reverse('cutless:centro_alertas')
        self.client.force_login(self.usuario)

    def presupuesto(self, estado, dias, **datos):
        return Presupuesto.objects.create(**{
            'usuario': self.usuario, 'numero': f'PRE-{Presupuesto.objects.count()}', 'estado': estado,
            'fecha_validez': self.hoy + timedelta(days=dias), 'precio_tablero': 20, 'costo_total': 100,
            'detalle_emitido': {'cliente': {'correo': 'cotizado@example.test'}, 'optimizaciones': []},
            **datos,
        })

    def proyecto(self, estado='planificacion', *, inicio=None, fin=None, **datos):
        return Proyecto.objects.create(**{
            'usuario': self.usuario, 'nombre': 'Armario sintético', 'estado': estado,
            'fecha_inicio': self.hoy + timedelta(days=inicio) if inicio is not None else None,
            'fecha_fin': self.hoy + timedelta(days=fin) if fin is not None else None,
            **datos,
        })

    def tipos(self, categoria=''):
        resultado = self.client.get(self.api, {'categoria': categoria}).json()
        return {alerta['id']: alerta['tipo'] for alerta in resultado['alertas']}

    def test_presupuestos_ventanas_estados_efectivos_y_precedencia(self):
        casos = (
            ('vencido', -7, 'vencido'), ('vencido', -8, None), ('vencido', -1, 'vencido'),
            ('emitido', -1, 'vencido'), ('enviado', -7, 'vencido'), ('enviado', -8, None),
            ('emitido', 0, 'vence_hoy'), ('enviado', 0, 'vence_hoy'),
            ('emitido', 1, 'proximo_vencer'), ('enviado', 3, 'proximo_vencer'),
            ('enviado', 4, None), ('emitido', 4, 'pendiente_envio'),
            ('borrador', -1, None), ('aceptado', 0, None), ('rechazado', 1, None),
        )
        esperado = {}
        for estado, dias, tipo in casos:
            presupuesto = self.presupuesto(estado, dias)
            if tipo:
                esperado[f'presupuestos:{presupuesto.pk}'] = f'presupuesto_{tipo}'
        resultado = self.client.get(self.api).json()
        self.assertEqual(resultado['total'], len(esperado))
        self.assertEqual(self.tipos(), esperado)
        mensajes = [alerta['mensaje'] for alerta in resultado['alertas']]
        self.assertTrue(any('vence mañana' in mensaje for mensaje in mensajes))
        self.assertTrue(any('vence en 3 días' in mensaje for mensaje in mensajes))
        self.assertTrue(any('Su validez terminaba el 17/11/2026' in mensaje for mensaje in mensajes))

    def test_proyectos_precedencia_fechas_ausentes_y_estados_finales(self):
        casos = (
            ('planificacion', -2, -1, 'atrasado'), ('en_proceso', None, -9, 'atrasado'),
            ('planificacion', -1, 0, 'finaliza_hoy'), ('planificacion', 0, 0, 'finaliza_hoy'),
            ('planificacion', -2, 1, 'inicio_pendiente'), ('planificacion', -1, None, 'inicio_pendiente'),
            ('planificacion', 0, 3, 'inicia_hoy'), ('en_proceso', None, 3, 'proximo_finalizar'),
            ('en_proceso', None, 4, None), ('planificacion', None, None, None),
            ('completado', -2, -1, None), ('cancelado', -1, 0, None), ('en_proceso', -2, None, None),
        )
        esperado = {}
        for estado, inicio, fin, tipo in casos:
            proyecto = self.proyecto(estado, inicio=inicio, fin=fin)
            if tipo:
                esperado[f'proyectos:{proyecto.pk}'] = f'proyecto_{tipo}'
        self.assertEqual(self.client.get(self.api).json()['total'], len(esperado))
        self.assertEqual(self.tipos(), esperado)

    def test_orden_paginacion_aislamiento_y_numero_constante_de_consultas(self):
        antiguos = [self.presupuesto('enviado', -5), self.presupuesto('vencido', -6)]
        self.proyecto(fin=0)
        Proyecto.objects.bulk_create([
            Proyecto(usuario=self.usuario, nombre='Nombre repetido', fecha_inicio=self.hoy) for _ in range(104)
        ])
        Proyecto.objects.bulk_create([
            Proyecto(usuario=self.otro, nombre='Nombre ajeno', fecha_inicio=self.hoy) for _ in range(110)
        ])
        self.usuario.perfil  # Cargar el perfil antes de medir las consultas de negocio.
        with self.assertNumQueries(2):
            resumen = obtener_alertas(self.usuario, solo_total=True)
        self.assertEqual(resumen['total'], 107)
        self.assertNotIn('alertas', resumen)
        with self.assertNumQueries(3):
            primera = obtener_alertas(self.usuario)
        self.assertEqual(len(primera['alertas']), TAMANO_PAGINA)
        self.assertEqual(primera['alertas'][0]['id'], f'presupuestos:{antiguos[1].pk}')
        ultimos = []
        pagina = 1
        while pagina:
            resultado = self.client.get(self.api, {'pagina': pagina, 'categoria': 'proyectos'}).json()
            self.assertEqual(resultado['total'], 107)
            ultimos.extend(alerta['id'] for alerta in resultado['alertas'])
            pagina = resultado['siguiente']
        self.assertEqual(len(set(ultimos)), len(ultimos))
        self.assertEqual(len(ultimos), 105)
        self.assertEqual(primera, obtener_alertas(self.usuario))

    def test_permisos_preferencias_y_limites_de_propietario_incluso_como_admin(self):
        self.presupuesto('enviado', 0)
        self.proyecto(inicio=0)
        self.presupuesto('enviado', 0, usuario=self.otro)
        self.proyecto(inicio=0, usuario=self.otro, nombre='Proyecto ajeno')
        perfil = self.usuario.perfil
        for presupuestos, proyectos, categorias in (
            (False, True, ['proyectos']), (True, False, ['presupuestos']), (False, False, []),
        ):
            perfil.puede_crear_presupuestos = presupuestos
            perfil.puede_crear_proyectos = proyectos
            perfil.save()
            resultado = self.client.get(self.api, {'usuario': self.otro.pk}).json()
            self.assertEqual(list(resultado['categorias']), categorias)
            self.assertEqual(resultado['total'], len(categorias))
        perfil.rol = 'admin'
        perfil.preferencias_menu = {'presupuestos': False, 'proyectos': False}
        perfil.notificar_presupuesto_creado = False
        perfil.notificar_proyecto_creado = False
        perfil.save()
        self.assertEqual(self.client.get(self.api).json()['total'], 2)
        self.assertContains(self.client.get(reverse('cutless:lista_proyectos')), 'data-alertas-boton')
        perfil.rol = 'usuario'
        perfil.save()
        self.usuario.is_superuser = True
        self.usuario.save()
        self.assertEqual(self.client.get(self.api).json()['total'], 2)
        perfil.notificaciones_pantalla = False
        perfil.save()
        with self.assertNumQueries(0):
            self.assertEqual(obtener_alertas(self.usuario, solo_total=True)['total'], 0)
        self.assertNotContains(self.client.get(reverse('cutless:lista_proyectos')), 'data-alertas-boton')
        self.assertEqual(self.client.get(self.centro).status_code, 403)
        self.assertEqual(self.client.get(self.api).json()['total'], 0)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_solo_lectura_escape_proteccion_cache_y_sesion(self):
        presupuesto = self.presupuesto('emitido', -1, cliente=self.cliente, notas='Nota privada')
        proyecto = self.proyecto(fin=-1, cliente=self.cliente, nombre='<img src=x onerror=alert(1)> «Ñ»')
        sesion = self.client.session.session_key
        vence = Session.objects.get(pk=sesion).expire_date
        antes = Presupuesto.objects.values().get(pk=presupuesto.pk)
        antes_proyecto = Proyecto.objects.values().get(pk=proyecto.pk)
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(self.api)
            pagina = self.client.get(self.centro)
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('UPDATE', 'INSERT', 'DELETE')) for q in consultas))
        for documento in (respuesta, pagina):
            self.assertIn('no-store', documento['Cache-Control'])
            self.assertIn('private', documento['Cache-Control'])
        self.assertEqual(pagina.status_code, 200)
        self.assertIn('no-store', pagina['Cache-Control'])
        self.assertNotContains(pagina, '<img src=x onerror=alert(1)>')
        self.assertContains(pagina, '&lt;img src=x onerror=alert(1)&gt;')
        self.assertNotIn('cliente@example.test', respuesta.content.decode())
        self.assertNotIn('cotizado@example.test', respuesta.content.decode())
        self.assertNotIn('Nota privada', respuesta.content.decode())
        self.assertEqual(Presupuesto.objects.values().get(pk=presupuesto.pk), antes)
        self.assertEqual(Proyecto.objects.values().get(pk=proyecto.pk), antes_proyecto)
        self.assertEqual(Session.objects.get(pk=sesion).expire_date, vence)
        self.assertFalse(list(get_messages(respuesta.wsgi_request)))
        self.assertFalse(mail.outbox)
        self.assertEqual(self.client.post(self.api).status_code, 405)
        self.assertEqual(self.client.get(self.api, {'pagina': '0'}).status_code, 400)
        self.client.logout()
        anonimo = self.client.get(self.api)
        self.assertEqual(anonimo.status_code, 401)
        self.assertIn('no-store', anonimo['Cache-Control'])
        self.assertEqual(self.client.get(self.centro).status_code, 302)
        self.assertNotContains(self.client.get(reverse('usuarios:login')), 'data-alertas-boton')

    def test_actualizacion_al_resolver_condiciones_en_rutas_existentes(self):
        proyecto = self.proyecto(inicio=-1)
        presupuesto = self.presupuesto('emitido', 4)
        atrasado = self.proyecto('en_proceso', fin=-1)
        confirmacion = reverse('cutless:cambiar_estado_proyecto', args=[proyecto.pk])
        self.assertEqual(self.client.get(self.api).json()['total'], 3)
        self.client.post(confirmacion, {'accion': 'iniciar', 'estado_origen': 'planificacion'})
        self.assertNotIn(f'proyectos:{proyecto.pk}', self.tipos())
        self.client.post(reverse('cutless:editar_presupuesto', args=[presupuesto.pk]),
                         {'estado': 'enviado', 'estado_origen': 'emitido'})
        self.assertNotIn(f'presupuestos:{presupuesto.pk}', self.tipos())
        editar = reverse('cutless:editar_proyecto', args=[atrasado.pk])
        self.client.post(editar, {'fecha_fin': self.hoy})
        self.assertEqual(self.tipos()[f'proyectos:{atrasado.pk}'], 'proyecto_finaliza_hoy')
        self.client.post(reverse('cutless:cambiar_estado_proyecto', args=[atrasado.pk]),
                         {'accion': 'completar', 'estado_origen': 'en_proceso'})
        self.assertEqual(self.client.get(self.api).json()['total'], 0)

    @override_settings(TIME_ZONE='UTC')
    def test_toma_una_sola_fecha_de_chile_en_verano_e_invierno(self):
        for instante in (datetime(2026, 1, 15, 3, tzinfo=UTC), datetime(2026, 7, 15, 4, tzinfo=UTC)):
            self.reloj.return_value = instante - timedelta(seconds=1)
            fecha = instante.date() - timedelta(days=1)
            presupuesto = self.presupuesto('enviado', 0, fecha_validez=fecha)
            self.assertEqual(self.tipos()[f'presupuestos:{presupuesto.pk}'], 'presupuesto_vence_hoy')
            self.reloj.return_value = instante
            with patch('cutless.services.alertas.fecha_comercial', return_value=instante.date()) as reloj_comercial:
                self.assertEqual(self.tipos()[f'presupuestos:{presupuesto.pk}'], 'presupuesto_vencido')
                reloj_comercial.assert_called_once()
            presupuesto.refresh_from_db()
            self.assertEqual(presupuesto.estado, 'enviado')
