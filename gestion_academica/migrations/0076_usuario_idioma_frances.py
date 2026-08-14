# Agrega Francés a las opciones de idioma de interfaz del usuario.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestion_academica", "0075_lectura_facil_deber_boletin"),
    ]

    operations = [
        migrations.AlterField(
            model_name="usuario",
            name="idioma_preferido",
            field=models.CharField(
                choices=[("es", "Español"), ("en", "English"), ("fr", "Français")],
                default="es",
                help_text="En qué idioma ve esta persona la interfaz. Solo aplica en instituciones bilingües.",
                max_length=5,
                verbose_name="Idioma de la Plataforma",
            ),
        ),
    ]
