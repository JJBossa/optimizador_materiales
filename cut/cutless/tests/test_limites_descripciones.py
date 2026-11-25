from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from cutless.forms.descripciones import DescripcionLimitadaField
from cutless.forms.materials import MaterialAdminForm, MaterialForm
from cutless.forms.piezas import texto_de_textarea
from cutless.models import Cliente, Material, Optimizacion, Plantilla, Presupuesto, Proyecto


HISTORICO = '  \r\n' + 'Mueble ñ 🪵 ' * 18 + '\rDetalle\n  '
EXACTO = 'ñ' * 148 + '🪵'
TABLERO = {'ancho': 122, 'alto': 244, 'unidad_medida': 'cm'}
PLANTILLA = {'ancho_tablero': 122, 'alto_tablero': 244, 'unidad_medida': 'cm',
             'categoria': 'muebles', 'piezas': 'Puerta,40,50,1', 'margen_corte': 3}


class ReglasTextoTests(SimpleTestCase):
    def test_longitud_utf16_y_normalizacion(self):
        campo = DescripcionLimitadaField(required=False)
        validos = (
            ('', ''), ('ñ', 'ñ'), ('á' * 149, 'á' * 149), (EXACTO, EXACTO),
            ('🪵' * 75, '🪵' * 75), ('  á\r\nñ\r🪵\n  ', 'á\nñ\n🪵'),
            ('á' * 146 + '\r\nñ🪵', 'á' * 146 + '\nñ🪵'),
        )
        # CRLF cuenta como un salto de línea visible.
        for bruto, limpio in validos:
            with self.subTest(longitud=len(bruto)):
                self.assertEqual(campo.clean(bruto), limpio)
        for bruto in (EXACTO + 'a', '🪵' * 76, 'a' * 1200, EXACTO + ' ', validos[-1][0] + 'a'):
            with self.subTest(longitud=len(bruto)), self.assertRaises(ValidationError) as error:
                campo.clean(bruto)
            self.assertEqual(error.exception.code, 'max_length')

    def test_cambio_historico_omite_o_distingue_borrado_explicito(self):
        for clase in (MaterialForm, MaterialAdminForm):
            for enviado in ({}, {'descripcion': texto_de_textarea(HISTORICO)}, {'descripcion': ''}):
                with self.subTest(clase=clase, enviado=enviado):
                    material = Material(pk=19, nombre='Material', descripcion=HISTORICO, **TABLERO)
                    material._state.adding = False
                    formulario = clase({**TABLERO, 'nombre': material.nombre, 'precio': '500', **enviado},
                                       instance=material)
                    self.assertTrue(formulario.is_valid(), formulario.errors)
                    borrado = enviado == {'descripcion': ''}
                    self.assertEqual('descripcion' in formulario.changed_data, borrado)
                    self.assertEqual('descripcion' in formulario.campos_actualizacion(), borrado)
                    self.assertEqual(formulario.cleaned_data['descripcion'], '' if borrado else HISTORICO)


class LimitesDescripcionesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_superuser('val03_local')
        cls.usuario.perfil.rol = 'admin'
        cls.usuario.perfil.save(update_fields=['rol'])
        cls.plan = Optimizacion.objects.create(usuario=cls.usuario, ancho_tablero=122, alto_tablero=244,
                                               piezas=PLANTILLA['piezas'], num_tableros=1)
        cls.cliente = Cliente.objects.create(usuario=cls.usuario, nombre='Cliente para presupuesto')

    def setUp(self):
        self.client.force_login(self.usuario)
        self.datos_presupuesto = {
            'cliente': self.cliente.pk, 'optimizaciones': [self.plan.pk], 'precio_tablero': '500',
            'mano_obra': '0', 'fecha_validez': timezone.localdate(), 'estado': 'borrador',
        }

    def post_invalido(self, url, datos, campo, *, admin=False):
        respuesta = self.client.post(url, datos)
        self.assertEqual(respuesta.status_code, 200)
        form = respuesta.context['adminform'].form if admin else respuesta.context['form']
        self.assertTrue(form.has_error(campo, 'max_length'), form.errors)
        self.assertEqual(form[campo].value(), datos[campo])
        self.assertContains(respuesta, f'id="id_{campo}_error"')
        self.assertContains(respuesta, 'aria-invalid="true"')
        self.assertContains(respuesta, 'Usa como máximo 150 caracteres')

    def test_alta_edicion_y_guardado_parcial_de_los_cinco_campos(self):
        casos = (
            ('material', Material, 'descripcion', TABLERO, {'precio': '600'}),
            ('proyecto', Proyecto, 'descripcion', {}, {'cliente': self.cliente.pk}),
            ('plantilla', Plantilla, 'descripcion', PLANTILLA, {'categoria': 'otros'}),
            ('cliente', Cliente, 'notas', {}, {'email': 'prueba@example.test'}),
            ('presupuesto', Presupuesto, 'notas', self.datos_presupuesto, {'precio_tablero': '600'}),
        )
        for entidad, modelo, campo, datos, cambio in casos:
            with self.subTest(entidad=entidad):
                datos = {'nombre': f'Ficha {entidad}', **datos}
                alta = reverse(f'cutless:crear_{entidad}')
                cantidad = modelo.objects.count()
                self.assertContains(self.client.get(alta), 'maxlength="150"')
                self.post_invalido(alta, {**datos, campo: EXACTO + 'a', f'{campo}_original': EXACTO + 'a'}, campo)
                self.assertEqual(modelo.objects.count(), cantidad)
                self.assertEqual(self.client.post(alta, {**datos, campo: EXACTO}).status_code, 302)
                registro = modelo.objects.latest('pk')
                self.assertEqual(getattr(registro, campo), EXACTO)
                campos = {campo: HISTORICO}
                if entidad == 'proyecto':
                    fecha = timezone.localdate() - timedelta(days=10)
                    campos.update(fecha_inicio=fecha, nombre='Nombre antiguo ' * 4)
                    datos.update(fecha_inicio=fecha, nombre=campos['nombre'])
                if entidad == 'cliente':
                    campos.update(direccion_modo='estructurada', direccion_pais='ZZ',
                                  direccion_calle='  Texto histórico  ', direccion_numero='aaaaaa')
                modelo.objects.filter(pk=registro.pk).update(**campos)
                editar = reverse(f'cutless:editar_{entidad}', args=[registro.pk])
                pagina = self.client.get(editar)
                self.assertContains(pagina, 'Puedes conservar el texto guardado')
                self.assertEqual(pagina.context['form'][campo].value(), HISTORICO)
                self.assertNotContains(pagina, 'maxlength="150"')

                original = modelo.objects.values().get(pk=registro.pk)
                self.post_invalido(editar, {**datos, **cambio, campo: HISTORICO + 'cambio'}, campo)
                self.assertEqual(modelo.objects.values().get(pk=registro.pk), original)
                for envio in ({campo: texto_de_textarea(HISTORICO)}, {}):
                    respuesta = self.client.post(editar, {**datos, **cambio, **envio})
                    self.assertEqual(respuesta.status_code, 302, respuesta.context['form'].errors if respuesta.status_code == 200 else '')
                    registro.refresh_from_db()
                    self.assertEqual({k: getattr(registro, k) for k in campos}, campos)
                self.assertEqual(self.client.post(editar, {**datos, **cambio, campo: EXACTO}).status_code, 302)
                self.assertEqual(self.client.get(editar).context['form'][campo].value(), EXACTO)
                self.assertEqual(self.client.post(editar, {**datos, **cambio, campo: ''}).status_code, 302)
                self.assertEqual(self.client.get(editar).context['form'][campo].value(), '')

    def test_admin_alta_y_edicion_de_material(self):
        datos = {**TABLERO, 'nombre': 'Material sintético', 'usuario': self.usuario.pk, 'precio': '500'}
        alta = reverse('admin:cutless_material_add')
        self.assertContains(self.client.get(alta), 'maxlength="150"')
        self.post_invalido(alta, {**datos, 'descripcion': EXACTO + 'a'}, 'descripcion', admin=True)
        self.assertFalse(Material.objects.exists())
        self.assertEqual(self.client.post(alta, {**datos, 'descripcion': EXACTO}).status_code, 302)
        material = Material.objects.get()
        Material.objects.filter(pk=material.pk).update(descripcion=HISTORICO)
        editar = reverse('admin:cutless_material_change', args=[material.pk])
        datos['precio'] = '950'
        self.post_invalido(editar, {**datos, 'descripcion': HISTORICO + 'a'}, 'descripcion', admin=True)
        self.assertEqual(self.client.post(editar, {**datos, 'descripcion': texto_de_textarea(HISTORICO)}).status_code,
                         302)
        material.refresh_from_db()
        self.assertEqual((material.precio, material.descripcion), (950, HISTORICO))
        self.assertEqual(self.client.post(editar, {**datos, 'descripcion': ''}).status_code, 302)
        material.refresh_from_db()
        self.assertEqual(material.descripcion, '')

    def test_plantilla_larga_se_puede_usar_pero_no_copiar_sin_corregir(self):
        origen = Plantilla.objects.create(nombre='Original', descripcion=HISTORICO, es_predefinida=True,
                                         **{**PLANTILLA, 'margen_corte': 0.3})
        copiar = reverse('cutless:editar_plantilla', args=[origen.pk])
        usar = reverse('cutless:usar_plantilla', args=[origen.pk])
        self.assertTemplateUsed(self.client.get(usar), 'cutless/index.html')
        self.assertEqual(self.client.get(copiar).context['form']['descripcion'].value(), HISTORICO)
        datos = {**PLANTILLA, 'nombre': 'Copia'}
        self.post_invalido(copiar, {**datos, 'descripcion': HISTORICO}, 'descripcion')
        self.assertEqual(Plantilla.objects.count(), 1)
        self.assertEqual(self.client.post(copiar, {**datos, 'descripcion': EXACTO}).status_code, 302)
        self.assertEqual(Plantilla.objects.get(usuario=self.usuario).descripcion, EXACTO)
        origen.refresh_from_db()
        self.assertEqual(origen.descripcion, HISTORICO)
        alta = f"{reverse('cutless:crear_plantilla')}?optimizacion={self.plan.pk}"
        self.post_invalido(alta, {**datos, 'descripcion': EXACTO + 'a'}, 'descripcion')
        self.assertEqual(self.client.post(alta, {**datos, 'nombre': 'Desde trabajo', 'descripcion': EXACTO}).status_code,
                         302)

    def test_emision_transicion_y_exportacion_con_notas_intactas(self):
        alta = reverse('cutless:crear_presupuesto')
        self.assertEqual(self.client.post(alta, self.datos_presupuesto).status_code, 302)
        presupuesto = Presupuesto.objects.get()
        Presupuesto.objects.filter(pk=presupuesto.pk).update(notas=HISTORICO)
        editar = reverse('cutless:editar_presupuesto', args=[presupuesto.pk])
        datos = {campo: valor for campo, valor in self.datos_presupuesto.items() if campo != 'estado'}
        datos.update(accion='emitir', revision=presupuesto.fecha_actualizacion.isoformat())
        self.assertEqual(self.client.post(editar, {**datos, 'notas': texto_de_textarea(HISTORICO)}).status_code, 302)
        presupuesto.refresh_from_db()
        antes = (presupuesto.numero, presupuesto.detalle_emitido, presupuesto.costo_total,
                 list(presupuesto.optimizaciones.values_list('pk', flat=True)))
        self.assertTrue(presupuesto.detalle_emitido)
        self.assertEqual(self.client.post(editar, {'estado': 'aceptado', 'estado_origen': 'emitido', 'notas': 'a' * 400}).status_code, 302)
        presupuesto.refresh_from_db()
        self.assertEqual((presupuesto.estado, presupuesto.notas), ('aceptado', HISTORICO))
        self.assertEqual((presupuesto.numero, presupuesto.detalle_emitido, presupuesto.costo_total,
                          list(presupuesto.optimizaciones.values_list('pk', flat=True))), antes)
        from cutless.views.budgets import construir_pdf_presupuesto
        with patch('cutless.views.budgets.construir_pdf_presupuesto', wraps=construir_pdf_presupuesto) as exportar:
            respuesta = self.client.get(reverse('cutless:generar_pdf_presupuesto', args=[presupuesto.pk]))
            self.assertEqual(respuesta.status_code, 200)
            self.assertTrue(b''.join(respuesta.streaming_content).startswith(b'%PDF'))
            self.assertEqual(exportar.call_args.args[0].notas, HISTORICO)
