from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestion_academica", "0049_docente_fecha_nacimiento_eventoinstitucional"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="idioma_preferido",
            field=models.CharField(
                choices=[("es", "Español"), ("en", "English")],
                default="es",
                max_length=5,
                verbose_name="Idioma de la Plataforma",
                help_text="En qué idioma ve esta persona la interfaz. Solo aplica en instituciones bilingües.",
            ),
        ),
    ]
