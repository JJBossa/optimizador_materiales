from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('cutless', '0007_correlativo_optimizaciones')]

    operations = [
        migrations.AlterField(
            model_name='optimizacion', name='correlativo', field=models.PositiveBigIntegerField(editable=False),
        ),
        migrations.AddConstraint(
            model_name='optimizacion',
            constraint=models.UniqueConstraint(fields=('usuario', 'correlativo'), name='opt_correlativo_usuario_unico'),
        ),
        migrations.AddConstraint(
            model_name='optimizacion',
            constraint=models.CheckConstraint(condition=models.Q(correlativo__gt=0), name='opt_correlativo_positivo'),
        ),
    ]
