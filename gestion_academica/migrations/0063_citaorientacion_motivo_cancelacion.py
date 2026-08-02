from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0062_citas_orientacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='citaorientacion',
            name='motivo_cancelacion',
            field=models.TextField(blank=True, help_text='Razón indicada por quien canceló la cita (familia u orientador).', null=True, verbose_name='Motivo de cancelación'),
        ),
    ]
