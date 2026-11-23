from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from cutless.forms import TableroForm
from cutless.models import Material, Optimizacion


class PermisosCatalogoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user('staff_catalogo', is_staff=True)
        cls.otro = User.objects.create_user('otro_catalogo')
        cls.delegado = User.objects.create_user('delegado_catalogo', is_staff=True)
        cls.delegado.perfil.rol = 'admin'
        cls.delegado.perfil.save(update_fields=['rol'])
        cls.superusuario = User.objects.create_superuser('super_catalogo')
        permisos = Permission.objects.filter(content_type__app_label='cutless', content_type__model='material')
        cls.staff.user_permissions.add(*permisos)
        cls.delegado.user_permissions.add(*permisos)
        cls.propio = Material.objects.create(nombre='Personal del staff', usuario=cls.staff, ancho=122, alto=244)
        cls.ajeno = Material.objects.create(nombre='Personal ajeno', usuario=cls.otro, ancho=122, alto=244)
        cls.global_ = Material.objects.create(nombre='Tablero de catálogo', es_predefinido=True, ancho=122, alto=244)
        cls.historico = Material.objects.create(nombre='Compartido antiguo', usuario=cls.otro, es_predefinido=True,
                                                ancho=122, alto=244)

    datos = {'nombre': 'Ficha revisada', 'ancho': '122', 'alto': '244', 'unidad_medida': 'cm', 'precio': '15000'}

    def admin_url(self, accion, material=None):
        return reverse('admin:cutless_material_' + accion, args=[material.pk] if material else [])

    def eliminar_seleccion(self, *materiales):
        return self.client.post(self.admin_url('changelist'), {
            'action': 'delete_selected', 'post': 'yes', ACTION_CHECKBOX_NAME: [m.pk for m in materiales],
        })

    def test_staff_ve_catalogo_pero_solo_gestiona_material_personal(self):
        self.client.force_login(self.staff)
        lista = self.client.get(self.admin_url('changelist'))
        for material in (self.propio, self.global_, self.historico):
            self.assertContains(lista, material.nombre)
        self.assertNotContains(lista, self.ajeno.nombre)
        self.assertEqual(self.client.get(self.admin_url('changelist'), {'usuario': self.otro.pk}).status_code, 400)
        ficha = self.client.get(self.admin_url('change', self.historico))
        self.assertContains(ficha, self.historico.nombre)
        self.assertNotContains(ficha, 'name="_save"')
        self.assertNotContains(ficha, self.otro.username)
        for material in (self.global_, self.historico):
            self.assertEqual(self.client.post(self.admin_url('change', material), self.datos).status_code, 403)
            for metodo in (self.client.get, self.client.post):
                self.assertEqual(metodo(self.admin_url('delete', material)).status_code, 403)
        for accion in ('change', 'delete'):
            self.assertRedirects(self.client.post(self.admin_url(accion, self.ajeno), self.datos),
                                 reverse('admin:index'), fetch_redirect_response=False)

    def test_material_compartido_con_propietario_no_aparece_como_personal(self):
        self.historico.usuario = self.staff
        self.historico.save(update_fields=['usuario'])
        self.client.force_login(self.staff)
        lista = self.client.get(reverse('cutless:lista_materiales'))
        self.assertContains(lista, self.historico.nombre, count=1)
        for accion in ('editar_material', 'eliminar_material'):
            self.assertNotContains(lista, reverse('cutless:' + accion, args=[self.historico.pk]))
        self.assertEqual(self.client.post(self.admin_url('change', self.historico), self.datos).status_code, 403)

    def test_staff_crea_y_edita_solo_personales_con_propietario_fijo(self):
        self.client.force_login(self.staff)
        datos = {**self.datos, 'usuario': self.otro.pk, 'es_predefinido': 'on'}
        alta = self.admin_url('add')
        ficha = self.client.get(alta)
        for campo in ('usuario', 'es_predefinido'):
            self.assertNotContains(ficha, f'name="{campo}"')
        self.assertEqual(self.client.post(alta, datos).status_code, 302)
        creado = Material.objects.get(nombre=self.datos['nombre'])
        self.assertEqual((creado.usuario_id, creado.es_predefinido), (self.staff.pk, False))
        self.assertEqual(self.client.post(self.admin_url('change', self.propio), datos).status_code, 302)
        self.propio.refresh_from_db()
        self.assertEqual((self.propio.usuario_id, self.propio.es_predefinido), (self.staff.pk, False))
        self.assertEqual(self.client.post(self.admin_url('delete', self.propio), {'post': 'yes'}).status_code, 302)
        self.assertFalse(Material.objects.filter(pk=self.propio.pk).exists())

    def test_lote_mixto_protegido_y_lote_personal_autorizado(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.eliminar_seleccion(self.propio, self.global_).status_code, 403)
        self.assertEqual(Material.objects.count(), 4)
        self.assertEqual(self.eliminar_seleccion(self.propio, self.ajeno).status_code, 302)
        self.assertEqual(set(Material.objects.values_list('pk', flat=True)),
                         {self.ajeno.pk, self.global_.pk, self.historico.pk})

    def test_delegado_preserva_propietario_historico_en_ambas_interfaces(self):
        self.client.force_login(self.delegado)
        datos = {**self.datos, 'usuario': self.delegado.pk, 'es_predefinido': ''}
        for url in (self.admin_url('change', self.historico),
                    reverse('cutless:editar_material', args=[self.historico.pk])):
            self.assertEqual(self.client.post(url, datos).status_code, 302)
            self.historico.refresh_from_db()
            self.assertEqual((self.historico.nombre, self.historico.usuario_id, self.historico.es_predefinido),
                             (self.datos['nombre'], self.otro.pk, True))
        self.assertEqual(self.eliminar_seleccion(self.global_).status_code, 302)
        self.assertFalse(Material.objects.filter(pk=self.global_.pk).exists())

    def test_superusuario_mantiene_administracion_del_catalogo_y_de_propiedad(self):
        self.client.force_login(self.superusuario)
        self.assertContains(self.client.get(self.admin_url('changelist')), self.ajeno.nombre)
        datos = {**self.datos, 'usuario': self.staff.pk, 'es_predefinido': 'on'}
        self.assertEqual(self.client.post(self.admin_url('change', self.ajeno), datos).status_code, 302)
        self.ajeno.refresh_from_db()
        self.assertEqual((self.ajeno.usuario_id, self.ajeno.es_predefinido), (self.staff.pk, True))

    def test_borrado_en_admin_preserva_las_optimizaciones_asociadas(self):
        plan = Optimizacion.objects.create(usuario=self.otro, ancho_tablero=122, alto_tablero=244,
                                          piezas='Pieza,20,20,1', material=self.global_)
        self.client.force_login(self.superusuario)
        for respuesta in (self.client.get(self.admin_url('delete', self.global_)),
                          self.client.post(self.admin_url('delete', self.global_), {'post': 'yes'}),
                          self.eliminar_seleccion(self.global_, self.propio)):
            self.assertContains(respuesta, 'materiales asociados a optimizaciones')
        plan.refresh_from_db()
        self.assertEqual(plan.material_id, self.global_.pk)
        self.assertEqual(Material.objects.count(), 4)

    def test_vistas_publicas_preservan_catalogo_y_autorizacion_por_propietario(self):
        self.client.force_login(self.staff)
        self.assertIn(self.global_, TableroForm(user=self.staff).fields['material'].queryset)
        self.assertNotIn(self.ajeno, TableroForm(user=self.staff).fields['material'].queryset)
        for material, estado in ((self.ajeno, 404), (self.global_, 403)):
            for accion in ('editar_material', 'eliminar_material'):
                url = reverse('cutless:' + accion, args=[material.pk])
                self.assertEqual(self.client.get(url).status_code, estado)
                self.assertEqual(self.client.post(url, self.datos).status_code, estado)
        self.assertEqual(self.client.post(reverse('cutless:crear_material'), {
            **self.datos, 'usuario': self.otro.pk, 'es_predefinido': 'on',
        }).status_code, 302)
        creado = Material.objects.get(nombre=self.datos['nombre'])
        self.assertEqual((creado.usuario_id, creado.es_predefinido), (self.staff.pk, False))
