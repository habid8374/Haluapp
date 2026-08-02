from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0063_citaorientacion_motivo_cancelacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='citaorientacion',
            name='fecha_propuesta',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Nuevo horario propuesto'),
        ),
        migrations.AddField(
            model_name='citaorientacion',
            name='propuesta_por',
            field=models.CharField(blank=True, choices=[('FAMILIA', 'Familia'), ('ORIENTADOR', 'Orientador(a)')], max_length=12, null=True, verbose_name='Propuesta hecha por'),
        ),
        migrations.AlterField(
            model_name='citaorientacion',
            name='estado',
            field=models.CharField(choices=[('PENDIENTE', 'Pendiente'), ('CONFIRMADA', 'Confirmada'), ('REAGENDANDO', 'En reprogramación'), ('CANCELADA', 'Cancelada'), ('REALIZADA', 'Realizada')], default='PENDIENTE', max_length=15),
        ),
    ]
