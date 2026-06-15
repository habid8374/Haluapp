import django.db.models.fields
import utils.encrypted_fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0015_add_bilingue_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='institucioneducativa',
            name='brevo_api_key',
            field=utils.encrypted_fields.EncryptedCharField(blank=True, null=True, verbose_name='Brevo API Key', help_text='Clave API de Brevo para correos transaccionales. Tiene prioridad sobre SMTP si está configurada.'),
        ),
        migrations.AddField(
            model_name='institucioneducativa',
            name='brevo_sender_email',
            field=django.db.models.fields.EmailField(blank=True, max_length=255, null=True, verbose_name='Email Remitente Brevo', help_text='Email verificado en Brevo desde el que se envían los correos.'),
        ),
        migrations.AddField(
            model_name='institucioneducativa',
            name='brevo_sender_name',
            field=django.db.models.fields.CharField(blank=True, max_length=100, null=True, verbose_name='Nombre Remitente Brevo', help_text="Nombre que aparece como remitente. Si no se configura, se usa el nombre de la institución."),
        ),
    ]
