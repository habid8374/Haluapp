# gestion_academica/migrations/0023_intentoactividad_multiples_intentos.py

import django.core.validators
from django.db import migrations, models
from django.db.models import Count, Q


def dedupe_intentos_en_progreso(apps, schema_editor):
    IntentoActividad = apps.get_model("gestion_academica", "IntentoActividad")
    grouped = (
        IntentoActividad.objects.filter(estado="en_progreso")
        .values("estudiante_id", "actividad_id")
        .annotate(c=Count("id"))
        .filter(c__gt=1)
    )
    for g in grouped:
        rows = list(
            IntentoActividad.objects.filter(
                estudiante_id=g["estudiante_id"],
                actividad_id=g["actividad_id"],
                estado="en_progreso",
            ).order_by("-inicio")
        )
        for old in rows[1:]:
            old.delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("gestion_academica", "0022_docente_modalidad_asistencia_entrada_salida"),
    ]

    operations = [
        migrations.RunPython(dedupe_intentos_en_progreso, noop_reverse),
        migrations.AlterUniqueTogether(
            name="intentoactividad",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="intentoactividad",
            constraint=models.UniqueConstraint(
                condition=Q(estado="en_progreso"),
                fields=("estudiante", "actividad"),
                name="ga_intentoactividad_uniq_en_progreso",
            ),
        ),
        migrations.AlterField(
            model_name="actividadcalificable",
            name="numero_intentos_permitidos",
            field=models.PositiveIntegerField(
                default=5,
                help_text=(
                    "Veces que el estudiante puede iniciar la actividad (cada sesión cuenta). "
                    "Por defecto 5, adecuado para etapa escolar; máximo 20 para evaluaciones especiales."
                ),
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(20),
                ],
                verbose_name="Número de Intentos Permitidos",
            ),
        ),
    ]
