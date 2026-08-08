from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0068_grupo'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='preferencias_accesibilidad',
            field=models.JSONField(
                blank=True, default=dict,
                verbose_name='Preferencias de accesibilidad',
            ),
        ),
    ]
