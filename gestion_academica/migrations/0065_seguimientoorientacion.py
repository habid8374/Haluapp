from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0064_citaorientacion_reprogramacion'),
        ('finanzas', '0006_institucioneducativa_acceso_modulo_finanzas'),
    ]

    operations = [
        migrations.CreateModel(
            name='SeguimientoOrientacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Fecha de la atención')),
                ('motivo', models.CharField(choices=[('EMOCIONAL', 'Acompañamiento emocional'), ('CONVIVENCIA', 'Convivencia / comportamiento'), ('FAMILIAR', 'Situación familiar'), ('ACADEMICO', 'Dificultad académica'), ('RIESGO', 'Riesgo psicosocial'), ('REMISION', 'Remisión a entidad externa'), ('PIAR', 'Seguimiento PIAR / inclusión'), ('VOCACIONAL', 'Orientación vocacional'), ('OTRO', 'Otro')], default='EMOCIONAL', max_length=20, verbose_name='Motivo de la atención')),
                ('descripcion', models.TextField(verbose_name='Relato / observaciones (confidencial)')),
                ('acuerdos', models.TextField(blank=True, null=True, verbose_name='Acuerdos y recomendaciones')),
                ('remision', models.TextField(blank=True, help_text='Si se remitió a EPS, ICBF, comisaría u otra entidad.', null=True, verbose_name='Remisión / entidad externa')),
                ('requiere_seguimiento', models.BooleanField(default=False, verbose_name='Requiere seguimiento')),
                ('proxima_cita', models.DateField(blank=True, null=True, verbose_name='Próxima cita / seguimiento')),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('estudiante', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='seguimientos_orientacion', to='gestion_academica.estudiante')),
                ('institucion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='seguimientos_orientacion', to='finanzas.institucioneducativa')),
                ('orientador', models.ForeignKey(blank=True, limit_choices_to={'rol': 'psicologo'}, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='seguimientos_orientacion_registrados', to='gestion_academica.usuario')),
            ],
            options={
                'verbose_name': 'Seguimiento de Orientación',
                'verbose_name_plural': 'Seguimientos de Orientación',
                'ordering': ['-fecha'],
            },
        ),
    ]
