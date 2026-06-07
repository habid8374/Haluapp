from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0031_observador_campos_estudiante_familiar'),
    ]

    operations = [
        migrations.AddField(
            model_name='noticia',
            name='tipo',
            field=models.CharField(
                choices=[
                    ('URGENTE', 'Urgente (pagos, fechas límite, acceso)'),
                    ('EVENTO', 'Evento (celebraciones, actividades)'),
                    ('INFORMATIVO', 'Informativo (sin banner)'),
                ],
                default='INFORMATIVO',
                max_length=15,
                verbose_name='Tipo',
            ),
        ),
        migrations.AddField(
            model_name='noticia',
            name='mostrar_banner',
            field=models.BooleanField(
                default=False,
                help_text='Activa esto para que aparezca como banner en la esquina inferior izquierda.',
                verbose_name='Mostrar como banner flotante',
            ),
        ),
        migrations.AddField(
            model_name='noticia',
            name='fecha_expiracion_banner',
            field=models.DateField(
                blank=True,
                null=True,
                help_text='El banner se oculta automáticamente después de esta fecha. Dejar vacío para que no expire.',
                verbose_name='Fecha de expiración del banner',
            ),
        ),
        migrations.AddField(
            model_name='noticia',
            name='audiencia',
            field=models.CharField(
                choices=[
                    ('TODOS', 'Todos (docentes + estudiantes + familias)'),
                    ('DOCENTES', 'Solo docentes'),
                    ('ESTUDIANTES', 'Solo estudiantes'),
                    ('FAMILIAS', 'Solo familias / acudientes'),
                ],
                default='TODOS',
                max_length=15,
                verbose_name='Audiencia del banner',
            ),
        ),
    ]
