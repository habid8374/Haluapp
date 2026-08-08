import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0069_usuario_preferencias_accesibilidad'),
        ('finanzas', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PerfilAccesibilidad',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activo', models.BooleanField(default=True, verbose_name='Perfil activo')),
                ('font', models.CharField(choices=[('normal', 'Normal'), ('lg', 'Grande'), ('xl', 'Muy grande')], default='normal', max_length=10, verbose_name='Tamaño de texto')),
                ('contrast', models.BooleanField(default=False, verbose_name='Alto contraste')),
                ('dyslexia', models.BooleanField(default=False, verbose_name='Fuente legible')),
                ('spacing', models.BooleanField(default=False, verbose_name='Más espaciado')),
                ('reduce_motion', models.BooleanField(default=False, verbose_name='Reducir animaciones')),
                ('easy_read', models.BooleanField(default=False, verbose_name='Lectura fácil')),
                ('tts_default', models.BooleanField(default=False, verbose_name='Lectura por voz destacada')),
                ('tiempo_extra_pct', models.PositiveIntegerField(default=0, help_text='Porcentaje adicional de tiempo en cuestionarios con temporizador (ej. 25, 50).', verbose_name='Tiempo extra en evaluaciones (%)')),
                ('enunciado_simplificado', models.BooleanField(default=False, help_text='Prepara la simplificación de enunciados con IA (se aplicará progresivamente).', verbose_name='Enunciados simplificados')),
                ('notas', models.TextField(blank=True, verbose_name='Notas del apoyo')),
                ('actualizado', models.DateTimeField(auto_now=True)),
                ('estudiante', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='perfil_accesibilidad', to='gestion_academica.estudiante', verbose_name='Estudiante')),
                ('institucion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='perfiles_accesibilidad', to='finanzas.institucioneducativa', verbose_name='Institución')),
            ],
            options={
                'verbose_name': 'Perfil de accesibilidad',
                'verbose_name_plural': 'Perfiles de accesibilidad',
            },
        ),
    ]
