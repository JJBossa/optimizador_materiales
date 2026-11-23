import csv
import io
from datetime import timedelta

from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from cutless.models import ContadorOptimizacion, Optimizacion, Presupuesto, TableroOptimizacion


class MigracionCorrelativosTests(TransactionTestCase):
    origen = [('cutless', '0006_alter_material_unidad_medida_and_more')]

    def test_backfill_historico_en_orden_y_reporte_sin_alterar_relaciones_o_documentos(self):
        ejecutor = MigrationExecutor(connection)
        ejecutor.migrate(self.origen)
        try:
            apps = ejecutor.loader.project_state(self.origen).apps
            Usuario = apps.get_model('auth', 'User')
            OptAntigua = apps.get_model('cutless', 'Optimizacion')
            autor = Usuario.objects.create(username='historico-a')
            otro = Usuario.objects.create(username='historico-b')
            nuevo = Usuario.objects.create(username='sin-optimizaciones')
            proyecto = apps.get_model('cutless', 'Proyecto').objects.create(usuario=autor, nombre='Proyecto histórico')
            geometria = {'vistas_web': {'1': {'ancho': 122, 'alto': 244}}}
            datos = {'ancho_tablero': 122, 'alto_tablero': 244, 'piezas': 'Puerta,40,120,1', 'resultado_extra': geometria}
            ahora = timezone.now()
            for pk, usuario, fecha in ((31, autor, ahora), (15, otro, ahora), (24, autor, ahora),
                                       (49, autor, ahora - timedelta(days=1))):
                OptAntigua.objects.create(pk=pk, usuario=usuario, **datos)
                OptAntigua.objects.filter(pk=pk).update(fecha=fecha)
            OptAntigua.objects.filter(pk=24).update(proyecto=proyecto)
            tablero = apps.get_model('cutless', 'TableroOptimizacion').objects.create(
                optimizacion_id=24, numero=1, area_usada=10, desperdicio=20, porcentaje_uso=33,
                imagen='optimizaciones/tableros/guardado.png',
            )
            detalle = {'cliente': None, 'optimizaciones': [{'pk': 24, 'codigo': 'OPT-0024'}]}
            presupuesto = apps.get_model('cutless', 'Presupuesto').objects.create(
                usuario=autor, numero='PRE-2026-0001', precio_tablero=200, costo_total=200,
                fecha_validez=timezone.localdate(), estado='enviado', detalle_emitido=detalle,
            )
            presupuesto.optimizaciones.add(24)
            previsto = io.StringIO()
            call_command('informe_correlativos_optimizaciones', stdout=previsto)
        finally:
            ejecutor = MigrationExecutor(connection)
            ejecutor.migrate(ejecutor.loader.graph.leaf_nodes())

        self.assertEqual(dict(Optimizacion.objects.values_list('pk', 'correlativo')), {49: 1, 24: 2, 31: 3, 15: 1})
        self.assertEqual(dict(ContadorOptimizacion.objects.values_list('usuario_id', 'siguiente')),
                         {autor.pk: 4, otro.pk: 2})
        actual = Optimizacion.objects.get(pk=24)
        self.assertEqual((actual.proyecto_id, actual.resultado_extra), (proyecto.pk, geometria))
        self.assertEqual(TableroOptimizacion.objects.get(pk=tablero.pk).optimizacion_id, 24)
        emitido = Presupuesto.objects.get(pk=presupuesto.pk)
        self.assertEqual(emitido.detalle_emitido, detalle)
        self.assertEqual(list(emitido.optimizaciones.values_list('pk', flat=True)), [24])
        aplicado = io.StringIO()
        call_command('informe_correlativos_optimizaciones', aplicado=True, stdout=aplicado)
        self.assertEqual(previsto.getvalue(), aplicado.getvalue())
        self.assertEqual(list(csv.DictReader(io.StringIO(aplicado.getvalue())))[1], {
            'usuario_id': str(autor.pk), 'optimizacion_id': '24', 'codigo_anterior': 'OPT-0024', 'codigo_nuevo': 'OPT-0002',
        })
        self.assertEqual(Optimizacion.objects.create(usuario_id=autor.pk, **datos).codigo, 'OPT-0004')
        self.assertEqual(Optimizacion.objects.create(usuario_id=nuevo.pk, **datos).codigo, 'OPT-0001')
