import csv
from itertools import groupby
from operator import itemgetter

from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS

from ...models import Optimizacion


class Command(BaseCommand):
    help = 'Exporta a CSV la correspondencia de códigos de optimización por usuario.'

    def add_arguments(self, parser):
        parser.add_argument('--database', default=DEFAULT_DB_ALIAS)
        parser.add_argument('--aplicado', action='store_true', help='Lee el correlativo persistido después de migrar.')

    def handle(self, *args, **options):
        aplicado = options['aplicado']
        campos = ('usuario_id', 'pk', 'correlativo') if aplicado else ('usuario_id', 'pk')
        filas = (Optimizacion.objects.using(options['database']).order_by('usuario_id', 'fecha', 'pk')
                 .values_list(*campos).iterator(chunk_size=1000))
        csv_salida = csv.writer(self.stdout, lineterminator='\n')
        csv_salida.writerow(('usuario_id', 'optimizacion_id', 'codigo_anterior', 'codigo_nuevo'))
        for usuario_id, grupo in groupby(filas, key=itemgetter(0)):
            for posicion, fila in enumerate(grupo, start=1):
                pk = fila[1]
                correlativo = fila[2] if aplicado else posicion
                csv_salida.writerow((usuario_id, pk, f'OPT-{pk:04d}', f'OPT-{correlativo:04d}'))
