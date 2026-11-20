from itertools import groupby
from operator import itemgetter

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def asignar_correlativos(apps, schema_editor):
    Optimizacion = apps.get_model('cutless', 'Optimizacion')
    Contador = apps.get_model('cutless', 'ContadorOptimizacion')
    alias = schema_editor.connection.alias
    optimizaciones = Optimizacion.objects.using(alias)
    contadores = Contador.objects.using(alias)
    filas = optimizaciones.order_by('usuario_id', 'fecha', 'pk').values_list('usuario_id', 'pk')
    cambios, nuevos_contadores = [], []

    for usuario_id, grupo in groupby(filas.iterator(chunk_size=1000), key=itemgetter(0)):
        for correlativo, (_, pk) in enumerate(grupo, start=1):
            cambios.append(Optimizacion(pk=pk, correlativo=correlativo))
            if len(cambios) == 500:
                optimizaciones.bulk_update(cambios, ['correlativo'])
                cambios.clear()
        nuevos_contadores.append(Contador(usuario_id=usuario_id, siguiente=correlativo + 1))
        if len(nuevos_contadores) == 500:
            contadores.bulk_create(nuevos_contadores)
            nuevos_contadores.clear()

    optimizaciones.bulk_update(cambios, ['correlativo'])
    contadores.bulk_create(nuevos_contadores)


class Migration(migrations.Migration):
    dependencies = [
        ('cutless', '0006_alter_material_unidad_medida_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ContadorOptimizacion',
            fields=[
                ('usuario', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE,
                                                 primary_key=True, serialize=False, to=settings.AUTH_USER_MODEL)),
                ('siguiente', models.PositiveBigIntegerField(default=1)),
            ],
            options={'constraints': [models.CheckConstraint(condition=models.Q(siguiente__gt=0),
                                                           name='opt_contador_positivo')]},
        ),
        migrations.AddField(
            model_name='optimizacion', name='correlativo',
            field=models.PositiveBigIntegerField(editable=False, null=True),
        ),
        migrations.RunPython(asignar_correlativos, migrations.RunPython.noop),
    ]
