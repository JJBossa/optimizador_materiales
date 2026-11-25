from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from cutless.models import Cliente, Optimizacion, Proyecto


class FechasProyectoTests(TestCase):
    hoy = date(2026, 7, 15)
    datos = {'nombre': 'Proyecto de prueba', 'estado': 'planificacion'}

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user('proyectos_val02')
        cls.usuario.perfil.puede_crear_proyectos = True
        cls.usuario.perfil.save(update_fields=['puede_crear_proyectos'])

    def setUp(self):
        self.client.force_login(self.usuario)
        self.alta = reverse('cutless:crear_proyecto')
        self.reloj = self.enterContext(patch('django.utils.timezone.now', return_value=datetime(2026, 7, 15, 12, tzinfo=UTC)))
        self.ayer = self.hoy - timedelta(days=1)
        self.manana = self.hoy + timedelta(days=1)

    def optimizacion(self, **kwargs):
        return Optimizacion.objects.create(
            ancho_tablero=122, alto_tablero=244, piezas='Puerta,40,50,1',
            **{'usuario': self.usuario, **kwargs},
        )

    def proyecto(self, **kwargs):
        return Proyecto.objects.create(**{'nombre': 'Proyecto guardado', 'usuario': self.usuario, **kwargs})

    def test_alta_acepta_hoy_manana_y_fechas_opcionales(self):
        formulario = self.client.get(self.alta).context['form']
        for campo in ('fecha_inicio', 'fecha_fin'):
            self.assertEqual(formulario[campo].field.widget.attrs['min'], self.hoy.isoformat())
            self.assertIsNone(formulario[campo].value())
            self.assertFalse(formulario[campo].field.required)

        for inicio, fin in ((None, None), (self.hoy, None), (None, self.hoy),
                            (self.hoy, self.hoy), (self.hoy, self.manana), (self.manana, self.manana)):
            with self.subTest(inicio=inicio, fin=fin):
                respuesta = self.client.post(self.alta, {
                    **self.datos, 'fecha_inicio': inicio or '', 'fecha_fin': fin or '',
                })
                self.assertEqual(respuesta.status_code, 302)
                guardado = Proyecto.objects.latest('pk')
                self.assertEqual((guardado.fecha_inicio, guardado.fecha_fin), (inicio, fin))

    def test_post_de_alta_rechaza_ayer_orden_invalido_y_formato_sin_crear(self):
        plan = self.optimizacion()
        casos = (
            (self.ayer, self.hoy, 'fecha_inicio', 'fecha_pasada'),
            (self.hoy, self.ayer, 'fecha_fin', 'fecha_pasada'),
            (self.manana, self.hoy, 'fecha_fin', 'fin_anterior_al_inicio'),
            ('2026-02-30', self.hoy, 'fecha_inicio', 'invalid'),
            (self.hoy, 'no-es-fecha', 'fecha_fin', 'invalid'),
        )
        for inicio, fin, campo, codigo in casos:
            with self.subTest(campo=campo, codigo=codigo):
                respuesta = self.client.post(self.alta, {
                    **self.datos, 'fecha_inicio': inicio, 'fecha_fin': fin, 'optimizaciones': [plan.pk],
                })
                self.assertEqual(respuesta.status_code, 200)
                form = respuesta.context['form']
                self.assertTrue(form.has_error(campo, codigo), form.errors)
                self.assertEqual(form['fecha_inicio'].value(), str(inicio))
                self.assertEqual(form['fecha_fin'].value(), str(fin))
                self.assertContains(respuesta, f'id="id_{campo}_error"')
                self.assertContains(respuesta, f'aria-describedby="id_{campo}_helptext id_{campo}_error"')
                self.assertTrue(respuesta.context['optimizaciones_info'][0]['seleccionada'])
                self.assertFalse(Proyecto.objects.exists())
                plan.refresh_from_db()
                self.assertIsNone(plan.proyecto_id)

    @override_settings(TIME_ZONE='UTC')
    def test_medianoche_chilena_en_invierno_y_verano_con_formulario_abierto(self):
        # La sesión y los ajustes del servidor pueden usar UTC.
        with timezone.override(UTC):
            for mes, medianoche_utc in ((1, 3), (7, 4)):
                anterior = date(2026, mes, 14)
                hoy = date(2026, mes, 15)
                instante = datetime(2026, mes, 15, medianoche_utc, tzinfo=UTC)
                with self.subTest(mes=mes):
                    self.reloj.return_value = instante - timedelta(seconds=1)
                    form = self.client.get(self.alta).context['form']
                    self.assertEqual(form['fecha_inicio'].field.widget.attrs['min'], anterior.isoformat())
                    self.assertEqual(self.client.post(self.alta, {
                        **self.datos, 'fecha_inicio': anterior, 'fecha_fin': anterior,
                    }).status_code, 302)

                    self.reloj.return_value = instante
                    atrasado = self.client.post(self.alta, {
                        **self.datos, 'fecha_inicio': anterior, 'fecha_fin': anterior,
                    }).context['form']
                    for campo in ('fecha_inicio', 'fecha_fin'):
                        self.assertTrue(atrasado.has_error(campo, 'fecha_pasada'))
                        self.assertEqual(atrasado[campo].field.widget.attrs['min'], hoy.isoformat())
                    self.assertEqual(self.client.post(self.alta, {
                        **self.datos, 'fecha_inicio': hoy, 'fecha_fin': hoy,
                    }).status_code, 302)

    def test_edicion_conserva_fechas_historicas_y_actualiza_los_otros_campos(self):
        inicio = self.hoy - timedelta(days=60)
        largo = 'Proyecto histórico ' * 3
        proyecto = self.proyecto(nombre=largo, fecha_inicio=inicio, fecha_fin=self.ayer)
        editar = reverse('cutless:editar_proyecto', args=[proyecto.pk])
        plan = self.optimizacion(proyecto=proyecto)
        siguiente = self.optimizacion()
        cliente = Cliente.objects.create(usuario=self.usuario, nombre='Cliente local')
        respuesta = self.client.get(editar)
        for campo, fecha in (('fecha_inicio', inicio), ('fecha_fin', self.ayer)):
            self.assertNotIn('min', respuesta.context['form'][campo].field.widget.attrs)
            self.assertContains(respuesta, f'value="{fecha.isoformat()}"')
        self.assertContains(respuesta, 'Puedes conservar la fecha guardada')
        self.assertContains(respuesta, 'maxlength="30"')

        datos = {**self.datos, 'nombre': largo, 'descripcion': 'Trabajo revisado',
                 'revision': respuesta.context['form']['revision'].value(),
                 'cliente': cliente.pk, 'optimizaciones': [siguiente.pk],
                 'fecha_inicio': inicio, 'fecha_fin': self.ayer}
        self.assertEqual(self.client.post(editar, datos).status_code, 302)
        proyecto.refresh_from_db()
        self.assertEqual((proyecto.fecha_inicio, proyecto.fecha_fin), (inicio, self.ayer))
        self.assertEqual((proyecto.nombre, proyecto.descripcion, proyecto.estado, proyecto.cliente_id),
                         (largo, 'Trabajo revisado', 'planificacion', cliente.pk))
        self.assertEqual(list(proyecto.optimizacion_set.values_list('pk', flat=True)), [siguiente.pk])
        plan.refresh_from_db()
        self.assertIsNone(plan.proyecto_id)

        # Omitir una fecha conserva el valor. Enviar un campo vacío lo borra explícitamente.
        del datos['fecha_fin']
        datos['revision'] = self.client.get(editar).context['form']['revision'].value()
        self.assertEqual(self.client.post(editar, {**datos, 'fecha_inicio': ''}).status_code, 302)
        proyecto.refresh_from_db()
        self.assertEqual((proyecto.fecha_inicio, proyecto.fecha_fin), (None, self.ayer))

    def test_edicion_invalida_representa_los_valores_del_post_y_guarda_nada(self):
        inicio = self.hoy - timedelta(days=30)
        proyecto = self.proyecto(fecha_inicio=inicio, fecha_fin=self.ayer)
        editar = reverse('cutless:editar_proyecto', args=[proyecto.pk])
        plan = self.optimizacion(proyecto=proyecto)
        libre = self.optimizacion()
        antes = Proyecto.objects.values().get(pk=proyecto.pk)
        base = {**self.datos, 'descripcion': 'Edición pendiente', 'optimizaciones': [libre.pk],
                'revision': self.client.get(editar).context['form']['revision'].value()}
        for fechas, campo, codigo in (
            ({'fecha_inicio': self.ayer, 'fecha_fin': self.ayer}, 'fecha_inicio', 'fecha_pasada'),
            ({'fecha_inicio': '', 'fecha_fin': inicio}, 'fecha_fin', 'fecha_pasada'),
            ({'fecha_inicio': self.hoy, 'fecha_fin': self.ayer}, 'fecha_fin', 'fin_anterior_al_inicio'),
            ({'fecha_inicio': inicio, 'fecha_fin': '2026-04-31'}, 'fecha_fin', 'invalid'),
        ):
            with self.subTest(fechas=fechas):
                respuesta = self.client.post(editar, {**base, **fechas})
                form = respuesta.context['form']
                self.assertTrue(form.has_error(campo, codigo), form.errors)
                for nombre, fecha in fechas.items():
                    self.assertEqual(form[nombre].value(), str(fecha))
                    self.assertContains(respuesta, f'value="{fecha}"')
                if codigo == 'invalid':
                    self.assertContains(respuesta, 'Valor recibido «2026-04-31».')
                self.assertContains(respuesta, 'Edición pendiente')
                self.assertEqual(Proyecto.objects.values().get(pk=proyecto.pk), antes)
                plan.refresh_from_db()
                libre.refresh_from_db()
                self.assertEqual(plan.proyecto_id, proyecto.pk)
                self.assertIsNone(libre.proyecto_id)
        self.assertEqual(self.client.post(editar, {
            **base, 'fecha_inicio': inicio, 'fecha_fin': self.hoy,
        }).status_code, 302)
        proyecto.refresh_from_db()
        self.assertEqual((proyecto.fecha_inicio, proyecto.fecha_fin), (inicio, self.hoy))

    def test_rango_historico_invertido_se_conserva_solo_si_ambas_fechas_siguen_iguales(self):
        fin = self.hoy - timedelta(days=30)
        proyecto = self.proyecto(fecha_inicio=self.ayer, fecha_fin=fin)
        editar = reverse('cutless:editar_proyecto', args=[proyecto.pk])
        self.assertEqual(self.client.post(editar, self.datos).status_code, 302)
        proyecto.refresh_from_db()
        self.assertEqual((proyecto.fecha_inicio, proyecto.fecha_fin), (self.ayer, fin))
        error = self.client.post(editar, {**self.datos, 'fecha_inicio': self.hoy})
        self.assertTrue(error.context['form'].has_error('fecha_fin', 'fin_anterior_al_inicio'))
        self.assertEqual(self.client.post(editar, {**self.datos, 'fecha_fin': self.hoy}).status_code, 302)
        proyecto.refresh_from_db()
        self.assertEqual((proyecto.fecha_inicio, proyecto.fecha_fin), (self.ayer, self.hoy))

    def test_val01b_y_permisos_siguen_aplicandose_al_post(self):
        otro = User.objects.create_user('otro_proyectos_val02')
        proyecto = self.proyecto(fecha_inicio=self.ayer)
        ajeno = self.proyecto(usuario=otro, fecha_inicio=self.ayer)
        cliente_ajeno = Cliente.objects.create(usuario=otro, nombre='Cliente ajeno')
        plan_ajeno = self.optimizacion(usuario=otro)
        editar = reverse('cutless:editar_proyecto', args=[proyecto.pk])
        respuesta = self.client.post(editar, {
            **self.datos, 'nombre': 'ñ' * 31, 'cliente': cliente_ajeno.pk, 'optimizaciones': [plan_ajeno.pk],
        })
        form = respuesta.context['form']
        self.assertTrue(form.has_error('nombre', 'max_length'))
        self.assertTrue(form.has_error('cliente', 'invalid_choice'))
        self.assertTrue(form.has_error('optimizaciones', 'invalid_choice'))
        plan_ajeno.refresh_from_db()
        self.assertIsNone(plan_ajeno.proyecto_id)
        url_ajena = reverse('cutless:editar_proyecto', args=[ajeno.pk])
        self.assertEqual(self.client.post(url_ajena, {**self.datos, 'fecha_inicio': self.hoy}).status_code, 404)
        ajeno.refresh_from_db()
        self.assertEqual(ajeno.fecha_inicio, self.ayer)
        self.usuario.perfil.puede_crear_proyectos = False
        self.usuario.perfil.save(update_fields=['puede_crear_proyectos'])
        for url in (editar, self.alta):
            self.assertRedirects(self.client.post(url, self.datos), reverse('cutless:index'), fetch_redirect_response=False)
        proyecto.refresh_from_db()
        self.assertEqual(proyecto.nombre, 'Proyecto guardado')
