# Halu STEAM — Fase 2: Proyectos (ABP) e Insignias/microcredenciales.
#
# NOTA: separada a mano del autogenerado por `makemigrations`, que agrupaba
# esto con un `AlterField` de `justificacioninasistencia.id` no relacionado
# (drift preexistente de la BD, ajeno a este cambio) — mismo criterio que en
# 0078_enfasis_taller_tecnico.py.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finanzas", "0034_seed_modulo_steam"),
        ("gestion_academica", "0079_enfasis_permisos_coordinadores"),
    ]

    operations = [
        migrations.CreateModel(
            name="Insignia",
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
                    "nombre",
                    models.CharField(
                        max_length=100, verbose_name="Nombre de la insignia"
                    ),
                ),
                (
                    "descripcion",
                    models.TextField(
                        blank=True, verbose_name="Criterio para obtenerla"
                    ),
                ),
                (
                    "icono",
                    models.CharField(
                        default="bi-award-fill",
                        help_text="Clase de Bootstrap Icons, ej. 'bi-award-fill'.",
                        max_length=40,
                        verbose_name="Ícono",
                    ),
                ),
                (
                    "color",
                    models.CharField(
                        default="#7c3aed",
                        help_text="Color hexadecimal, ej. #7c3aed.",
                        max_length=7,
                        verbose_name="Color",
                    ),
                ),
                ("activo", models.BooleanField(default=True, verbose_name="Activa")),
                (
                    "institucion",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="insignias",
                        to="finanzas.institucioneducativa",
                        verbose_name="Institución",
                    ),
                ),
            ],
            options={
                "verbose_name": "Insignia",
                "verbose_name_plural": "Insignias",
                "ordering": ["nombre"],
                "unique_together": {("institucion", "nombre")},
            },
        ),
        migrations.CreateModel(
            name="ProyectoSTEAM",
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
                    "titulo",
                    models.CharField(
                        max_length=200, verbose_name="Título del proyecto"
                    ),
                ),
                (
                    "reto",
                    models.TextField(
                        blank=True,
                        help_text="¿Qué problema real intenta resolver este proyecto?",
                        verbose_name="Reto / pregunta guía",
                    ),
                ),
                (
                    "fecha_inicio",
                    models.DateField(
                        blank=True, null=True, verbose_name="Fecha de inicio"
                    ),
                ),
                (
                    "fecha_entrega",
                    models.DateField(
                        blank=True, null=True, verbose_name="Fecha de entrega"
                    ),
                ),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("PLANEACION", "En planeación"),
                            ("EN_CURSO", "En curso"),
                            ("ENTREGADO", "Entregado"),
                            ("EVALUADO", "Evaluado"),
                        ],
                        default="PLANEACION",
                        max_length=12,
                        verbose_name="Estado",
                    ),
                ),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                (
                    "actividad_calificable",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="proyecto_steam",
                        to="gestion_academica.actividadcalificable",
                        verbose_name="Actividad calificable enlazada",
                    ),
                ),
                (
                    "creado_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="proyectos_steam_creados",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Creado por",
                    ),
                ),
                (
                    "curso",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="proyectos_steam",
                        to="gestion_academica.curso",
                        verbose_name="Curso",
                    ),
                ),
                (
                    "institucion",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="proyectos_steam",
                        to="finanzas.institucioneducativa",
                        verbose_name="Institución",
                    ),
                ),
            ],
            options={
                "verbose_name": "Proyecto STEAM",
                "verbose_name_plural": "Proyectos STEAM",
                "ordering": ["-creado_en"],
            },
        ),
        migrations.CreateModel(
            name="InsigniaObtenida",
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
                    models.CharField(
                        blank=True, max_length=255, verbose_name="Comentario (opcional)"
                    ),
                ),
                (
                    "fecha_obtenida",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Fecha obtenida"
                    ),
                ),
                (
                    "estudiante",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="insignias_obtenidas",
                        to="gestion_academica.estudiante",
                        verbose_name="Estudiante",
                    ),
                ),
                (
                    "insignia",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="otorgadas",
                        to="gestion_academica.insignia",
                        verbose_name="Insignia",
                    ),
                ),
                (
                    "institucion",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="insignias_otorgadas",
                        to="finanzas.institucioneducativa",
                        verbose_name="Institución",
                    ),
                ),
                (
                    "otorgada_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="insignias_steam_otorgadas",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Otorgada por",
                    ),
                ),
                (
                    "proyecto",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="insignias_otorgadas",
                        to="gestion_academica.proyectosteam",
                        verbose_name="Proyecto de origen (opcional)",
                    ),
                ),
            ],
            options={
                "verbose_name": "Insignia Obtenida",
                "verbose_name_plural": "Insignias Obtenidas",
                "ordering": ["-fecha_obtenida"],
            },
        ),
        migrations.CreateModel(
            name="HitoProyecto",
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
                ("titulo", models.CharField(max_length=200, verbose_name="Hito")),
                (
                    "fecha_limite",
                    models.DateField(
                        blank=True, null=True, verbose_name="Fecha límite"
                    ),
                ),
                (
                    "completado",
                    models.BooleanField(default=False, verbose_name="Completado"),
                ),
                ("orden", models.PositiveIntegerField(default=0, verbose_name="Orden")),
                (
                    "proyecto",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="hitos",
                        to="gestion_academica.proyectosteam",
                        verbose_name="Proyecto",
                    ),
                ),
            ],
            options={
                "verbose_name": "Hito de Proyecto",
                "verbose_name_plural": "Hitos de Proyecto",
                "ordering": ["orden", "fecha_limite"],
            },
        ),
        migrations.CreateModel(
            name="EvidenciaProyecto",
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
                    "titulo",
                    models.CharField(
                        max_length=200, verbose_name="Título de la evidencia"
                    ),
                ),
                (
                    "url",
                    models.URLField(
                        help_text="Solo URLs http:// o https://",
                        verbose_name="Enlace (foto, video o documento)",
                    ),
                ),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                (
                    "subido_por",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="evidencias_steam_subidas",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Subido por",
                    ),
                ),
                (
                    "proyecto",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="evidencias",
                        to="gestion_academica.proyectosteam",
                        verbose_name="Proyecto",
                    ),
                ),
            ],
            options={
                "verbose_name": "Evidencia de Proyecto",
                "verbose_name_plural": "Evidencias de Proyecto",
                "ordering": ["-creado_en"],
            },
        ),
        migrations.CreateModel(
            name="ParticipanteProyecto",
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
                    "rol",
                    models.CharField(
                        blank=True,
                        help_text="Ej: Líder, Diseñador, Documentador.",
                        max_length=100,
                        verbose_name="Rol en el equipo",
                    ),
                ),
                (
                    "estudiante",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="proyectos_steam_participados",
                        to="gestion_academica.estudiante",
                        verbose_name="Estudiante",
                    ),
                ),
                (
                    "proyecto",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="participantes",
                        to="gestion_academica.proyectosteam",
                        verbose_name="Proyecto",
                    ),
                ),
            ],
            options={
                "verbose_name": "Participante de Proyecto",
                "verbose_name_plural": "Participantes de Proyecto",
                "ordering": ["estudiante__usuario__last_name"],
                "unique_together": {("proyecto", "estudiante")},
            },
        ),
    ]
