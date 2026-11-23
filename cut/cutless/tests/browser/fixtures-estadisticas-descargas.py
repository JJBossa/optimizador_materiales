"""Prepara planes, presupuestos y sesiones sintéticas en una SQLite vacía."""

import json
import os
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from reportlab.pdfgen import canvas

from cutless.models import Optimizacion, Presupuesto
from cutless.services import obtener_resultado_optimizacion


if settings.CUTLESS_ENV != 'development' or settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
    raise SystemExit('Usa una SQLite desechable en desarrollo.')
if User.objects.exists():
    raise SystemExit('La prueba requiere una base vacía.')

usuario = User.objects.create_superuser('vis03_sintetico')
usuario.perfil.preferencias_menu = {'_inicio_completado': True}
usuario.perfil.tutorial_completado = True
usuario.perfil.save()
planes = []
for nombre, piezas in (('Armario sintético', 'Puerta,40,50,2'),
                       ('Repisas sintéticas', 'Tablero,60,50,3'), ('Escritorio sintético', 'Cubierta,110,60,1')):
    plan = Optimizacion.objects.create(usuario=usuario, nombre=nombre, ancho_tablero=122, alto_tablero=244,
                                       piezas=piezas, precio_tablero=15000)
    obtener_resultado_optimizacion(plan, generar_imagenes=False)
    planes.append(plan)

plan = planes[0]
presupuesto = Presupuesto.objects.create(usuario=usuario, numero='PRE-UX03', precio_tablero=15000, costo_total=15000,
                                         fecha_validez=timezone.localdate() + timedelta(days=30))
presupuesto.optimizaciones.add(plan)
archivo = Path(settings.MEDIA_ROOT) / 'presupuestos' / 'ux03-archivado.pdf'
archivo.parent.mkdir(parents=True, exist_ok=True)
pdf = canvas.Canvas(str(archivo))
pdf.drawString(72, 720, 'PDF sintético archivado')
pdf.save()
historico = Presupuesto.objects.create(usuario=usuario, numero='PRE-UX03-ARCHIVADO', estado='enviado',
                                      precio_tablero=15000, costo_total=15000,
                                      fecha_validez=timezone.localdate() - timedelta(days=30),
                                      pdf=archivo.relative_to(settings.MEDIA_ROOT).as_posix())
rutas = {
    clave: reverse('cutless:' + vista, args=args)
    for clave, vista, args in (
        ('estadisticas', 'estadisticas', []), ('historial', 'historial', []),
        ('resultado', 'resultado', [plan.pk]), ('tiempo', 'calcular_tiempo_corte', [plan.pk]),
        ('presupuestos', 'lista_presupuestos', []), ('presupuesto', 'detalle_presupuesto', [presupuesto.pk]),
        ('historico', 'detalle_presupuesto', [historico.pk]), ('costos', 'historial_costos', []),
        ('pdf', 'descargar_pdf', [plan.pk]), ('login', 'index', []),
    )
}
sesion = Client()
sesion.force_login(usuario)
with Path(os.environ['CUTLESS_TEST_FIXTURE']).open('x', encoding='utf-8') as salida:
    json.dump({'session': sesion.cookies['sessionid'].value, 'rutas': rutas}, salida)
