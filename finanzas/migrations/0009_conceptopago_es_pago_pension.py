# Fase A: añade flag es_pago_pension para detectar mensualidades sin
# depender del nombre del TipoConceptoPago (que era frágil).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0008_webhook_y_llamada_mercadopago'),
    ]

    operations = [
        migrations.AddField(
            model_name='conceptopago',
            name='es_pago_pension',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Marca todas las mensualidades del año lectivo (Feb–Nov). '
                    'Las cuentas por cobrar mensuales se crean automáticamente '
                    'tomando los conceptos con este flag y filtrados por Nivel.'
                ),
                verbose_name='¿Es un concepto de pago de Pensión / Mensualidad?',
            ),
        ),
    ]
