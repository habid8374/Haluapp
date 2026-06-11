from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0037_itemmalla_evidencias_dba'),
    ]

    operations = [
        migrations.CreateModel(
            name='DBAPredefinido',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('area', models.CharField(
                    choices=[
                        ('matematicas', 'Matemáticas'),
                        ('lenguaje', 'Lenguaje'),
                        ('ciencias_naturales', 'Ciencias Naturales'),
                        ('ciencias_sociales', 'Ciencias Sociales'),
                        ('ingles', 'Inglés'),
                    ],
                    max_length=30, verbose_name='Área',
                )),
                ('grado', models.CharField(
                    choices=[
                        ('transicion', 'Transición'),
                        ('1', 'Grado 1°'), ('2', 'Grado 2°'), ('3', 'Grado 3°'),
                        ('4', 'Grado 4°'), ('5', 'Grado 5°'), ('6', 'Grado 6°'),
                        ('7', 'Grado 7°'), ('8', 'Grado 8°'), ('9', 'Grado 9°'),
                        ('10', 'Grado 10°'), ('11', 'Grado 11°'),
                    ],
                    max_length=15, verbose_name='Grado',
                )),
                ('numero', models.PositiveSmallIntegerField(verbose_name='N° DBA')),
                ('enunciado', models.TextField(verbose_name='Enunciado del DBA')),
                ('evidencias', models.TextField(blank=True, verbose_name='Evidencias de Aprendizaje')),
                ('version_men', models.CharField(default='V.2', max_length=10, verbose_name='Versión MEN')),
            ],
            options={
                'verbose_name': 'DBA Predefinido (MEN)',
                'verbose_name_plural': 'DBA Predefinidos (MEN)',
                'ordering': ['area', 'grado', 'numero'],
                'unique_together': {('area', 'grado', 'numero')},
            },
        ),
    ]
