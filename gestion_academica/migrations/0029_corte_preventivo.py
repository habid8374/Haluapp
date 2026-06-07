from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0028_itemmalla_estructura_colombiana'),
        ('finanzas', '__first__'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ConfiguracionCortePreventivo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('umbral_riesgo_bajo', models.DecimalField(decimal_places=1, default=2.9, max_digits=3, verbose_name='Umbral Riesgo Alto (nota por debajo de...)')),
                ('umbral_riesgo_medio', models.DecimalField(decimal_places=1, default=3.4, max_digits=3, verbose_name='Umbral Riesgo Medio (nota por debajo de...)')),
                ('porcentaje_inasistencia_alerta', models.PositiveIntegerField(default=20, verbose_name='% Inasistencia que genera alerta')),
                ('mostrar_promedio_parcial', models.BooleanField(default=True, verbose_name='Mostrar promedio parcial en el reporte')),
                ('mostrar_asistencia', models.BooleanField(default=True, verbose_name='Incluir asistencia en el reporte')),
                ('mostrar_observaciones_docente', models.BooleanField(default=True, verbose_name='Incluir observaciones de docentes')),
                ('firma_rector_en_reporte', models.BooleanField(default=True, verbose_name='Incluir firma del rector en el PDF')),
                ('permitir_descarga_familiar', models.BooleanField(default=False, verbose_name='Permitir que familias descarguen el reporte desde el portal')),
                ('texto_pie_pagina', models.TextField(blank=True, default='Este informe es de carácter preventivo y no constituye el boletín oficial de calificaciones.', verbose_name='Texto del pie de página del reporte PDF')),
                ('institucion', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='config_corte_preventivo', to='finanzas.institucioneducativa', verbose_name='Institución')),
            ],
            options={'verbose_name': 'Configuración de Corte Preventivo', 'verbose_name_plural': 'Configuraciones de Corte Preventivo'},
        ),
        migrations.CreateModel(
            name='CortePreventivo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_corte', models.DateField(verbose_name='Fecha de Corte')),
                ('nombre_corte', models.CharField(max_length=150, verbose_name='Nombre del Corte')),
                ('estado', models.CharField(choices=[('BORRADOR', 'Borrador'), ('CALCULANDO', 'Calculando...'), ('PUBLICADO', 'Publicado'), ('ARCHIVADO', 'Archivado')], default='BORRADOR', max_length=15, verbose_name='Estado')),
                ('fecha_generacion', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')),
                ('fecha_publicacion', models.DateTimeField(blank=True, null=True, verbose_name='Fecha de Publicación')),
                ('observacion_general', models.TextField(blank=True, verbose_name='Observación General del Coordinador')),
                ('total_estudiantes_evaluados', models.PositiveIntegerField(default=0, verbose_name='Total Estudiantes Evaluados')),
                ('total_en_riesgo', models.PositiveIntegerField(default=0, verbose_name='Total en Riesgo')),
                ('grado', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cortes_preventivos', to='gestion_academica.grado', verbose_name='Grado')),
                ('generado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Generado por')),
                ('institucion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='finanzas.institucioneducativa', verbose_name='Institución')),
                ('periodo_academico', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cortes_preventivos', to='gestion_academica.periodoacademico', verbose_name='Período Académico')),
            ],
            options={'verbose_name': 'Corte Preventivo', 'verbose_name_plural': 'Cortes Preventivos', 'ordering': ['-fecha_corte', 'grado__nombre']},
        ),
        migrations.AddConstraint(
            model_name='cortepreventivo',
            constraint=models.UniqueConstraint(fields=['institucion', 'periodo_academico', 'grado', 'fecha_corte'], name='unique_corte_grado_fecha'),
        ),
        migrations.CreateModel(
            name='ResultadoCorteEstudiante',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('promedio_general', models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True, verbose_name='Promedio General')),
                ('nivel_desempeno_general', models.CharField(choices=[('SUPERIOR', 'Superior'), ('ALTO', 'Alto'), ('BASICO', 'Básico'), ('BAJO', 'Bajo'), ('SIN_DATOS', 'Sin datos')], default='SIN_DATOS', max_length=10, verbose_name='Nivel de Desempeño')),
                ('nivel_riesgo', models.CharField(choices=[('ALTO', 'Riesgo Alto'), ('MEDIO', 'Riesgo Medio'), ('BAJO', 'Riesgo Bajo'), ('SIN_RIESGO', 'Sin Riesgo')], default='SIN_RIESGO', max_length=10, verbose_name='Nivel de Riesgo')),
                ('porcentaje_asistencia', models.DecimalField(blank=True, decimal_places=1, max_digits=5, null=True, verbose_name='% Asistencia')),
                ('total_actividades_registradas', models.PositiveIntegerField(default=0, verbose_name='Total Actividades Registradas')),
                ('total_actividades_calificadas', models.PositiveIntegerField(default=0, verbose_name='Total Actividades Calificadas')),
                ('materias_en_riesgo_count', models.PositiveIntegerField(default=0, verbose_name='Materias en Riesgo')),
                ('observacion_director_curso', models.TextField(blank=True, verbose_name='Observación del Director de Curso')),
                ('requiere_citacion_padres', models.BooleanField(default=False, verbose_name='Requiere Citación de Padres')),
                ('notificacion_enviada', models.BooleanField(default=False, verbose_name='Notificación Enviada')),
                ('fecha_notificacion', models.DateTimeField(blank=True, null=True, verbose_name='Fecha de Notificación')),
                ('corte', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='resultados', to='gestion_academica.cortepreventivo', verbose_name='Corte')),
                ('estudiante', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='resultados_corte', to='gestion_academica.estudiante', verbose_name='Estudiante')),
                ('institucion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='finanzas.institucioneducativa', verbose_name='Institución')),
            ],
            options={'verbose_name': 'Resultado de Estudiante', 'verbose_name_plural': 'Resultados de Estudiantes', 'ordering': ['estudiante__usuario__last_name', 'estudiante__usuario__first_name']},
        ),
        migrations.AddConstraint(
            model_name='resultadocorteestudiante',
            constraint=models.UniqueConstraint(fields=['corte', 'estudiante', 'institucion'], name='unique_resultado_corte_estudiante'),
        ),
        migrations.CreateModel(
            name='DetalleMateriaCortePrev',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('promedio_materia', models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True, verbose_name='Promedio en la Materia')),
                ('nivel_desempeno', models.CharField(choices=[('SUPERIOR', 'Superior'), ('ALTO', 'Alto'), ('BASICO', 'Básico'), ('BAJO', 'Bajo'), ('SIN_DATOS', 'Sin datos')], default='SIN_DATOS', max_length=10, verbose_name='Nivel de Desempeño')),
                ('en_riesgo', models.BooleanField(default=False, verbose_name='¿En riesgo?')),
                ('actividades_registradas', models.PositiveIntegerField(default=0, verbose_name='Actividades Registradas')),
                ('actividades_calificadas', models.PositiveIntegerField(default=0, verbose_name='Actividades Calificadas')),
                ('actividades_pendientes', models.PositiveIntegerField(default=0, verbose_name='Actividades Pendientes de Nota')),
                ('observacion_docente', models.TextField(blank=True, verbose_name='Observación del Docente')),
                ('curso', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='gestion_academica.curso', verbose_name='Curso')),
                ('institucion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='finanzas.institucioneducativa', verbose_name='Institución')),
                ('resultado_estudiante', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detalles_materias', to='gestion_academica.resultadocorteestudiante', verbose_name='Resultado del Estudiante')),
            ],
            options={'verbose_name': 'Detalle por Materia', 'verbose_name_plural': 'Detalles por Materia', 'ordering': ['curso__materia__nombre_materia']},
        ),
        migrations.AddConstraint(
            model_name='detallemateriacorteprev',
            constraint=models.UniqueConstraint(fields=['resultado_estudiante', 'curso', 'institucion'], name='unique_detalle_materia_corte'),
        ),
    ]
