from django.db import migrations
import utils.encrypted_fields


def encrypt_existing_secrets(apps, schema_editor):
    """Re-guarda cada secret para que quede cifrado (los valores en texto plano
    se leen vía el fallback de EncryptedCharField y se cifran al guardar)."""
    InstitucionEducativa = apps.get_model('finanzas', 'InstitucionEducativa')
    for inst in InstitucionEducativa.objects.all().iterator():
        if inst.mp_webhook_secret:
            inst.save(update_fields=['mp_webhook_secret'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0018_itemcuenta_institucion'),
    ]

    operations = [
        migrations.AlterField(
            model_name='institucioneducativa',
            name='mp_webhook_secret',
            field=utils.encrypted_fields.EncryptedCharField(
                blank=False,
                default='',
                help_text='Secret generado en Mercado Pago > Tu integración > Webhooks (obligatorio para validar notificaciones).',
                verbose_name='Secret de firma Webhooks (Mercado Pago)',
            ),
        ),
        migrations.RunPython(encrypt_existing_secrets, noop_reverse),
    ]
