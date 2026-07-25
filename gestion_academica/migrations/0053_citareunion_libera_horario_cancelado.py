from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0052_justificacioninasistencia'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='citareunion',
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name='citareunion',
            constraint=models.UniqueConstraint(
                condition=~models.Q(estado='CANCELADA'),
                fields=('docente', 'fecha_hora_inicio'),
                name='unique_cita_activa_por_docente_horario',
            ),
        ),
    ]
