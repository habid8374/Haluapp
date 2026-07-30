import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0053_citareunion_libera_horario_cancelado'),
    ]

    operations = [
        migrations.AddField(
            model_name='deber',
            name='tipo_actividad',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='deberes',
                to='gestion_academica.tipoactividad',
                verbose_name='Categoría de la actividad',
            ),
        ),
    ]
