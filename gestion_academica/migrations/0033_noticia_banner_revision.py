from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0032_noticia_banner_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='noticia',
            name='banner_revision',
            field=models.PositiveIntegerField(
                default=1,
                help_text='Se incrementa automáticamente al reactivar el banner, forzando que reaparezca para todos los usuarios.',
                verbose_name='Revisión del banner',
            ),
        ),
    ]
