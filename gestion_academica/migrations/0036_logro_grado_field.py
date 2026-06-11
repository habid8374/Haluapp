from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0035_add_bilingue_materia_itemmalla'),
    ]

    operations = [
        migrations.AddField(
            model_name='logro',
            name='grado',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='logros',
                to='gestion_academica.grado',
                verbose_name='Grado',
            ),
        ),
        migrations.AddField(
            model_name='logropreescolar',
            name='grado',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='logros_preescolar',
                to='gestion_academica.grado',
                verbose_name='Grado',
            ),
        ),
        migrations.AddField(
            model_name='descriptorlogro',
            name='grado',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='descriptores_logro',
                to='gestion_academica.grado',
                verbose_name='Grado',
            ),
        ),
    ]
