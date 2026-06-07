# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cuestionarios", "0011_respuestaestudiante_alerta_plagio_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cuestionario",
            name="intentos_permitidos",
            field=models.PositiveIntegerField(
                default=5,
                help_text="Máximo de veces que el estudiante puede presentar el cuestionario (recomendado 3–5).",
            ),
        ),
    ]
