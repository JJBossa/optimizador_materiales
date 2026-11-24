from django.core.management.base import BaseCommand

from cutless.models import Presupuesto
from cutless.services.presupuestos import sincronizar_vencimientos


class Command(BaseCommand):
    help = 'Sincroniza presupuestos abiertos cuya validez terminó en Chile.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Cuenta los elegibles sin modificar datos.')

    def handle(self, *args, **options):
        simulacion = options['dry_run']
        cantidad = sincronizar_vencimientos(Presupuesto.objects.all(), simulacion=simulacion)
        etiqueta = 'Presupuestos elegibles' if simulacion else 'Presupuestos actualizados'
        self.stdout.write(f'{etiqueta}: {cantidad}')
