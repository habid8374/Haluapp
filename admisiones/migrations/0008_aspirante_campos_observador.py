# Generated manually — Aspirante: nuevos campos para el Observador del Estudiante
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admisiones', '0007_lote_resumen_correos'),
    ]

    operations = [
        migrations.AddField(
            model_name='aspirante',
            name='tipo_documento',
            field=models.CharField(
                max_length=2,
                choices=[
                    ('TI', 'Tarjeta de Identidad'),
                    ('CC', 'Cédula de Ciudadanía'),
                    ('RC', 'Registro Civil'),
                    ('PA', 'Pasaporte'),
                    ('CE', 'Cédula de Extranjería'),
                    ('OT', 'Otro'),
                ],
                blank=True, null=True,
                verbose_name='Tipo de Documento',
            ),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='lugar_nacimiento',
            field=models.CharField(
                max_length=150, blank=True, null=True,
                verbose_name='Lugar de Nacimiento',
            ),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='grupo_sanguineo',
            field=models.CharField(
                max_length=3,
                choices=[
                    ('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'),
                    ('AB+', 'AB+'), ('AB-', 'AB-'), ('O+', 'O+'), ('O-', 'O-'),
                ],
                blank=True, null=True,
                verbose_name='Grupo Sanguíneo',
            ),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='eps',
            field=models.CharField(
                max_length=100, blank=True, null=True,
                verbose_name='EPS / Entidad de Salud',
            ),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='discapacidad',
            field=models.CharField(
                max_length=255, blank=True, null=True,
                verbose_name='Discapacidad (si aplica)',
                help_text='Dejar en blanco si no aplica.',
            ),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='direccion',
            field=models.CharField(
                max_length=255, blank=True, null=True,
                verbose_name='Dirección de Residencia',
            ),
        ),
    ]
