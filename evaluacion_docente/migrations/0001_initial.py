import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("finanzas", "0022_pagoregistrado_pago_inst_fecha_idx"),
        ("gestion_academica", "0047_alter_registroasistencia_fecha_solo_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CriterioEvaluacion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("texto", models.CharField(max_length=255, verbose_name="Criterio / pregunta")),
                ("descripcion", models.CharField(blank=True, default="", max_length=255, verbose_name="Ayuda (opcional)")),
                ("orden", models.PositiveIntegerField(default=0, verbose_name="Orden")),
                ("activo", models.BooleanField(default=True, verbose_name="Activo")),
                ("institucion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="criterios_eval_docente",
                    to="finanzas.institucioneducativa",
                    verbose_name="Institución",
                )),
            ],
            options={
                "verbose_name": "Criterio de evaluación docente",
                "verbose_name_plural": "Criterios de evaluación docente",
                "ordering": ["orden", "id"],
            },
        ),
        migrations.CreateModel(
            name="CampanaEvaluacion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(max_length=200, verbose_name="Título")),
                ("estado", models.CharField(
                    choices=[("BORRADOR", "Borrador"), ("ABIERTA", "Abierta"), ("CERRADA", "Cerrada")],
                    default="BORRADOR", max_length=10, verbose_name="Estado",
                )),
                ("fecha_apertura", models.DateField(blank=True, null=True, verbose_name="Apertura")),
                ("fecha_cierre", models.DateField(blank=True, null=True, verbose_name="Cierre")),
                ("creada_en", models.DateTimeField(auto_now_add=True)),
                ("creada_por", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="campanas_eval_creadas",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("institucion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="campanas_eval_docente",
                    to="finanzas.institucioneducativa",
                    verbose_name="Institución",
                )),
                ("periodo_academico", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="campanas_eval_docente",
                    to="gestion_academica.periodoacademico",
                    verbose_name="Periodo académico",
                )),
            ],
            options={
                "verbose_name": "Campaña de evaluación docente",
                "verbose_name_plural": "Campañas de evaluación docente",
                "ordering": ["-creada_en"],
            },
        ),
        migrations.CreateModel(
            name="RespuestaEvaluacion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("anonimo", models.BooleanField(default=False, verbose_name="Respuesta anónima")),
                ("comentario", models.TextField(blank=True, default="", verbose_name="Comentario")),
                ("fecha", models.DateTimeField(auto_now_add=True)),
                ("campana", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="respuestas",
                    to="evaluacion_docente.campanaevaluacion",
                )),
                ("institucion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to="finanzas.institucioneducativa",
                )),
                ("docente", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="evaluaciones_recibidas",
                    to="gestion_academica.docente",
                )),
                ("curso", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to="gestion_academica.curso",
                )),
                ("estudiante", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to="gestion_academica.estudiante",
                )),
                ("familiar", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="evaluaciones_docente_hechas",
                    to="gestion_academica.familiar",
                )),
            ],
            options={
                "verbose_name": "Respuesta de evaluación docente",
                "verbose_name_plural": "Respuestas de evaluación docente",
                "indexes": [
                    models.Index(fields=["campana", "docente"], name="evaldoc_camp_doc_idx"),
                    models.Index(fields=["institucion", "campana"], name="evaldoc_inst_camp_idx"),
                ],
                "unique_together": {("campana", "docente", "curso", "estudiante", "familiar")},
            },
        ),
        migrations.CreateModel(
            name="ValoracionCriterio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("valor", models.PositiveSmallIntegerField(verbose_name="Valor (1–5)")),
                ("criterio", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    to="evaluacion_docente.criterioevaluacion",
                )),
                ("respuesta", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="valoraciones",
                    to="evaluacion_docente.respuestaevaluacion",
                )),
            ],
            options={
                "verbose_name": "Valoración de criterio",
                "verbose_name_plural": "Valoraciones de criterio",
                "unique_together": {("respuesta", "criterio")},
            },
        ),
    ]
