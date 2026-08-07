from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0025_institucion_bloqueo_secciones'),
    ]

    operations = [
        migrations.AddField(
            model_name='institucioneducativa',
            name='simat_codigo_municipio_dane',
            field=models.CharField(blank=True, help_text='Código DANE del municipio/distrito de la Secretaría de Educación (ETC).', max_length=5, verbose_name='SIMAT · Código DANE del municipio (ETC)'),
        ),
        migrations.AddField(
            model_name='institucioneducativa',
            name='simat_calendario',
            field=models.CharField(blank=True, choices=[('A', 'Calendario A'), ('B', 'Calendario B')], max_length=1, verbose_name='SIMAT · Calendario'),
        ),
        migrations.AddField(
            model_name='institucioneducativa',
            name='simat_sector',
            field=models.CharField(blank=True, choices=[('OFICIAL', 'Oficial'), ('NO_OFICIAL', 'No oficial')], max_length=12, verbose_name='SIMAT · Sector'),
        ),
    ]
