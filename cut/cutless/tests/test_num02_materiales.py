from decimal import Decimal

from django.contrib.auth.models import Permission, User
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from cutless.forms import TableroForm
from cutless.models import Material, Optimizacion, Plantilla


class MaterialesFormulariosTests(TestCase):
    def setUp(self):
        self.superusuario = User.objects.create_superuser('num02_admin')
        self.client.force_login(self.superusuario)
        self.datos = dict(nombre='Material de prueba', ancho='122', alto='244',
                          unidad_medida='cm', precio='20.25', descripcion='Descripción original')

    def material(self, **valores):
        return Material.objects.create(**{
            **self.datos, 'ancho': 122.0, 'alto': 244.0, 'usuario': self.superusuario, **valores,
        })

    def ruta(self, admin, material=None):
        if admin:
            return (reverse('admin:cutless_material_change', args=[material.pk]) if material
                    else reverse('admin:cutless_material_add'))
        return (reverse('cutless:editar_material', args=[material.pk]) if material
                else reverse('cutless:crear_material'))

    def enviar(self, admin, datos, material=None, **admin_extra):
        if admin:
            datos = {**datos, 'usuario': self.superusuario.pk, '_save': 'Guardar', **admin_extra}
        return self.client.post(self.ruta(admin, material), datos)

    def formulario(self, respuesta, admin):
        return respuesta.context['adminform'].form if admin else respuesta.context['form']

    def iniciales(self, admin, material):
        respuesta = self.client.get(self.ruta(admin, material))
        form = self.formulario(respuesta, admin)
        return {campo: form[campo].value() for campo in self.datos}

    def comprobar_guardado(self, admin, original, **cambios):
        valores = {**self.datos, **cambios}
        respuesta = self.enviar(admin, valores, original)
        self.assertEqual(respuesta.status_code, 302)
        guardado = Material.objects.get(pk=original.pk) if original else Material.objects.latest('pk')
        self.assertEqual(guardado.usuario, self.superusuario)
        self.assertFalse(guardado.es_predefinido)
        return guardado

    def test_ambas_rutas_aceptan_coma_y_punto_en_alta_y_edicion(self):
        for admin in (False, True):
            for editar in (False, True):
                for decimal in ('12,5', '12.5'):
                    with self.subTest(admin=admin, editar=editar, decimal=decimal):
                        original = self.material() if editar else None
                        guardado = self.comprobar_guardado(admin, original, ancho=decimal, precio=decimal)
                        self.assertEqual((guardado.ancho, guardado.alto, guardado.precio),
                                         (12.5, 244.0, Decimal('12.50')))

    def test_ambas_rutas_aceptan_extremos_y_conservan_precio_nulo_cero_y_maximo(self):
        for admin in (False, True):
            for entrada, precio in (('', None), ('0', Decimal('0')), ('99999999,99', Decimal('99999999.99'))):
                with self.subTest(admin=admin, entrada=entrada):
                    material = self.comprobar_guardado(admin, None, ancho='10', alto='300', precio=entrada)
                    self.assertEqual((material.ancho, material.alto, material.precio), (10.0, 300.0, precio))

    def test_unidades_publicas_y_cm_en_admin_incluso_al_cambiar_la_presentacion(self):
        for unidad, ancho, alto in (('cm', '122.1250', '244'), ('mm', '1221.25', '2440'), ('m', '1.22125', '2.44')):
            with self.subTest(unidad=unidad):
                publico = self.comprobar_guardado(False, None, ancho=ancho, alto=alto, unidad_medida=unidad)
                admin = self.comprobar_guardado(True, self.material(unidad_medida='in'),
                                                 ancho='122,1250', alto='244', unidad_medida=unidad)
                for material in (publico, admin):
                    self.assertEqual((material.ancho, material.alto, material.unidad_medida), (122.125, 244.0, unidad))
        pagina = self.client.get(self.ruta(True))
        for texto in ('Ancho (cm)', 'Alto (cm)', 'Unidad de presentación'):
            self.assertContains(pagina, texto)

    def test_entradas_invalidas_conservan_formulario_y_no_escriben_parcialmente(self):
        casos = {
            'ancho': ('0', '-1', '9.99', '301', '100000000', '1.000', '1,000', 'NaN', 'Infinity', '1e2', '12cm', '9' * 310),
            'alto': ('-0.01', '300.01', '', '1_22'),
            'precio': ('-0.01', '100000000', '12.3456', '1.000', '1,000', 'NaN', '1e2', '12 pesos'),
            'unidad_medida': ('km',),
        }
        original = self.material(ancho=122.125, nombre='Original')
        for admin in (False, True):
            for editar in (False, True):
                for campo, entradas in casos.items():
                    for entrada in entradas:
                        with self.subTest(admin=admin, editar=editar, campo=campo, entrada=entrada):
                            datos = {**self.datos, 'nombre': 'Nombre aún sin guardar', campo: entrada}
                            respuesta = self.enviar(admin, datos, original if editar else None)
                            self.assertEqual(respuesta.status_code, 200)
                            form = self.formulario(respuesta, admin)
                            self.assertTrue(form.has_error(campo), form.errors)
                            for clave, valor in datos.items():
                                self.assertEqual(form[clave].value(), valor)
                            for clave in ('ancho', 'alto', 'precio'):
                                self.assertEqual(form[clave].field.widget.input_type, 'text')
                                self.assertEqual(form[clave].field.widget.attrs['inputmode'], 'decimal')
                            self.assertEqual(Material.objects.count(), 1)
                            original.refresh_from_db()
                            self.assertEqual((original.nombre, original.ancho, original.alto, original.precio),
                                             ('Original', 122.125, 244.0, Decimal('20.25')))

    def test_edicion_de_metadatos_preserva_lados_originales_y_costo_del_plan(self):
        for admin in (False, True):
            for unidad, ancho, alto in (
                ('cm', 122.1234567, 244.1234567), ('mm', 122.125, 244.125),
                ('m', 122.125, 244.125), ('in', 122.125, 244.125),
                ('ft', 122.125, 244.125), ('ft', 122.125, 300.0),
            ):
                with self.subTest(admin=admin, unidad=unidad, alto=alto):
                    original = self.material(ancho=ancho, alto=alto, unidad_medida=unidad)
                    plan = Optimizacion.objects.create(
                        usuario=self.superusuario, material=original, ancho_tablero=ancho, alto_tablero=alto,
                        precio_tablero=Decimal('32.15'), mano_obra=Decimal('10.25'), piezas='Pieza,20,30,1',
                    )
                    presupuesto = plan.presupuestos.create(
                        usuario=self.superusuario, precio_tablero=Decimal('42.25'), costo_total=Decimal('50.00'),
                        fecha_validez='2026-11-30', numero=f'PRE-NUM02-{plan.pk}',
                    )
                    datos = self.iniciales(admin, original)
                    datos.update(nombre='Nombre editado', descripcion='Descripción editada')
                    self.assertEqual(self.enviar(admin, datos, original).status_code, 302)
                    original.refresh_from_db()
                    plan.refresh_from_db()
                    presupuesto.refresh_from_db()
                    self.assertEqual((original.nombre, original.ancho, original.alto), ('Nombre editado', ancho, alto))
                    self.assertEqual((plan.material_id, plan.ancho_tablero, plan.alto_tablero), (original.pk, ancho, alto))
                    self.assertEqual((plan.precio_tablero, plan.mano_obra), (Decimal('32.15'), Decimal('10.25')))
                    self.assertEqual((presupuesto.precio_tablero, presupuesto.costo_total),
                                     (Decimal('42.25'), Decimal('50.00')))
                    self.assertEqual(list(presupuesto.optimizaciones.all()), [plan])

    def test_editar_un_solo_lado_preserva_el_otro_y_cambiar_unidad_publica_revalida(self):
        original = self.material(ancho=122.1234567, alto=244.1234567, unidad_medida='ft')
        datos = self.iniciales(False, original)
        self.assertEqual(self.enviar(False, {**datos, 'ancho': '4.1'}, original).status_code, 302)
        original.refresh_from_db()
        self.assertEqual((original.ancho, original.alto), (124.968, 244.1234567))
        self.assertEqual(self.enviar(False, {**datos, 'unidad_medida': 'cm'}, original).status_code, 200)
        original.refresh_from_db()
        self.assertEqual((original.ancho, original.alto, original.unidad_medida), (124.968, 244.1234567, 'ft'))

        original = self.material(ancho=12.2, alto=24.4, unidad_medida='mm')
        datos = self.iniciales(False, original)
        self.assertEqual(self.enviar(False, {**datos, 'unidad_medida': 'cm'}, original).status_code, 302)
        original.refresh_from_db()
        self.assertEqual((original.ancho, original.alto, original.unidad_medida), (122.0, 244.0, 'cm'))

    def test_edicion_de_metadatos_no_reescribe_precio_historico_en_la_base(self):
        tabla = connection.ops.quote_name(Material._meta.db_table)

        def precio_en_base(material):
            with connection.cursor() as cursor:
                cursor.execute(f'SELECT CAST(precio AS TEXT) FROM {tabla} WHERE id = %s', [material.pk])
                return cursor.fetchone()[0]

        for admin in (False, True):
            with self.subTest(admin=admin):
                original = self.material(precio=Decimal('12.3456'))
                previo = precio_en_base(original)
                self.assertEqual(previo, '12.3456' if connection.vendor == 'sqlite' else '12.35')
                original.refresh_from_db()
                self.assertEqual(original.precio, Decimal('12.35'))
                datos = {**self.iniciales(admin, original), 'nombre': 'Nombre editado'}
                self.assertEqual(self.enviar(admin, datos, original).status_code, 302)
                self.assertEqual(precio_en_base(original), previo)

    def test_historicos_invalidos_se_advierten_se_conservan_y_admiten_correccion(self):
        for admin in (False, True):
            with self.subTest(admin=admin):
                original = self.material(ancho=9.99, precio=Decimal('-1.00'))
                pagina = self.client.get(self.ruta(admin, original))
                self.assertContains(pagina, 'La medida histórica está fuera de rango')
                self.assertContains(pagina, 'El precio histórico es inválido')
                datos = {**self.iniciales(admin, original), 'nombre': 'Revisado'}
                self.assertEqual(self.enviar(admin, datos, original).status_code, 302)
                original.refresh_from_db()
                self.assertEqual((original.nombre, original.ancho, original.precio), ('Revisado', 9.99, Decimal('-1.00')))
                rechazado = self.enviar(admin, {**datos, 'ancho': '9.98', 'precio': '-2'}, original)
                self.assertEqual(rechazado.status_code, 200)
                form = self.formulario(rechazado, admin)
                self.assertEqual(set(form.errors), {'ancho', 'precio'})
                original.refresh_from_db()
                self.assertEqual((original.ancho, original.precio), (9.99, Decimal('-1.00')))
                self.assertEqual(self.enviar(admin, {**datos, 'ancho': '10', 'precio': ''}, original).status_code, 302)
                original.refresh_from_db()
                self.assertEqual((original.ancho, original.precio), (10.0, None))

    def test_medida_historica_no_finita_requiere_correccion_en_ambas_rutas(self):
        for admin in (False, True):
            with self.subTest(admin=admin):
                original = self.material(ancho=float('inf'))
                self.assertContains(self.client.get(self.ruta(admin, original)),
                                    'Corrige la medida histórica para poder guardar')
                datos = self.iniciales(admin, original)
                respuesta = self.enviar(admin, {**datos, 'nombre': 'Sin guardar'}, original)
                self.assertEqual(respuesta.status_code, 200)
                self.assertTrue(self.formulario(respuesta, admin).has_error('ancho'))
                original.refresh_from_db()
                self.assertEqual((original.nombre, original.ancho), ('Material de prueba', float('inf')))
                self.assertEqual(self.enviar(admin, {**datos, 'ancho': '10'}, original).status_code, 302)

    def test_unidad_historica_invalida_requiere_seleccion_explicita(self):
        for admin in (False, True):
            with self.subTest(admin=admin):
                original = self.material(ancho=122.1234567, unidad_medida='km')
                pagina = self.client.get(self.ruta(admin, original))
                self.assertContains(pagina, 'Unidad histórica inválida. Selecciona una unidad.')
                datos = {**self.iniciales(admin, original), 'nombre': 'Nombre editado'}
                self.assertEqual(datos['unidad_medida'], '')
                respuesta = self.enviar(admin, datos, original)
                self.assertEqual(respuesta.status_code, 200)
                self.assertTrue(self.formulario(respuesta, admin).has_error('unidad_medida'))
                original.refresh_from_db()
                self.assertEqual((original.nombre, original.unidad_medida), ('Material de prueba', 'km'))
                self.assertEqual(self.enviar(admin, {**datos, 'unidad_medida': 'cm'}, original).status_code, 302)
                original.refresh_from_db()
                self.assertEqual((original.nombre, original.ancho, original.unidad_medida),
                                 ('Nombre editado', 122.1234567, 'cm'))

    def test_politicas_publicas_y_admin_para_propios_ajenos_y_compartidos(self):
        propietario = User.objects.create_user('num02_propietario')
        administrador = User.objects.create_user('num02_cutless', is_staff=True)
        administrador.perfil.rol = 'admin'
        administrador.perfil.save(update_fields=['rol'])
        staff = User.objects.create_user('num02_staff', is_staff=True)
        personal = self.material(usuario=propietario, nombre='Personal')
        compartido = self.material(usuario=None, es_predefinido=True, nombre='Compartido')
        propio_staff = self.material(usuario=staff, nombre='Del staff')
        permiso = Permission.objects.filter(content_type__app_label='cutless')
        staff.user_permissions.add(permiso.get(codename='view_material'))

        self.client.force_login(propietario)
        self.assertEqual(self.enviar(False, self.datos, personal).status_code, 302)
        self.assertEqual(self.enviar(False, self.datos, compartido).status_code, 403)
        self.assertRedirects(self.client.get(self.ruta(True)), reverse('admin:login') + '?next=' + self.ruta(True),
                             fetch_redirect_response=False)

        self.client.force_login(administrador)
        self.assertEqual(self.enviar(False, self.datos, compartido).status_code, 302)
        self.assertEqual(self.enviar(True, self.datos, compartido).status_code, 403)
        cambio = self.enviar(False, {**self.datos, 'nombre': 'Ajeno'}, personal)
        self.assertEqual(cambio.status_code, 404)

        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.ruta(True, propio_staff)).status_code, 200)
        self.assertEqual(self.enviar(True, self.datos, propio_staff).status_code, 403)
        staff.user_permissions.add(permiso.get(codename='change_material'), permiso.get(codename='add_material'))
        self.assertEqual(self.enviar(True, self.datos, propio_staff, usuario=staff.pk).status_code, 302)
        self.assertEqual(self.enviar(True, self.datos, None, usuario=staff.pk).status_code, 302)
        self.assertEqual(self.enviar(True, self.datos, compartido).status_code, 403)
        intento = self.enviar(True, {**self.datos, 'nombre': 'Bloqueado'}, personal)
        self.assertRedirects(intento, reverse('admin:index'), fetch_redirect_response=False)
        personal.refresh_from_db()
        compartido.refresh_from_db()
        self.assertEqual((personal.nombre, personal.usuario_id), (self.datos['nombre'], propietario.pk))
        self.assertEqual((compartido.usuario_id, compartido.es_predefinido), (None, True))

    def test_admin_conserva_campos_de_propiedad_al_crear_predefinidos(self):
        self.assertEqual(self.enviar(True, self.datos, None, usuario='', es_predefinido='on').status_code, 302)
        material = Material.objects.latest('pk')
        self.assertTrue(material.es_predefinido)
        self.assertIsNone(material.usuario)


class CatalogoOptimizacionTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user('num02_planes')
        self.client.force_login(self.usuario)
        self.material = Material.objects.create(usuario=self.usuario, nombre='Catálogo de prueba',
                                                ancho=122, alto=244, precio=Decimal('-0.01'))
        self.datos = {'unidad_medida': 'cm', 'ancho': '122', 'alto': '244', 'material': self.material.pk,
                      'form-TOTAL_FORMS': '1', 'form-INITIAL_FORMS': '0',
                      'form-0-ancho': '20', 'form-0-alto': '30', 'form-0-cantidad': '1'}

    def test_fallback_usa_solo_precio_valido_y_respetando_precio_explicito_y_cero(self):
        for catalogo, entrada, esperado in (
            (Decimal('12.50'), '', Decimal('12.50')), (Decimal('0'), '', Decimal('0')),
            (None, '', None), (Decimal('-0.01'), '0', Decimal('0')), (Decimal('-0.01'), '16.75', Decimal('16.75')),
        ):
            with self.subTest(catalogo=catalogo, entrada=entrada):
                Material.objects.filter(pk=self.material.pk).update(precio=catalogo)
                formulario = TableroForm({**self.datos, 'precio_tablero': entrada}, user=self.usuario)
                self.assertTrue(formulario.is_valid(), formulario.errors)
                self.assertEqual(formulario.datos_costos()['precio_tablero'], esperado)

    def test_precio_invalido_del_catalogo_bloquea_alta_y_edicion_sin_tocar_plan(self):
        opt = Optimizacion.objects.create(usuario=self.usuario, material=self.material, ancho_tablero=122,
                                          alto_tablero=244, piezas='Pieza,20,30,1', precio_tablero=Decimal('32.15'))
        for ruta in ('cutless:index', 'cutless:editar_optimizacion'):
            url = reverse(ruta, args=[opt.pk] if ruta.endswith('editar_optimizacion') else [])
            with self.subTest(ruta=ruta):
                respuesta = self.client.post(url, self.datos)
                self.assertContains(respuesta, 'El precio del material es inválido.')
                self.assertTrue(respuesta.context['tablero_form'].has_error('precio_tablero'))
                self.assertEqual(Optimizacion.objects.count(), 1)
                opt.refresh_from_db()
                self.assertEqual((opt.material_id, opt.precio_tablero), (self.material.pk, Decimal('32.15')))

    def test_alta_real_con_precio_explicito_valido_ante_catalogo_negativo(self):
        respuesta = self.client.post(reverse('cutless:index'), {**self.datos, 'precio_tablero': '17.25'})
        self.assertEqual(respuesta.status_code, 302)
        plan = Optimizacion.objects.get()
        self.assertEqual((plan.material_id, plan.precio_tablero), (self.material.pk, Decimal('17.25')))
        self.material.refresh_from_db()
        self.assertEqual(self.material.precio, Decimal('-0.01'))

    def test_no_asocia_material_personal_ajeno_y_admite_predefinido(self):
        otro = User.objects.create_user('num02_ajeno')
        self.material.usuario = otro
        self.material.precio = Decimal('19.25')
        self.material.save(update_fields=['usuario', 'precio'])
        formulario = TableroForm(self.datos, user=self.usuario)
        self.assertFalse(formulario.is_valid())
        self.assertTrue(formulario.has_error('material', 'invalid_choice'))
        self.material.es_predefinido = True
        self.material.save(update_fields=['es_predefinido'])
        formulario = TableroForm(self.datos, user=self.usuario)
        self.assertTrue(formulario.is_valid(), formulario.errors)
        self.assertEqual(formulario.datos_costos()['precio_tablero'], Decimal('19.25'))

    def test_catalogo_no_precarga_datos_invalidos_y_no_excluye_asociacion(self):
        Material.objects.filter(pk=self.material.pk).update(ancho=float('inf'))
        opt = Optimizacion.objects.create(usuario=self.usuario, ancho_tablero=122, alto_tablero=244,
                                          piezas='Pieza,20,30,1')
        plantilla = Plantilla.objects.create(usuario=self.usuario, nombre='Prueba', ancho_tablero=122,
                                             alto_tablero=244, piezas='Pieza,20,30,1')
        for url in (reverse('cutless:index'), reverse('cutless:editar_optimizacion', args=[opt.pk])):
            with self.subTest(url=url):
                respuesta = self.client.get(url)
                self.assertEqual(respuesta.status_code, 200)
                datos = respuesta.context['materiales_data'][str(self.material.pk)]
                self.assertEqual((datos['precio'], datos['ancho'], datos['alto']), (None, None, None))
                self.assertIn(self.material, respuesta.context['tablero_form'].fields['material'].queryset)

        plantilla_url = reverse('cutless:usar_plantilla', args=[plantilla.pk])
        respuesta = self.client.get(plantilla_url)
        self.assertEqual(respuesta.context['materiales_data'][str(self.material.pk)],
                         {'nombre': self.material.nombre, 'precio': None})
        self.usuario.perfil.puede_ver_historial_costos = False
        self.usuario.perfil.save(update_fields=['puede_ver_historial_costos'])
        respuesta = self.client.get(plantilla_url)
        self.assertEqual(respuesta.context['materiales_data'], {})
        self.assertNotIn('material', respuesta.context['tablero_form'].fields)
