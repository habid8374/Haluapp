from django.db import migrations, models
import finanzas.models


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0024_institucion_usa_modulo_financiero'),
    ]

    operations = [
        migrations.AddField(
            model_name='institucioneducativa',
            name='bloqueo_secciones',
            field=models.JSONField(
                default=finanzas.models._default_bloqueo_secciones,
                blank=True,
                help_text=(
                    'Lista de secciones del portal que NO podrá ver un estudiante con el '
                    'acceso bloqueado manualmente (ej. por no pago). El resto del portal '
                    'sigue disponible. Se configura con casillas en la pantalla de '
                    'Bloqueos de Estudiantes.'
                ),
                verbose_name='Secciones que se ocultan al estudiante bloqueado manualmente',
            ),
        ),
    ]
