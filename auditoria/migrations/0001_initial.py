import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('finanzas', '__first__'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RegistroAuditoria',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('accion', models.CharField(
                    choices=[('CREAR', 'Crear'), ('EDITAR', 'Editar'), ('ELIMINAR', 'Eliminar')],
                    max_length=10,
                    verbose_name='Acción',
                )),
                ('modelo', models.CharField(max_length=60, verbose_name='Modelo')),
                ('objeto_id', models.PositiveIntegerField(verbose_name='ID del objeto')),
                ('descripcion', models.TextField(verbose_name='Descripción')),
                ('valor_anterior', models.JSONField(blank=True, null=True, verbose_name='Valor anterior')),
                ('valor_nuevo', models.JSONField(blank=True, null=True, verbose_name='Valor nuevo')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='Dirección IP')),
                ('fecha', models.DateTimeField(auto_now_add=True, verbose_name='Fecha')),
                ('institucion', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='finanzas.institucioneducativa',
                    verbose_name='Institución',
                )),
                ('usuario', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Usuario',
                )),
            ],
            options={
                'verbose_name': 'Registro de Auditoría',
                'verbose_name_plural': 'Registros de Auditoría',
                'ordering': ['-fecha'],
            },
        ),
        migrations.AddIndex(
            model_name='registroauditoria',
            index=models.Index(fields=['institucion', 'fecha'], name='auditoria_r_institu_idx'),
        ),
        migrations.AddIndex(
            model_name='registroauditoria',
            index=models.Index(fields=['modelo', 'objeto_id'], name='auditoria_r_modelo_idx'),
        ),
    ]
