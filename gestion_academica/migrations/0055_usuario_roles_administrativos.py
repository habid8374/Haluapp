from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0054_deber_tipo_actividad'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usuario',
            name='rol',
            field=models.CharField(
                choices=[
                    ('administrador', 'Administrador'),
                    ('coordinador', 'Coordinador(a)'),
                    ('rector', 'Rector(a) / Directivo'),
                    ('secretaria', 'Secretaría'),
                    ('tesoreria', 'Tesorería / Financiera'),
                    ('docente', 'Docente'),
                    ('estudiante', 'Estudiante'),
                    ('familiar', 'Familiar'),
                ],
                default='estudiante',
                max_length=20,
                verbose_name='Rol de Usuario',
            ),
        ),
    ]
