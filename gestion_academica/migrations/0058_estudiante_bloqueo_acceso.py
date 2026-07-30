import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0057_rector_acceso_total'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='estudiante',
            name='acceso_bloqueado',
            field=models.BooleanField(
                default=False,
                help_text='Si está activo, el estudiante ve una pantalla de acceso suspendido en vez del portal.',
                verbose_name='Acceso bloqueado',
            ),
        ),
        migrations.AddField(
            model_name='estudiante',
            name='motivo_bloqueo',
            field=models.CharField(blank=True, default='', max_length=255, verbose_name='Motivo del bloqueo'),
        ),
        migrations.AddField(
            model_name='estudiante',
            name='fecha_bloqueo',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Fecha de bloqueo'),
        ),
        migrations.AddField(
            model_name='estudiante',
            name='bloqueado_por',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='estudiantes_bloqueados',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Bloqueado por',
            ),
        ),
    ]
