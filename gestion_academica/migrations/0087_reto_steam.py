# Halu STEAM: catálogo de plantillas de retos de ingeniería/robótica (ABP).
#
# NOTA: separada a mano del autogenerado por `makemigrations`, que agrupaba
# esto con un `AlterField` de `justificacioninasistencia.id` no relacionado
# (drift preexistente de la BD, ajeno a este cambio) — mismo criterio que en
# 0078/0080/0082/0083/0084.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finanzas", "0034_seed_modulo_steam"),
        ("gestion_academica", "0086_permisos_simulaciones_steam"),
    ]

    operations = [
        migrations.CreateModel(
            name="RetoSTEAM",
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
                    "categoria",
                    models.CharField(
                        choices=[
                            ("ESTRUCTURAS", "Estructuras (puentes, torres)"),
                            ("HIDRAULICA_NEUMATICA", "Hidráulica y neumática"),
                            ("MOVIMIENTO_TRANSPORTE", "Movimiento y transporte"),
                            ("COMPETENCIA_EXTERNA", "Competencia externa"),
                        ],
                        max_length=25,
                        verbose_name="Categoría",
                    ),
                ),
                (
                    "descripcion_corta",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        verbose_name="Descripción corta (para la tarjeta)",
                    ),
                ),
                (
                    "reto_texto",
                    models.TextField(
                        blank=True,
                        help_text="Se precarga como el reto del Proyecto STEAM al usar esta plantilla.",
                        verbose_name="Reto / pregunta guía",
                    ),
                ),
                (
                    "materiales",
                    models.TextField(blank=True, verbose_name="Materiales sugeridos"),
                ),
                (
                    "criterio_evaluacion",
                    models.TextField(blank=True, verbose_name="Criterio de éxito"),
                ),
                (
                    "hitos_sugeridos",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text='Lista de {"titulo": "..."}, en orden — se crean como hitos reales al usar la plantilla.',
                        verbose_name="Hitos sugeridos",
                    ),
                ),
                (
                    "enlace_externo",
                    models.URLField(
                        blank=True,
                        verbose_name="Enlace oficial (competencias externas)",
                    ),
                ),
                (
                    "icono",
                    models.CharField(
                        default="bi-cone-striped", max_length=40, verbose_name="Ícono"
                    ),
                ),
                ("activo", models.BooleanField(default=True, verbose_name="Activo")),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                (
                    "creado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="retos_steam_creados",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Creado por",
                    ),
                ),
                (
                    "institucion",
                    models.ForeignKey(
                        blank=True,
                        help_text="Vacío = plantilla pública del catálogo de la plataforma.",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="retos_steam",
                        to="finanzas.institucioneducativa",
                        verbose_name="Institución",
                    ),
                ),
            ],
            options={
                "verbose_name": "Reto STEAM",
                "verbose_name_plural": "Retos STEAM",
                "ordering": ["categoria", "titulo"],
            },
        ),
    ]
