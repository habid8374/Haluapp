from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0023_institucioneducativa_claude_api_key'),
    ]

    operations = [
        migrations.AddField(
            model_name='institucioneducativa',
            name='usa_modulo_financiero',
            field=models.BooleanField(
                default=True,
                help_text=(
                    'Si se desactiva, esta institución NO ve el módulo de finanzas y la '
                    'matrícula NO genera cuentas de cobro (los pagos se manejan por fuera '
                    'de la plataforma). Independiente de si es pública o privada.'
                ),
                verbose_name='Usa el módulo financiero',
            ),
        ),
    ]
