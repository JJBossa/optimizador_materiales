from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cutless.models import Cliente, Material, Optimizacion, Plantilla, Presupuesto, Proyecto
from cutless.pieces import parsear_piezas_desde_texto, piezas_como_csv, serializar_piezas


class LimitesNombresTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user('titular')
        self.usuario.perfil.rol = 'admin'
        self.usuario.perfil.save(update_fields=['rol'])
        self.client.force_login(self.usuario)
        self.trabajo = {
            'unidad_medida': 'cm', 'ancho': 122, 'alto': 244, 'margen_corte': 3,
            'form-TOTAL_FORMS': 1, 'form-INITIAL_FORMS': 0,
            'form-0-nombre': 'Puerta', 'form-0-ancho': 40, 'form-0-alto': 50, 'form-0-cantidad': 1,
        }
        self.plantilla = {
            'categoria': 'muebles', 'unidad_medida': 'cm', 'ancho_tablero': 122,
            'alto_tablero': 244, 'piezas': 'Puerta,40,50,1', 'margen_corte': 3,
        }

    def verificar_exceso(self, url, datos, campo='nombre', formulario='form'):
        respuesta = self.client.post(url, datos)
        self.assertEqual(respuesta.status_code, 200)
        form = respuesta.context[formulario]
        self.assertTrue(form.has_error(campo, 'max_length'), form.errors)
        self.assertEqual(form[campo].value(), datos[campo])
        self.assertContains(respuesta, 'Usa como máximo')

    def test_alta_y_edicion_de_catalogos_preservan_nombres_historicos(self):
        casos = (
            ('proyecto', Proyecto, {'estado': 'planificacion'}, 'descripcion'),
            ('cliente', Cliente, {}, 'notas'),
            ('material', Material, {'ancho': 122, 'alto': 244, 'unidad_medida': 'cm'}, 'descripcion'),
            ('plantilla', Plantilla, self.plantilla, 'descripcion'),
        )
        for ruta, modelo, datos, otro_campo in casos:
            with self.subTest(ruta=ruta):
                alta = reverse(f'cutless:crear_{ruta}')
                exacto = 'Á' * 28 + '🪵'
                historico = '  ' + 'Histórico ' * 4 + '\r\n'
                self.assertContains(self.client.get(alta), 'maxlength="30"')
                self.verificar_exceso(alta, {**datos, 'nombre': exacto + 'é'})
                self.assertFalse(modelo.objects.exists())
                self.assertEqual(self.client.post(alta, {**datos, 'nombre': exacto}).status_code, 302)
                registro = modelo.objects.get(usuario=self.usuario)
                self.assertEqual(registro.nombre, exacto)

                modelo.objects.filter(pk=registro.pk).update(nombre=historico)
                editar = reverse(f'cutless:editar_{ruta}', args=[registro.pk])
                self.assertContains(self.client.get(editar), 'maxlength="30"')
                self.assertContains(self.client.get(editar), 'Puedes conservar el nombre guardado.')
                self.verificar_exceso(editar, {**datos, 'nombre': exacto + 'é', otro_campo: 'Se rechaza'})
                registro.refresh_from_db()
                self.assertEqual(registro.nombre, historico)
                self.assertEqual(getattr(registro, otro_campo), '')

                # El navegador descarta CR y LF de un input de una línea.
                self.assertEqual(self.client.post(editar, {
                    **datos, 'nombre': historico[:-2], otro_campo: 'Se conserva',
                }).status_code, 302)
                registro.refresh_from_db()
                self.assertEqual(registro.nombre, historico)
                self.assertEqual(getattr(registro, otro_campo), 'Se conserva')
                self.assertEqual(self.client.post(editar, {**datos, 'nombre': exacto}).status_code, 302)
                registro.refresh_from_db()
                self.assertEqual(registro.nombre, exacto)

    def test_trabajo_se_crea_edita_renombra_y_duplica_con_el_mismo_maximo(self):
        campo = 'nombre_optimizacion'
        alta = reverse('cutless:index')
        exacto = 'ñ' * 28 + '🪵'
        self.assertContains(self.client.get(alta), 'maxlength="30"')
        self.verificar_exceso(alta, {**self.trabajo, campo: exacto + 'a'}, campo, 'tablero_form')
        self.assertFalse(Optimizacion.objects.exists())
        self.assertEqual(self.client.post(alta, {**self.trabajo, campo: exacto}).status_code, 302)
        plan = Optimizacion.objects.get(usuario=self.usuario)
        self.assertEqual(plan.nombre, exacto)

        historico = '  Taller  ' + 'é' * 51 + ' '
        Optimizacion.objects.filter(pk=plan.pk).update(nombre=historico)
        editar = reverse('cutless:editar_optimizacion', args=[plan.pk])
        renombrar = reverse('cutless:renombrar_optimizacion', args=[plan.pk])
        duplicar = reverse('cutless:duplicar_optimizacion', args=[plan.pk])
        self.assertContains(self.client.get(editar), 'Puedes conservar el nombre guardado.')
        self.verificar_exceso(editar, {**self.trabajo, campo: exacto + 'a'}, campo, 'tablero_form')
        self.verificar_exceso(renombrar, {campo: exacto + 'a'}, campo)
        self.assertEqual(self.client.post(editar, {**self.trabajo, 'margen_corte': 4, campo: historico}).status_code, 302)
        plan.refresh_from_db()
        self.assertEqual(plan.nombre, historico)
        self.assertAlmostEqual(plan.margen_corte, 0.4)
        duplicado = self.client.get(duplicar)
        self.assertContains(duplicado, 'Acorta el nombre original')
        self.assertEqual(duplicado.context['tablero_form'][campo].value(), historico)
        datos = {**self.trabajo, campo: historico, 'origen_medidas': duplicado.context['tablero_form']['origen_medidas'].value()}
        self.verificar_exceso(alta, datos, campo, 'tablero_form')
        self.assertEqual(Optimizacion.objects.count(), 1)
        self.assertEqual(self.client.post(alta, {**datos, campo: ''}).status_code, 302)
        self.assertTrue(Optimizacion.objects.filter(nombre='').exists())
        self.assertEqual(self.client.post(renombrar, {campo: exacto}).status_code, 302)
        plan.refresh_from_db()
        self.assertEqual(plan.nombre, exacto)

    def test_limite_de_piezas_en_optimizador_y_csv_de_plantilla(self):
        alta = reverse('cutless:index')
        exacto = 'ñ' * 28 + '🪵'
        self.assertEqual(self.client.get(alta).context['pieza_formset'].forms[0].fields['nombre'].max_length, 30)
        respuesta = self.client.post(alta, {**self.trabajo, 'form-0-nombre': exacto + 'a'})
        self.assertTrue(respuesta.context['pieza_formset'][0].has_error('nombre', 'max_length'))
        self.assertFalse(Optimizacion.objects.exists())
        self.assertEqual(self.client.post(alta, {**self.trabajo, 'form-0-nombre': exacto}).status_code, 302)

        alta_plantilla = reverse('cutless:crear_plantilla')
        respuesta = self.client.post(alta_plantilla, {**self.plantilla, 'nombre': 'Plantilla',
                                                     'piezas': f'{exacto}a,40,50,1'})
        self.assertContains(respuesta, 'Pieza 1: Usa como máximo 30 caracteres')
        self.assertFalse(Plantilla.objects.exists())
        self.assertEqual(self.client.post(alta_plantilla, {
            **self.plantilla, 'nombre': 'Plantilla', 'piezas': f'{exacto},40,50,1',
        }).status_code, 302)

    def test_pieza_historica_de_optimizacion_sobrevive_edicion_y_reindexacion(self):
        historico = '  Frente, "norte" ' + 'ñ' * 20 + '\r\nPiso superior '
        guardado = serializar_piezas([
            {'nombre': 'Puerta corta', 'ancho': 40, 'alto': 50, 'cantidad': 1},
            {'nombre': historico, 'ancho': 40, 'alto': 50, 'cantidad': 1},
        ])
        plan = Optimizacion.objects.create(
            usuario=self.usuario, ancho_tablero=122, alto_tablero=244, piezas=guardado,
        )
        editar = reverse('cutless:editar_optimizacion', args=[plan.pk])
        alta = reverse('cutless:index')
        visible = historico.replace('\r\n', '\n')
        fila = {'nombre': visible, 'ancho': 40, 'alto': 50, 'cantidad': 1}
        fila_adicional = {f'form-1-{campo}': valor for campo, valor in fila.items()}
        ambas = {**self.trabajo, **fila_adicional, 'form-0-nombre': 'Puerta corta', 'form-TOTAL_FORMS': 2}
        self.assertEqual(self.client.post(editar, {**ambas, 'margen_corte': 4}).status_code, 302)
        plan.refresh_from_db()
        self.assertEqual(plan.piezas, guardado)

        reindexada = {**self.trabajo, 'form-0-nombre': visible, 'form-0-ancho': 45}
        duplicada = self.client.post(editar, {**reindexada, **fila_adicional, 'form-TOTAL_FORMS': 2})
        self.assertTrue(duplicada.context['pieza_formset'][1].has_error('nombre', 'max_length'))
        renombrada = self.client.post(editar, {**reindexada, 'form-0-nombre': 'X' * 31})
        self.assertTrue(renombrada.context['pieza_formset'][0].has_error('nombre', 'max_length'))
        plan.refresh_from_db()
        self.assertEqual(plan.piezas, guardado)

        self.assertEqual(self.client.post(editar, reindexada).status_code, 302)
        plan.refresh_from_db()
        pieza, = parsear_piezas_desde_texto(plan.piezas, estricto=True)
        self.assertEqual((pieza['nombre'], pieza['ancho']), (historico, 45))
        copiar = self.client.get(reverse('cutless:duplicar_optimizacion', args=[plan.pk]))
        firma = copiar.context['tablero_form']['origen_medidas'].value()
        datos = {**reindexada, 'origen_medidas': firma}
        respuesta = self.client.post(alta, datos)
        self.assertTrue(respuesta.context['pieza_formset'][0].has_error('nombre', 'max_length'))
        self.assertEqual(Optimizacion.objects.count(), 1)
        self.assertEqual(self.client.post(alta, {**datos, 'form-0-nombre': 'P' * 30}).status_code, 302)

    def test_pieza_historica_en_csv_se_edita_sin_alterarla_y_la_copia_exige_30(self):
        historico = '  Puerta, "Norte" ' + 'é' * 16 + '\r\nNivel 2 '
        guardado = serializar_piezas([{'nombre': historico, 'ancho': 40, 'alto': 50, 'cantidad': 1}])
        plantilla = Plantilla.objects.create(
            usuario=self.usuario, nombre='Plantilla', ancho_tablero=122, alto_tablero=244, piezas=guardado,
        )
        editar = reverse('cutless:editar_plantilla', args=[plantilla.pk])
        usar = reverse('cutless:usar_plantilla', args=[plantilla.pk])
        csv = piezas_como_csv(guardado).replace('\r\n', '\n')
        datos = {**self.plantilla, 'nombre': plantilla.nombre, 'piezas': csv}
        self.assertTemplateUsed(self.client.get(usar), 'cutless/index.html')
        self.assertEqual(self.client.post(editar, {**datos, 'descripcion': 'Nueva descripción'}).status_code, 302)
        plantilla.refresh_from_db()
        self.assertEqual(plantilla.piezas, guardado)
        self.assertContains(self.client.post(editar, {**datos, 'piezas': csv * 2}), 'Pieza 2: Usa como máximo 30')
        self.assertEqual(self.client.post(editar, {**datos, 'piezas': csv.replace(',50.0,1', ',50.0,2')}).status_code, 302)
        plantilla.refresh_from_db()
        pieza, = plantilla.get_piezas_list()
        self.assertEqual((pieza['nombre'], pieza['cantidad']), (historico, 2))

        plantilla.es_predefinida = True
        plantilla.usuario = None
        plantilla.save(update_fields=['usuario', 'es_predefinida'])
        self.assertContains(self.client.post(editar, datos), 'Pieza 1: Usa como máximo 30')
        self.assertEqual(Plantilla.objects.count(), 1)
        self.assertEqual(self.client.post(editar, {**datos, 'piezas': 'P' * 30 + ',40,50,1'}).status_code, 302)
        plantilla.refresh_from_db()
        self.assertTrue(plantilla.es_predefinida)
        self.assertEqual(plantilla.get_piezas_list()[0]['nombre'], historico)

    def test_plantilla_predefinida_larga_se_usa_pero_la_copia_exige_nombre_nuevo(self):
        original = Plantilla.objects.create(nombre='P' * 31, es_predefinida=True, ancho_tablero=122,
                                            alto_tablero=244, piezas=self.plantilla['piezas'])
        editar = reverse('cutless:editar_plantilla', args=[original.pk])
        usar = reverse('cutless:usar_plantilla', args=[original.pk])
        self.assertContains(self.client.get(editar), 'Acorta el nombre original')
        self.assertTemplateUsed(self.client.get(usar), 'cutless/index.html')
        self.verificar_exceso(editar, {**self.plantilla, 'nombre': original.nombre})
        self.assertEqual(Plantilla.objects.count(), 1)
        self.assertEqual(self.client.post(editar, {**self.plantilla, 'nombre': 'P' * 30}).status_code, 302)
        original.refresh_from_db()
        self.assertEqual(original.nombre, 'P' * 31)
        self.assertTrue(original.es_predefinida)
        self.assertTrue(Plantilla.objects.filter(usuario=self.usuario, nombre='P' * 30).exists())

    def test_plantilla_desde_optimizacion_y_recarga_de_ubicacion(self):
        csv_historico = 'Puerta ' + 'X' * 24 + ',40,50,1'
        plan = Optimizacion.objects.create(usuario=self.usuario, ancho_tablero=122, alto_tablero=244, piezas=csv_historico)
        alta = f"{reverse('cutless:crear_plantilla')}?optimizacion={plan.pk}"
        self.assertContains(self.client.get(alta), 'maxlength="30"')
        self.verificar_exceso(alta, {**self.plantilla, 'nombre': 'P' * 31})
        self.assertContains(self.client.post(alta, {**self.plantilla, 'nombre': 'P' * 30, 'piezas': csv_historico}),
                            'Pieza 1: Usa como máximo 30')
        self.assertFalse(Plantilla.objects.exists())
        self.assertEqual(self.client.post(alta, {**self.plantilla, 'nombre': 'P' * 30}).status_code, 302)

        alta_cliente = reverse('cutless:crear_cliente')
        datos = {'nombre': 'C' * 31, 'direccion_pais': 'CL'}
        respuesta = self.client.post(alta_cliente, {**datos, 'actualizar_ubicacion': '1'})
        self.assertEqual(respuesta.context['form']['nombre'].value(), datos['nombre'])
        self.assertFalse(Cliente.objects.exists())
        self.verificar_exceso(alta_cliente, datos)
        self.assertFalse(Cliente.objects.exists())

    def test_alta_rapida_desde_presupuestos_y_seleccion_de_cliente_historico(self):
        plan = Optimizacion.objects.create(usuario=self.usuario, ancho_tablero=122, alto_tablero=244,
                                           piezas=self.plantilla['piezas'], num_tableros=1)
        datos = {'optimizaciones': [plan.pk], 'precio_tablero': '100', 'mano_obra': '0',
                 'fecha_validez': timezone.localdate(), 'estado': 'borrador', 'notas': 'Original'}
        alta = reverse('cutless:crear_presupuesto')
        campo = 'nombre_cliente_nuevo'
        exacto = 'Empresa Ñ ' + 'é' * 20
        self.assertContains(self.client.get(alta), 'maxlength="30"')
        self.verificar_exceso(alta, {**datos, campo: exacto + 'a'}, campo)
        self.assertFalse(Cliente.objects.exists())
        self.assertFalse(Presupuesto.objects.exists())
        self.assertEqual(self.client.post(alta, {**datos, campo: exacto}).status_code, 302)
        presupuesto = Presupuesto.objects.get()
        self.assertEqual(presupuesto.cliente.nombre, exacto)

        editar = reverse('cutless:editar_presupuesto', args=[presupuesto.pk])
        self.assertContains(self.client.get(editar), 'maxlength="30"')
        self.verificar_exceso(editar, {**datos, campo: exacto + 'a', 'notas': 'Rechazado'}, campo)
        presupuesto.refresh_from_db()
        self.assertEqual(presupuesto.notas, 'Original')
        self.assertEqual(Cliente.objects.count(), 1)
        self.assertEqual(self.client.post(editar, {**datos, campo: 'Z' * 30}).status_code, 302)
        nuevo = Cliente.objects.get(nombre='Z' * 30)
        Cliente.objects.filter(pk=nuevo.pk).update(nombre='Z' * 31)
        self.assertEqual(self.client.post(editar, {**datos, 'cliente': nuevo.pk, 'notas': 'Selección'}).status_code, 302)
        presupuesto.refresh_from_db()
        self.assertEqual(presupuesto.cliente.nombre, 'Z' * 31)
        self.assertEqual(presupuesto.notas, 'Selección')

        ajeno = User.objects.create_user('ajeno')
        cliente_ajeno = Cliente.objects.create(usuario=ajeno, nombre='Histórico ' * 15)
        respuesta = self.client.post(editar, {**datos, 'cliente': cliente_ajeno.pk})
        self.assertTrue(respuesta.context['form'].has_error('cliente', 'invalid_choice'))
        presupuesto.refresh_from_db()
        self.assertEqual(presupuesto.cliente_id, nuevo.pk)
        ajeno.perfil.puede_crear_presupuestos = False
        ajeno.perfil.save(update_fields=['puede_crear_presupuestos'])
        self.client.force_login(ajeno)
        self.assertRedirects(self.client.post(alta, {**datos, campo: exacto}), reverse('cutless:index'))
        self.assertEqual(Cliente.objects.count(), 3)

    def test_presupuesto_emitido_conserva_nombres_historicos_y_piezas(self):
        largo = 'Mueble ñ ' * 5
        cliente = Cliente.objects.create(usuario=self.usuario, nombre=largo)
        piezas = serializar_piezas([{'nombre': largo, 'ancho': 40, 'alto': 50, 'cantidad': 1}])
        plan = Optimizacion.objects.create(usuario=self.usuario, nombre=largo, ancho_tablero=122,
                                           alto_tablero=244, piezas=piezas, num_tableros=1)
        datos = {'optimizaciones': [plan.pk], 'cliente': cliente.pk, 'precio_tablero': '100',
                 'mano_obra': '0', 'fecha_validez': timezone.localdate(), 'estado': 'enviado'}
        self.assertEqual(self.client.post(reverse('cutless:crear_presupuesto'), datos).status_code, 302)
        presupuesto = Presupuesto.objects.get()
        detalle = presupuesto.detalle_emitido
        self.assertEqual(detalle['cliente']['nombre'], largo)
        self.assertEqual(detalle['optimizaciones'][0]['etiqueta'], plan.etiqueta)
        self.assertEqual(detalle['optimizaciones'][0]['piezas'], piezas)
        Cliente.objects.filter(pk=cliente.pk).update(nombre='Cliente nuevo')
        Optimizacion.objects.filter(pk=plan.pk).update(nombre='Trabajo nuevo', piezas='Puerta,40,50,1')
        editar = reverse('cutless:editar_presupuesto', args=[presupuesto.pk])
        self.assertEqual(self.client.post(editar, {'estado': 'aceptado', 'nombre_cliente_nuevo': largo}).status_code, 302)
        presupuesto.refresh_from_db()
        self.assertEqual(presupuesto.detalle_emitido, detalle)
        self.assertEqual(Cliente.objects.count(), 1)

    def test_nombre_historico_no_habilita_editar_trabajo_ajeno(self):
        ajeno = User.objects.create_user('otro_titular')
        plan = Optimizacion.objects.create(usuario=ajeno, nombre='N' * 51, ancho_tablero=122,
                                           alto_tablero=244, piezas=self.plantilla['piezas'])
        for ruta in ('editar_optimizacion', 'renombrar_optimizacion', 'duplicar_optimizacion'):
            with self.subTest(ruta=ruta):
                url = reverse(f'cutless:{ruta}', args=[plan.pk])
                self.assertEqual(self.client.post(url, {**self.trabajo, 'nombre_optimizacion': plan.nombre}).status_code, 404)
        plan.refresh_from_db()
        self.assertEqual(plan.nombre, 'N' * 51)

    def test_modelos_del_catalogo_en_django_admin_aplican_los_maximos(self):
        self.usuario.is_staff = self.usuario.is_superuser = True
        self.usuario.save(update_fields=['is_staff', 'is_superuser'])
        material = {'nombre': 'M' * 30, 'ancho': 122, 'alto': 244, 'unidad_medida': 'cm'}
        alta_material = reverse('admin:cutless_material_add')
        self.assertContains(self.client.get(alta_material), 'maxlength="30"')
        self.assertContains(self.client.post(alta_material, {**material, 'nombre': 'M' * 31}), 'Usa como máximo 30')
        self.assertEqual(self.client.post(alta_material, material).status_code, 302)
        guardado = Material.objects.get()
        Material.objects.filter(pk=guardado.pk).update(nombre='M' * 31)
        editar_material = reverse('admin:cutless_material_change', args=[guardado.pk])
        self.assertEqual(self.client.post(editar_material, {**material, 'nombre': 'M' * 31, 'descripcion': 'Nueva'}).status_code, 302)
        guardado.refresh_from_db()
        self.assertEqual((guardado.nombre, guardado.descripcion), ('M' * 31, 'Nueva'))

        trabajo = {
            'usuario': self.usuario.pk, 'nombre': 'T' * 30, 'unidad_medida': 'cm',
            'ancho_tablero': 122, 'alto_tablero': 244, 'margen_corte': '0.3', 'piezas': self.plantilla['piezas'],
            'aprovechamiento_total': 0, 'num_tableros': 1, 'area_usada_total': 0, 'desperdicio_total': 0, 'mano_obra': 0,
        }
        alta_trabajo = reverse('admin:cutless_optimizacion_add')
        self.assertContains(self.client.get(alta_trabajo), 'maxlength="30"')
        self.assertContains(self.client.post(alta_trabajo, {**trabajo, 'nombre': 'T' * 31}), 'Usa como máximo 30')
        self.assertContains(self.client.post(alta_trabajo, {**trabajo, 'piezas': 'P' * 31 + ',40,50,1'}),
                            'Pieza 1: Usa como máximo 30')
        respuesta = self.client.post(alta_trabajo, trabajo)
        self.assertEqual(respuesta.status_code, 302, respuesta.context and respuesta.context['adminform'].form.errors)
        plan = Optimizacion.objects.get()
        piezas_historicas = '  ' + 'P' * 31 + ' ,40,50,1'
        Optimizacion.objects.filter(pk=plan.pk).update(nombre='T' * 31, piezas=piezas_historicas)
        editar_trabajo = reverse('admin:cutless_optimizacion_change', args=[plan.pk])
        self.assertEqual(self.client.post(editar_trabajo, {
            **trabajo, 'nombre': 'T' * 31, 'piezas': piezas_historicas, 'num_tableros': 2,
        }).status_code, 302)
        plan.refresh_from_db()
        self.assertEqual((plan.nombre, plan.num_tableros), ('T' * 31, 2))
        self.assertEqual(plan.piezas, piezas_historicas)
        self.assertContains(self.client.post(editar_trabajo, {**trabajo, 'piezas': 'Q' * 31 + ',40,50,1'}),
                            'Pieza 1: Usa como máximo 30')
        self.assertEqual(self.client.post(editar_trabajo, {
            **trabajo, 'nombre': 'T' * 31, 'piezas': piezas_historicas.replace(',50,1', ',50,2'),
        }).status_code, 302)
        plan.refresh_from_db()
        pieza, = parsear_piezas_desde_texto(plan.piezas, estricto=True)
        self.assertEqual((pieza['nombre'], pieza['cantidad']), ('  ' + 'P' * 31 + ' ', 2))
