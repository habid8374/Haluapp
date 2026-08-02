from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0061_grupo_psicoorientador'),
        ('finanzas', '0006_institucioneducativa_acceso_modulo_finanzas'),
    ]

    operations = [
        migrations.CreateModel(
            name='DisponibilidadOrientador',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('dia_semana', models.IntegerField(choices=[(0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'), (3, 'Jueves'), (4, 'Viernes')], verbose_name='Día de la semana')),
                ('hora_inicio', models.TimeField(verbose_name='Hora de inicio de disponibilidad')),
                ('hora_fin', models.TimeField(verbose_name='Hora de fin de disponibilidad')),
                ('institucion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='finanzas.institucioneducativa')),
                ('orientador', models.ForeignKey(limit_choices_to={'rol': 'psicologo'}, on_delete=django.db.models.deletion.CASCADE, related_name='disponibilidades_orientacion', to='gestion_academica.usuario')),
            ],
            options={
                'verbose_name': 'Disponibilidad de Orientador',
                'verbose_name_plural': 'Disponibilidades de Orientadores',
                'unique_together': {('orientador', 'dia_semana', 'hora_inicio')},
            },
        ),
        migrations.CreateModel(
            name='CitaOrientacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_hora_inicio', models.DateTimeField(verbose_name='Fecha y hora de la cita')),
                ('duracion_minutos', models.PositiveIntegerField(default=30, verbose_name='Duración (minutos)')),
                ('asunto', models.CharField(max_length=255, verbose_name='Asunto principal de la reunión')),
                ('enlace_virtual', models.URLField(blank=True, null=True, verbose_name='Enlace de la videollamada (si aplica)')),
                ('estado', models.CharField(choices=[('PENDIENTE', 'Pendiente'), ('CONFIRMADA', 'Confirmada'), ('CANCELADA', 'Cancelada'), ('REALIZADA', 'Realizada')], default='PENDIENTE', max_length=15)),
                ('origen', models.CharField(choices=[('FAMILIA', 'Solicitada por la familia'), ('ORIENTADOR', 'Citada por el orientador')], default='FAMILIA', max_length=12)),
                ('observaciones_orientador', models.TextField(blank=True, help_text='Notas privadas del orientador sobre lo discutido en la reunión.', null=True, verbose_name='Observaciones de la Reunión')),
                ('acuerdos_compromisos', models.TextField(blank=True, help_text='Resumen de los acuerdos a los que se llegaron. Será visible para la familia.', null=True, verbose_name='Acuerdos y Compromisos')),
                ('creada', models.DateTimeField(auto_now_add=True)),
                ('estudiante', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='citas_orientacion', to='gestion_academica.estudiante')),
                ('familiar', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='citas_orientacion', to='gestion_academica.familiar')),
                ('institucion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='finanzas.institucioneducativa')),
                ('orientador', models.ForeignKey(limit_choices_to={'rol': 'psicologo'}, on_delete=django.db.models.deletion.CASCADE, related_name='citas_orientacion', to='gestion_academica.usuario')),
            ],
            options={
                'verbose_name': 'Cita de Orientación',
                'verbose_name_plural': 'Citas de Orientación',
                'ordering': ['fecha_hora_inicio'],
            },
        ),
        migrations.AddConstraint(
            model_name='citaorientacion',
            constraint=models.UniqueConstraint(
                condition=models.Q(('estado', 'CANCELADA'), _negated=True),
                fields=('orientador', 'fecha_hora_inicio'),
                name='unique_cita_orientacion_activa',
            ),
        ),
    ]
