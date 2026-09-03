# Agrega dos categorías más al catálogo de Retos STEAM:
# "Electricidad y electrónica" (retos de circuitos) y "Herramienta externa"
# (para tarjetas informativas de herramientas gratuitas como Tinkercad —
# igual que las de competencia externa, pero no son una competencia).
#
# NOTA: separada a mano del autogenerado por `makemigrations`, que agrupaba
# esto con un `AlterField` de `justificacioninasistencia.id` no relacionado
# (drift preexistente de la BD) — mismo criterio que en migraciones
# anteriores de este módulo (0078/0080/.../0091).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestion_academica", "0092_seed_retos_steam_lote2"),
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
                    ("ELECTRICIDAD_ELECTRONICA", "Electricidad y electrónica"),
                    ("COMPETENCIA_EXTERNA", "Competencia externa"),
                    ("HERRAMIENTA_EXTERNA", "Herramienta externa"),
                ],
                max_length=25,
                verbose_name="Categoría",
            ),
        ),
    ]
