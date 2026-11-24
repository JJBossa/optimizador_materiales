from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from cutless.forms import MaterialForm
from cutless.models import Cliente, Material, Optimizacion, Presupuesto, Proyecto


class GestionTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user('gestor')
        self.usuario.perfil.rol = 'admin'
        self.usuario.perfil.save()
        self.client.force_login(self.usuario)

    def test_material_en_metros_se_guarda_en_cm_y_se_edita_sin_escalar_otra_vez(self):
        datos = {'nombre': 'MDF', 'ancho': '1.22', 'alto': '2.44',
                 'unidad_medida': 'm', 'precio': '0', 'descripcion': ''}
        self.client.post(reverse('cutless:crear_material'), datos)
        material = Material.objects.get(usuario=self.usuario)
        self.assertAlmostEqual(material.ancho, 122)
        self.assertAlmostEqual(material.alto, 244)
        self.assertEqual(material.get_area(), 122 * 244)
        form = MaterialForm(instance=material)
        self.assertAlmostEqual(form['ancho'].value(), 1.22)
        self.client.post(reverse('cutless:editar_material', args=[material.pk]), datos)
        material.refresh_from_db()
        self.assertAlmostEqual(material.ancho, 122)
        response = self.client.get(reverse('cutless:lista_materiales'))
        self.assertNotContains(response, 'Sin precio')

    def test_material_no_acepta_cero_negativo_o_medidas_no_finitas(self):
        datos = {'nombre': 'Tablero', 'ancho': '100', 'alto': '200', 'unidad_medida': 'cm'}
        for cambio in ({'ancho': '0'}, {'alto': '-1'}, {'ancho': 'nan'}, {'precio': '-1'}):
            with self.subTest(cambio=cambio):
                self.assertFalse(MaterialForm({**datos, **cambio}).is_valid())

    def test_listas_y_formularios_sin_registros_se_renderizan(self):
        for grupo in ('presupuestos', 'proyectos', 'clientes', 'materiales'):
            with self.subTest(grupo=grupo):
                self.assertEqual(self.client.get(reverse('cutless:lista_' + grupo)).status_code, 200)
        for tipo in ('presupuesto', 'proyecto', 'cliente', 'material'):
            with self.subTest(tipo=tipo):
                self.assertEqual(self.client.get(reverse('cutless:crear_' + tipo)).status_code, 200)

    def test_detalles_edicion_y_seleccion_con_registros_se_renderizan(self):
        cliente = Cliente.objects.create(usuario=self.usuario, nombre='Cliente de prueba')
        proyecto = Proyecto.objects.create(usuario=self.usuario, cliente=cliente, nombre='Cocina')
        opt = Optimizacion.objects.create(usuario=self.usuario, ancho_tablero=122,
                                         alto_tablero=244, piezas='Puerta,40,50,1',
                                         precio_tablero=0, num_tableros=1)
        presupuesto = Presupuesto.objects.create(usuario=self.usuario, cliente=cliente,
                                                numero='PRUEBA', precio_tablero=0,
                                                costo_total=0, fecha_validez=date(2030, 1, 1))
        presupuesto.optimizaciones.add(opt)
        cliente_sin_relaciones = Cliente.objects.create(usuario=self.usuario, nombre='Sin asociaciones')
        rutas = [('detalle_presupuesto', presupuesto.pk), ('editar_presupuesto', presupuesto.pk),
                 ('detalle_proyecto', proyecto.pk), ('editar_proyecto', proyecto.pk),
                 ('historial_cliente', cliente.pk), ('editar_cliente', cliente.pk),
                 ('agregar_optimizaciones_proyecto', proyecto.pk),
                 ('agregar_optimizaciones_presupuesto', presupuesto.pk),
                 ('eliminar_cliente', cliente_sin_relaciones.pk), ('eliminar_proyecto', proyecto.pk)]
        for nombre, pk in rutas:
            with self.subTest(ruta=nombre):
                self.assertEqual(self.client.get(reverse('cutless:' + nombre, args=[pk])).status_code, 200)

    def test_historial_de_cliente_sin_proyectos_muestra_estado_vacio(self):
        cliente = Cliente.objects.create(usuario=self.usuario, nombre='Sin proyectos')
        respuesta = self.client.get(reverse('cutless:historial_cliente', args=[cliente.pk]))

        self.assertContains(respuesta, 'Este cliente aún no tiene optimizaciones ni proyectos asociados.')
        self.assertNotContains(respuesta, '>Ver proyecto</a>')

    def test_historial_enlaza_a_un_proyecto_sin_optimizaciones(self):
        cliente = Cliente.objects.create(usuario=self.usuario, nombre='Cliente de prueba')
        proyecto = Proyecto.objects.create(usuario=self.usuario, cliente=cliente, nombre='Proyecto vacío')
        historial = reverse('cutless:historial_cliente', args=[cliente.pk])
        detalle = reverse('cutless:detalle_proyecto', args=[proyecto.pk])

        respuesta = self.client.get(historial)
        self.assertContains(respuesta, '>Ver proyecto</a>', count=1)
        self.assertContains(respuesta, f'href="{detalle}"', count=1)

        respuesta = self.client.get(detalle)
        self.assertContains(respuesta, 'Este proyecto aún no tiene optimizaciones asociadas.')
        self.assertEqual(respuesta.context['proyecto'], proyecto)

    def test_historial_enlaza_cada_proyecto_y_conserva_el_resultado_individual(self):
        cliente = Cliente.objects.create(usuario=self.usuario, nombre='Cliente de prueba')
        cocina = Proyecto.objects.create(usuario=self.usuario, cliente=cliente, nombre='Cocina')
        oficina = Proyecto.objects.create(usuario=self.usuario, cliente=cliente, nombre='Oficina')
        plan = Optimizacion.objects.create(
            usuario=self.usuario, cliente=cliente, proyecto=oficina,
            ancho_tablero=122, alto_tablero=244, piezas='Puerta,40,50,1', num_tableros=1,
        )

        respuesta = self.client.get(reverse('cutless:historial_cliente', args=[cliente.pk]))
        self.assertContains(respuesta, '>Ver proyecto</a>', count=2)
        for proyecto in (cocina, oficina):
            detalle = reverse('cutless:detalle_proyecto', args=[proyecto.pk])
            self.assertContains(respuesta, f'href="{detalle}"', count=1)
        resultado = reverse('cutless:resultado', args=[plan.pk])
        self.assertContains(respuesta, f'href="{resultado}"', count=1)
        self.assertContains(respuesta, '>Ver resultado</a>', count=1)
        self.assertNotContains(respuesta, 'href="#" class="btn btn-sm btn-secondary"')

    def test_historial_y_detalle_aislan_proyectos_por_cliente_y_propietario(self):
        ajeno = User.objects.create_user('otro_gestor')
        ajeno.perfil.rol = 'admin'
        ajeno.perfil.save(update_fields=['rol'])
        cliente = Cliente.objects.create(usuario=self.usuario, nombre='Cliente propio')
        segundo_cliente = Cliente.objects.create(usuario=self.usuario, nombre='Segundo cliente')
        cliente_ajeno = Cliente.objects.create(usuario=ajeno, nombre='Cliente ajeno')
        propio = Proyecto.objects.create(usuario=self.usuario, cliente=cliente, nombre='Proyecto propio')
        otro_cliente = Proyecto.objects.create(usuario=self.usuario, cliente=segundo_cliente, nombre='Otro cliente')
        cruzado = Proyecto.objects.create(usuario=ajeno, cliente=cliente, nombre='Relación cruzada sintética')
        privado = Proyecto.objects.create(usuario=ajeno, cliente=cliente_ajeno, nombre='Proyecto privado')
        historial_ajeno = reverse('cutless:historial_cliente', args=[cliente_ajeno.pk])

        respuesta = self.client.get(reverse('cutless:historial_cliente', args=[cliente.pk]))
        self.assertQuerySetEqual(respuesta.context['proyectos'], [propio])
        self.assertContains(respuesta, '>Ver proyecto</a>', count=1)
        for proyecto in (otro_cliente, cruzado, privado):
            detalle = reverse('cutless:detalle_proyecto', args=[proyecto.pk])
            self.assertNotContains(respuesta, f'href="{detalle}"')
        self.assertEqual(self.client.get(historial_ajeno).status_code, 404)

        for proyecto in (cruzado, privado):
            detalle = reverse('cutless:detalle_proyecto', args=[proyecto.pk])
            denegacion = self.client.get(detalle, follow=True)
            self.assertRedirects(denegacion, reverse('cutless:lista_proyectos'))
            self.assertContains(denegacion, 'Proyecto no encontrado.')
            self.assertNotContains(denegacion, proyecto.nombre)

        self.client.force_login(ajeno)
        respuesta = self.client.get(historial_ajeno)
        self.assertQuerySetEqual(respuesta.context['proyectos'], [privado])
        detalle_propio = reverse('cutless:detalle_proyecto', args=[propio.pk])
        self.assertNotContains(respuesta, f'href="{detalle_propio}"')
