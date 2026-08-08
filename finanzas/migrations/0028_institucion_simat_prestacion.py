from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0027_institucion_simat_municipio_etc'),
    ]

    operations = [
        migrations.AddField(
            model_name='institucioneducativa',
            name='simat_prestacion_servicio',
            field=models.CharField(
                blank=True, max_length=2,
                help_text='Código de prestación del servicio que asigna el MEN al establecimiento '
                          '(según la Secretaría de Educación). Se usa en el reporte plano.',
                verbose_name='SIMAT · Prestación del servicio',
            ),
        ),
    ]
