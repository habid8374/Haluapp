# Agrega la categoría "Ciencia de la Tierra y sostenibilidad" al catálogo
# de Retos STEAM (horno solar, filtro de agua...).
#
# NOTA: separada a mano del autogenerado por `makemigrations`, que agrupaba
# esto con un `AlterField` de `justificacioninasistencia.id` no relacionado
# (drift preexistente de la BD, ajeno a este cambio) — mismo criterio que en
# 0078/0080/0082/0083/0084/0087.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestion_academica", "0090_fix_iconos_steam"),
    ]

    operations = [
        migrations.AlterField(
            model_name="retosteam",
            name="categoria",
            field=models.CharField(
                choices=[
                    ("ESTRUCTURAS", "Estructuras (puentes, torres)"),
                    ("HIDRAULICA_NEUMATICA", "Hidráulica y neumática"),
                    ("MOVIMIENTO_TRANSPORTE", "Movimiento y transporte"),
                    ("CIENCIA_SOSTENIBILIDAD", "Ciencia de la Tierra y sostenibilidad"),
                    ("COMPETENCIA_EXTERNA", "Competencia externa"),
                ],
                max_length=25,
                verbose_name="Categoría",
            ),
        ),
    ]
