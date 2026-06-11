from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0036_logro_grado_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemmalla',
            name='evidencias_dba',
            field=models.TextField(
                blank=True,
                null=True,
                verbose_name='Evidencias de Aprendizaje del DBA',
                help_text='Las 3-5 acciones observables del DBA que evidencian su logro. Sirven de base para los indicadores de desempeño.',
            ),
        ),
    ]
