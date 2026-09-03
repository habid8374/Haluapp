# Halu STEAM: catálogo de simulaciones PhET (Universidad de Colorado Boulder,
# código abierto CC-BY) + asignación por curso.
#
# NOTA: separada a mano del autogenerado por `makemigrations`, que agrupaba
# esto con un `AlterField` de `justificacioninasistencia.id` no relacionado
# (drift preexistente de la BD, ajeno a este cambio) — mismo criterio que en
# 0078/0080/0082/0083.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finanzas", "0034_seed_modulo_steam"),
        ("gestion_academica", "0083_permisos_malla_curricular_coord_docentes"),
    ]

    operations = [
        migrations.CreateModel(
            name="SimulacionSTEAM",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "es_publica",
                    models.BooleanField(
                        default=False,
                        verbose_name="Pública (catálogo de la plataforma)",
                    ),
                ),
                ("titulo", models.CharField(max_length=150, verbose_name="Título")),
                (
                    "descripcion",
                    models.TextField(blank=True, verbose_name="Descripción"),
                ),
                (
                    "area",
                    models.CharField(
                        choices=[
                            ("FISICA", "Física"),
                            ("QUIMICA", "Química"),
                            ("MATEMATICAS", "Matemáticas"),
                            ("BIOLOGIA", "Biología"),
                            ("CIENCIAS_TIERRA", "Ciencias de la Tierra"),
                        ],
                        max_length=20,
                        verbose_name="Área",
                    ),
                ),
                (
                    "url",
                    models.URLField(
                        help_text="Por ahora solo se permiten enlaces de phet.colorado.edu.",
                        verbose_name="Enlace a la simulación",
                    ),
                ),
                (
                    "icono",
                    models.CharField(
                        default="bi-atom", max_length=40, verbose_name="Ícono"
                    ),
                ),
                ("activo", models.BooleanField(default=True, verbose_name="Activa")),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                (
                    "creado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="simulaciones_steam_creadas",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Creada por",
                    ),
                ),
                (
                    "institucion",
                    models.ForeignKey(
                        blank=True,
                        help_text="Vacío = simulación pública del catálogo de la plataforma.",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="simulaciones_steam",
                        to="finanzas.institucioneducativa",
                        verbose_name="Institución",
                    ),
                ),
            ],
            options={
                "verbose_name": "Simulación STEAM",
                "verbose_name_plural": "Simulaciones STEAM",
                "ordering": ["area", "titulo"],
            },
        ),
        migrations.CreateModel(
            name="AsignacionSimulacionSTEAM",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "nota",
                    models.TextField(
                        blank=True,
                        verbose_name="Instrucciones para el estudiante (opcional)",
                    ),
                ),
                (
                    "fecha_limite",
                    models.DateField(
                        blank=True, null=True, verbose_name="Fecha límite (opcional)"
                    ),
                ),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                (
                    "asignado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="simulaciones_steam_asignadas",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Asignado por",
                    ),
                ),
                (
                    "curso",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="simulaciones_steam_asignadas",
                        to="gestion_academica.curso",
                        verbose_name="Curso",
                    ),
                ),
                (
                    "institucion",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="asignaciones_simulaciones_steam",
                        to="finanzas.institucioneducativa",
                        verbose_name="Institución",
                    ),
                ),
                (
                    "simulacion",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="asignaciones",
                        to="gestion_academica.simulacionsteam",
                        verbose_name="Simulación",
                    ),
                ),
            ],
            options={
                "verbose_name": "Asignación de Simulación STEAM",
                "verbose_name_plural": "Asignaciones de Simulaciones STEAM",
                "ordering": ["-creado_en"],
                "unique_together": {("simulacion", "curso")},
            },
        ),
    ]
