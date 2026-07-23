import utils.encrypted_fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0022_pagoregistrado_pago_inst_fecha_idx'),
    ]

    operations = [
        migrations.AddField(
            model_name='institucioneducativa',
            name='claude_api_key',
            field=utils.encrypted_fields.EncryptedCharField(blank=True, null=True, verbose_name='Claude API Key (Anthropic)', help_text='Clave de la API de Claude (Anthropic) para esta institución. Opcional: se usa como respaldo automático si Gemini falla.'),
        ),
    ]
