from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('cutless', '0004_nombre_optimizacion')]

    operations = [
        migrations.AddField(
            model_name='presupuesto',
            name='detalle_emitido',
            field=models.JSONField(blank=True, editable=False, null=True),
        ),
    ]
