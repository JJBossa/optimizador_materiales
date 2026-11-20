import base64
import io
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError, connections, transaction
from django.test import Client, TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from openpyxl import load_workbook
from PIL import Image

from cutless.models import ContadorOptimizacion, Optimizacion, Proyecto
from cutless.services.optimization import (
    calcular_numero_lista, nombre_descarga_pdf, nombre_descarga_png_tablero,
    nombre_descarga_excel,
)


class IdentificadoresPermanentesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('referencias')
        self.otro = User.objects.create_user('otras-referencias')
        self.client.force_login(self.user)
        self.ajena = Optimizacion.objects.create(usuario=self.otro, ancho_tablero=122,
            alto_tablero=244, piezas='Pieza ajena,40,120,1', nombre='Plan ajeno')
        self.opts = [Optimizacion.objects.create(usuario=self.user, ancho_tablero=122,
            alto_tablero=244, piezas=f'Puerta {i},40,120,1', aprovechamiento_total=i*10)
            for i in range(1,8)]

    def test_eliminar_intermedia_no_renumera_ordenes_ni_filtros(self):
        before = {o.pk:o.codigo for o in self.opts}
        self.opts[4].delete()
        for order in ['fecha_desc','fecha_asc','aprovechamiento_desc','aprovechamiento_asc']:
            response = self.client.get(reverse('cutless:historial'), {'ordenar_por':order})
            self.assertEqual(response.status_code,200)
            for item in response.context['optimizaciones_con_piezas']:
                opt = item['optimizacion']
                self.assertEqual(item['numero'], opt.correlativo)
                self.assertContains(response,before[opt.pk])
                self.assertEqual(calcular_numero_lista(self.user, opt.pk, order), opt.correlativo)
        response = self.client.get(reverse('cutless:historial'), {'nombre_pieza':'Puerta 6'})
        self.assertContains(response,self.opts[5].codigo)
        self.assertEqual(len(response.context['optimizaciones_con_piezas']),1)

    def test_eliminar_ultima_no_reutiliza_codigo(self):
        last_id = self.opts[-1].pk
        self.opts[-1].delete()
        new = Optimizacion.objects.create(usuario=self.user,ancho_tablero=122,
            alto_tablero=244,piezas='Puerta,40,120,1')
        self.assertGreater(new.pk,last_id)
        self.assertEqual(new.codigo, 'OPT-0008')

    def test_historial_vacio_no_reinicia_contador_y_usuarios_son_independientes(self):
        self.assertEqual(self.ajena.codigo, 'OPT-0001')
        self.assertEqual([opt.codigo for opt in self.opts], [f'OPT-{n:04d}' for n in range(1, 8)])
        self.assertNotEqual(self.ajena.pk, self.opts[0].pk)
        respuesta = self.client.post(reverse('cutless:borrar_historial'))
        self.assertRedirects(respuesta, reverse('cutless:historial'), fetch_redirect_response=False)
        self.assertEqual(list(Optimizacion.objects.all()), [self.ajena])
        self.assertEqual(ContadorOptimizacion.objects.get(usuario=self.user).siguiente, 8)
        datos = {'ancho_tablero': 122, 'alto_tablero': 244, 'piezas': 'Puerta,40,120,1'}
        reinicio, otro = Optimizacion.objects.bulk_create([
            Optimizacion(usuario=self.user, **datos), Optimizacion(usuario=self.otro, **datos),
        ])
        self.assertEqual((reinicio.codigo, otro.codigo), ('OPT-0008', 'OPT-0002'))

    def test_busquedas_por_codigo_y_descargas_solo_exponen_al_propietario(self):
        for usuario in (self.user, self.otro):
            usuario.perfil.rol = 'admin'
            usuario.perfil.save(update_fields=['rol'])
        proyecto = Proyecto.objects.create(usuario=self.user, nombre='Proyecto propio')
        historial = reverse('cutless:historial')
        agregar = reverse('cutless:agregar_optimizaciones_proyecto', args=[proyecto.pk])
        self.assertEqual(self.client.get(historial, {'nombre_pieza': 'opt-1'}).context['page_obj'].object_list[0],
                         self.opts[0])
        planes = self.client.get(agregar, {'busqueda': 'OPT-0001'}).context['optimizaciones_disponibles']
        self.assertEqual(planes, [self.opts[0]])
        cliente_ajeno = Client()
        cliente_ajeno.force_login(self.otro)
        resultado = cliente_ajeno.get(historial, {'nombre_pieza': 'OPT-0001'})
        self.assertContains(resultado, 'Plan ajeno')
        self.assertNotContains(resultado, 'Puerta 1')
        self.assertEqual(cliente_ajeno.get(agregar).status_code, 404)
        self.assertIsNone(calcular_numero_lista(self.user, self.ajena.pk))
        for vista in ('resultado', 'descargar_pdf', 'descargar_excel', 'descargar_png'):
            self.assertEqual(self.client.get(reverse('cutless:' + vista, args=[self.ajena.pk])).status_code, 404)
        for codigo in ('OPT-0000', 'OPT-9223372036854775808', 'OPT-' + '9' * 5000):
            resultado = self.client.get(historial, {'nombre_pieza': codigo})
            self.assertEqual(len(resultado.context['optimizaciones_con_piezas']), 0)

    def test_colision_de_pk_revierte_reserva_y_restriccion_unica_protege_la_bd(self):
        with self.assertRaises(IntegrityError):
            Optimizacion.objects.create(pk=self.opts[0].pk, usuario=self.user, ancho_tablero=122,
                                        alto_tablero=244, piezas='Puerta,40,120,1')
        self.assertEqual(ContadorOptimizacion.objects.get(usuario=self.user).siguiente, 8)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Optimizacion._base_manager.filter(pk=self.opts[1].pk).update(correlativo=1)
        with self.assertRaises(ValueError):
            Optimizacion.objects.filter(pk=self.opts[1].pk).update(correlativo=999)
        cambio = self.opts[1]
        cambio.usuario = self.otro
        with self.assertRaises(ValueError):
            cambio.save()

    def test_descargas_ignoran_posicion_y_distinguen_tableros(self):
        opt = self.opts[5]
        self.assertEqual(nombre_descarga_pdf(1,opt),opt.codigo+'.pdf')
        self.assertEqual(nombre_descarga_excel(999,opt),opt.codigo+'.xlsx')
        self.assertEqual(nombre_descarga_png_tablero(1,opt,2),opt.codigo+'_tablero-2.png')

    def test_duplicar_y_eliminar_utilizan_la_misma_referencia(self):
        opt=self.opts[5]
        response=self.client.get(reverse('cutless:duplicar_optimizacion',args=[opt.pk]))
        self.assertContains(response,opt.codigo)
        response=self.client.get(reverse('cutless:borrar_optimizacion',args=[opt.pk]))
        self.assertContains(response,opt.codigo)

    def test_contenido_pdf_y_excel_identifica_el_trabajo(self):
        from cutless.exports.excel import generar_excel
        from cutless.exports.pdf import generar_pdf
        from reportlab.pdfgen.canvas import Canvas
        opt=self.opts[5]
        info={'info_tableros':[], 'area_usada_total':4800,'desperdicio_total':24968}
        workbook=load_workbook(generar_excel(opt,info,[],numero_lista=1))
        self.assertIn(opt.codigo,workbook['Resumen']['A1'].value)
        workbook.close()
        png=io.BytesIO();Image.new('RGB',(20,40),'white').save(png,format='PNG')
        original=Canvas.drawCentredString
        labels=[]
        def capture(canvas,x,y,text,*args,**kwargs):
            labels.append(text)
            return original(canvas,x,y,text,*args,**kwargs)
        with patch.object(Canvas,'drawCentredString',autospec=True,side_effect=capture):
            generar_pdf(opt,[base64.b64encode(png.getvalue()).decode()],numero_lista=1,
                info_desperdicio=info,archivo_salida=io.BytesIO())
        self.assertTrue(any(opt.codigo in text for text in labels))

    def test_edicion_recalculo_y_duplicacion_conservan_o_asignan_segun_corresponde(self):
        original = self.opts[0]
        editar = reverse('cutless:editar_optimizacion', args=[original.pk])
        duplicar = reverse('cutless:duplicar_optimizacion', args=[original.pk])
        datos = {'unidad_medida': 'cm', 'ancho': 122, 'alto': 244, 'margen_corte': 3,
                 'form-TOTAL_FORMS': 1, 'form-INITIAL_FORMS': 0, 'form-0-nombre': 'Puerta',
                 'form-0-ancho': 40, 'form-0-alto': 120, 'form-0-cantidad': 2}
        self.assertEqual(self.client.post(editar, {**datos, 'nombre_optimizacion': 'Recalculado'}).status_code, 302)
        original.refresh_from_db()
        self.assertEqual((original.codigo, original.nombre), ('OPT-0001', 'Recalculado'))
        self.assertContains(self.client.get(duplicar), original.codigo)
        self.assertEqual(Optimizacion.objects.filter(usuario=self.user).count(), 7)
        self.assertEqual(self.client.post(reverse('cutless:index'), datos).status_code, 302)
        copia = Optimizacion.objects.get(usuario=self.user, correlativo=8)
        self.assertEqual(copia.codigo, 'OPT-0008')
        self.assertNotEqual(copia.pk, original.pk)

        for ruta, nombre in (('descargar_pdf', 'OPT-0001.pdf'), ('descargar_excel', 'OPT-0001.xlsx'),
                             ('descargar_png', 'OPT-0001_tablero-1.png')):
            respuesta = self.client.get(reverse('cutless:' + ruta, args=[original.pk]))
            self.assertEqual(respuesta.status_code, 200)
            self.assertIn(nombre, respuesta['Content-Disposition'])
            contenido = b''.join(respuesta.streaming_content) if respuesta.streaming else respuesta.content
            self.assertTrue(contenido)

    def test_pdf_en_disco_no_colisiona_entre_propietarios_con_el_mismo_codigo(self):
        from cutless.exports.pdf import generar_pdf

        imagen = io.BytesIO()
        Image.new('RGB', (20, 40), 'white').save(imagen, format='PNG')
        tableros = [base64.b64encode(imagen.getvalue()).decode()]
        with TemporaryDirectory() as destino, self.settings(MEDIA_ROOT=destino):
            rutas = [generar_pdf(opt, tableros, info_desperdicio={}) for opt in (self.opts[0], self.ajena)]
            self.assertNotEqual(*rutas)
            for ruta in rutas:
                self.assertTrue((Path(destino) / ruta).read_bytes().startswith(b'%PDF'))

    def test_excel_de_estadisticas_incluye_codigo_visible(self):
        from cutless.exports.excel import generar_excel_resumen_desperdicio

        planes = Optimizacion.objects.filter(pk=self.opts[0].pk)
        with io.BytesIO(generar_excel_resumen_desperdicio(planes, {}).read()) as contenido:
            libro = load_workbook(contenido)
            self.assertEqual(libro['Detalle Optimizaciones']['J2'].value, 'OPT-0001')
            libro.close()


class CorrelativosConcurrentesTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_alta_simultanea_inicial_y_lotes_comparten_el_contador_correcto(self):
        primero = User.objects.create_user('correlativo-concurrente-a').pk
        segundo = User.objects.create_user('correlativo-concurrente-b').pk
        datos = {'ancho_tablero': 122, 'alto_tablero': 244, 'piezas': 'Puerta,40,120,1'}
        barrera = Barrier(8)

        def insertar(i):
            try:
                barrera.wait(timeout=10)
                if i % 2:
                    return [Optimizacion.objects.create(usuario_id=primero, **datos)]
                usuarios = (primero, segundo) if i % 4 else (segundo, primero)
                return Optimizacion.objects.bulk_create([Optimizacion(usuario_id=uid, **datos) for uid in usuarios])
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=8) as ejecutor:
            creadas = [opt for lote in ejecutor.map(insertar, range(8)) for opt in lote]
        for uid, cantidad in ((primero, 8), (segundo, 4)):
            numeros = sorted(opt.correlativo for opt in creadas if opt.usuario_id == uid)
            self.assertEqual(numeros, list(range(1, cantidad + 1)))
            self.assertEqual(ContadorOptimizacion.objects.get(usuario_id=uid).siguiente, cantidad + 1)
