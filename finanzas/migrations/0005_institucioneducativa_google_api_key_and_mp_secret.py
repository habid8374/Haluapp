# Migración: API key Gemini por institución y mp_webhook_secret sin NULL.

from django.db import migrations, models


def coerce_null_mp_secrets(apps, schema_editor):
    Inst = apps.get_model("finanzas", "InstitucionEducativa")
    Inst.objects.filter(mp_webhook_secret__isnull=True).update(mp_webhook_secret="")


class Migration(migrations.Migration):

    dependencies = [
        ("finanzas", "0004_institucioneducativa_mp_webhook_secret"),
    ]

    operations = [
        migrations.RunPython(coerce_null_mp_secrets, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="institucioneducativa",
            name="mp_webhook_secret",
            field=models.CharField(
                blank=False,
                default="",
                help_text="Secret generado en Mercado Pago > Tu integración > Webhooks (obligatorio para validar notificaciones).",
                max_length=255,
                verbose_name="Secret de firma Webhooks (Mercado Pago)",
            ),
        ),
        migrations.AddField(
            model_name="institucioneducativa",
            name="google_api_key",
            field=models.CharField(
                blank=False,
                default="",
                help_text="Clave de la API de Google AI / Gemini para esta institución (obligatoria para funciones de IA).",
                max_length=512,
                verbose_name="Google API Key (Gemini)",
            ),
        ),
    ]
