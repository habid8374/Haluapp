import decimal
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('finanzas', '0001_initial'),
        ('gestion_academica', '__first__'),
    ]

    operations = [
        migrations.CreateModel(
            name='RecursoEducativo3D',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('modo', models.CharField(
                    choices=[
                        ('galeria', 'Solo Galería'),
                        ('studio', 'Solo Studio'),
                        ('ambos', 'Galería + Studio'),
                    ],
                    default='ambos',
                    max_length=10,
                    verbose_name='Modo del Recurso',
                )),
                ('valor_maximo', models.DecimalField(
                    decimal_places=2,
                    default=decimal.Decimal('5.00'),
                    help_text='Nota máxima que puede obtener el estudiante (ej: 5.00)',
                    max_digits=5,
                    verbose_name='Nota Máxima',
                )),
                ('actividad', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='recurso_3d',
                    to='gestion_academica.actividadcalificable',
                    verbose_name='Actividad Calificable',
                )),
                ('institucion', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='recursos_3d',
                    to='finanzas.institucioneducativa',
                    verbose_name='Institución',
                )),
            ],
            options={
                'verbose_name': 'Recurso Educativo 3D',
                'verbose_name_plural': 'Recursos Educativos 3D',
                'ordering': ['-actividad__fecha_publicacion'],
            },
        ),
        migrations.CreateModel(
            name='EntregaRecurso3D',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('piezas_colocadas', models.PositiveSmallIntegerField(
                    default=0,
                    help_text='Número de órganos correctamente colocados en el Studio (0–13)',
                    verbose_name='Piezas Colocadas',
                )),
                ('completado', models.BooleanField(default=False, verbose_name='Studio Completado')),
                ('fecha_inicio', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Primer Acceso')),
                ('fecha_completado', models.DateTimeField(blank=True, null=True, verbose_name='Fecha de Completado')),
                ('estudiante', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='entregas_3d',
                    to='gestion_academica.estudiante',
                    verbose_name='Estudiante',
                )),
                ('recurso', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='entregas',
                    to='recursos_educativos.recursoeducativo3d',
                    verbose_name='Recurso 3D',
                )),
                ('institucion', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='entregas_3d',
                    to='finanzas.institucioneducativa',
                    verbose_name='Institución',
                )),
            ],
            options={
                'verbose_name': 'Entrega de Recurso 3D',
                'verbose_name_plural': 'Entregas de Recursos 3D',
                'ordering': ['-fecha_inicio'],
            },
        ),
        migrations.AddConstraint(
            model_name='entregarecurso3d',
            constraint=models.UniqueConstraint(
                fields=['recurso', 'estudiante', 'institucion'],
                name='unique_entrega_por_recurso_estudiante_institucion',
            ),
        ),
    ]
