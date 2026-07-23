from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0047_alter_registroasistencia_fecha_solo_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='acepto_tratamiento_datos',
            field=models.BooleanField(default=False, verbose_name='Aceptó la Política de Tratamiento de Datos'),
        ),
        migrations.AddField(
            model_name='usuario',
            name='fecha_aceptacion_tratamiento_datos',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Fecha de aceptación'),
        ),
        migrations.AddField(
            model_name='usuario',
            name='version_politica_aceptada',
            field=models.CharField(blank=True, default='', max_length=20, verbose_name='Versión de la política aceptada'),
        ),
        migrations.AddField(
            model_name='usuario',
            name='hash_politica_aceptada',
            field=models.CharField(blank=True, default='', help_text='Identifica de forma única el contenido exacto que el usuario aceptó, para poder demostrarlo aunque la política cambie después.', max_length=64, verbose_name='Huella (SHA-256) del texto aceptado'),
        ),
        migrations.AddField(
            model_name='usuario',
            name='ip_aceptacion_politica',
            field=models.GenericIPAddressField(blank=True, null=True, verbose_name='IP registrada al aceptar'),
        ),
        migrations.AddField(
            model_name='usuario',
            name='user_agent_aceptacion_politica',
            field=models.TextField(blank=True, default='', verbose_name='Navegador/dispositivo registrado al aceptar'),
        ),
    ]
