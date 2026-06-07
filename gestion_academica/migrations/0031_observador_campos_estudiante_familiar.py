# Generated manually — Observador del Estudiante: nuevos campos en Estudiante y Familiar
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0030_ampliar_decimales_umbral_corte_prev'),
    ]

    operations = [
        # ── Estudiante ───────────────────────────────────────────────────────
        migrations.AddField(
            model_name='estudiante',
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
            model_name='estudiante',
            name='lugar_nacimiento',
            field=models.CharField(
                max_length=150, blank=True, null=True,
                verbose_name='Lugar de Nacimiento',
            ),
        ),
        migrations.AddField(
            model_name='estudiante',
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
            model_name='estudiante',
            name='eps',
            field=models.CharField(
                max_length=100, blank=True, null=True,
                verbose_name='EPS / Entidad de Salud',
            ),
        ),
        migrations.AddField(
            model_name='estudiante',
            name='discapacidad',
            field=models.CharField(
                max_length=255, blank=True, null=True,
                verbose_name='Discapacidad (si aplica)',
                help_text='Dejar en blanco si no aplica.',
            ),
        ),
        # ── Familiar ─────────────────────────────────────────────────────────
        migrations.AddField(
            model_name='familiar',
            name='documento_identidad',
            field=models.CharField(
                max_length=20, blank=True, null=True,
                verbose_name='Número de Documento',
            ),
        ),
        migrations.AddField(
            model_name='familiar',
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
            model_name='familiar',
            name='ocupacion',
            field=models.CharField(
                max_length=150, blank=True, null=True,
                verbose_name='Ocupación',
            ),
        ),
        migrations.AddField(
            model_name='familiar',
            name='lugar_trabajo',
            field=models.CharField(
                max_length=200, blank=True, null=True,
                verbose_name='Lugar de Trabajo / Empresa',
            ),
        ),
        migrations.AddField(
            model_name='familiar',
            name='direccion',
            field=models.CharField(
                max_length=255, blank=True, null=True,
                verbose_name='Dirección de Residencia',
            ),
        ),
    ]
