# Generated manually for Mercado Pago webhook signature secret per institution.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finanzas", "0003_cuentacontable_institucion_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="institucioneducativa",
            name="mp_webhook_secret",
            field=models.CharField(
                blank=True,
                help_text="Copia el secret generado en Tu integración > Webhooks. Si queda vacío, se puede usar MERCADOPAGO_WEBHOOK_SECRET en el servidor.",
                max_length=255,
                null=True,
                verbose_name="Secret de firma Webhooks (Mercado Pago)",
            ),
        ),
    ]
