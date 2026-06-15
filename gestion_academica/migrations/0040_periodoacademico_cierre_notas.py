from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0039_setup_permission_groups'),
    ]

    operations = [
        migrations.AddField(
            model_name='periodoacademico',
            name='notas_cerradas',
            field=models.BooleanField(default=False, verbose_name='Notas cerradas'),
        ),
        migrations.AddField(
            model_name='periodoacademico',
            name='fecha_cierre_notas',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Fecha de cierre de notas'),
        ),
    ]
