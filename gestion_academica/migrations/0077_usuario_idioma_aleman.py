# Agrega Alemán a las opciones de idioma de interfaz del usuario.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestion_academica", "0076_usuario_idioma_frances"),
    ]

    operations = [
        migrations.AlterField(
            model_name="usuario",
            name="idioma_preferido",
            field=models.CharField(
                choices=[
                    ("es", "Español"),
                    ("en", "English"),
                    ("fr", "Français"),
                    ("de", "Deutsch"),
                ],
                default="es",
                help_text="En qué idioma ve esta persona la interfaz. Solo aplica en instituciones bilingües.",
                max_length=5,
                verbose_name="Idioma de la Plataforma",
            ),
        ),
    ]
