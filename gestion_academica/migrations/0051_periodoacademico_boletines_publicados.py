from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0050_usuario_idioma_preferido'),
    ]

    operations = [
        migrations.AddField(
            model_name='periodoacademico',
            name='boletines_publicados',
            field=models.BooleanField(
                default=False,
                help_text='Controla si estudiantes y acudientes ya pueden ver/descargar el boletín de este periodo. Independiente del cierre de notas.',
                verbose_name='Boletines publicados',
            ),
        ),
        migrations.AddField(
            model_name='periodoacademico',
            name='fecha_publicacion_boletines',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Fecha de publicación de boletines'),
        ),
    ]
