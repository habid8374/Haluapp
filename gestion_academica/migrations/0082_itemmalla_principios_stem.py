# Halu STEAM — Fase 3: alineación STEM+ del MEN.
#
# NOTA: separada a mano del autogenerado por `makemigrations`, que agrupaba
# esto con un `AlterField` de `justificacioninasistencia.id` no relacionado
# (drift preexistente de la BD, ajeno a este cambio) — mismo criterio que en
# 0078_enfasis_taller_tecnico.py y 0080_proyectos_insignias_steam.py.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestion_academica", "0081_permisos_proyectos_insignias_steam"),
    ]

    operations = [
        migrations.AddField(
            model_name="itemmalla",
            name="principios_stem",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="¿Cuáles de los 6 principios de la Visión STEM+ del MEN aplica este ítem?",
                verbose_name="Principios STEM+ (MEN)",
            ),
        ),
    ]
