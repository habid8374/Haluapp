import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import gestion_academica.models


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('gestion_academica', '0051_periodoacademico_boletines_publicados'),
    ]

    operations = [
        migrations.CreateModel(
            name='JustificacionInasistencia',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_inicio', models.DateField(verbose_name='Desde')),
                ('fecha_fin', models.DateField(verbose_name='Hasta')),
                ('motivo', models.CharField(choices=[('MEDICA', 'Incapacidad médica'), ('FAMILIAR', 'Motivo familiar'), ('OTRO', 'Otro motivo')], max_length=10, verbose_name='Motivo')),
                ('descripcion', models.TextField(blank=True, verbose_name='Descripción')),
                ('documento_soporte', models.FileField(blank=True, null=True, upload_to=gestion_academica.models.ruta_documento_justificacion_inasistencia, verbose_name='Soporte (incapacidad, certificado, etc.)')),
                ('estado_revision', models.CharField(choices=[('PENDIENTE', 'Pendiente de revisión'), ('APROBADA', 'Aprobada'), ('RECHAZADA', 'Rechazada')], default='PENDIENTE', max_length=10)),
                ('fecha_revision', models.DateTimeField(blank=True, null=True)),
                ('observaciones_revision', models.TextField(blank=True, verbose_name='Observaciones de quien revisa')),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('estudiante', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='justificaciones_inasistencia', to='gestion_academica.estudiante')),
                ('institucion', models.ForeignKey(editable=False, on_delete=django.db.models.deletion.CASCADE, to='finanzas.institucioneducativa')),
                ('revisado_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Justificación de Inasistencia',
                'verbose_name_plural': 'Justificaciones de Inasistencia',
                'ordering': ['-creado_en'],
            },
        ),
    ]
