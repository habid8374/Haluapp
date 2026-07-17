import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("finanzas", "0022_pagoregistrado_pago_inst_fecha_idx"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ComponenteGestion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("area", models.CharField(
                    choices=[
                        ("DIRECTIVA", "Gestión Directiva"),
                        ("ACADEMICA", "Gestión Académica"),
                        ("ADMINISTRATIVA", "Gestión Administrativa y Financiera"),
                        ("COMUNIDAD", "Gestión de la Comunidad"),
                    ],
                    max_length=20, verbose_name="Área de gestión",
                )),
                ("nombre", models.CharField(max_length=255, verbose_name="Componente")),
                ("descripcion", models.CharField(blank=True, default="", max_length=500, verbose_name="Descripción (opcional)")),
                ("orden", models.PositiveIntegerField(default=0, verbose_name="Orden")),
                ("activo", models.BooleanField(default=True, verbose_name="Activo")),
                ("institucion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="componentes_autoeval",
                    to="finanzas.institucioneducativa",
                    verbose_name="Institución",
                )),
            ],
            options={
                "verbose_name": "Componente de gestión",
                "verbose_name_plural": "Componentes de gestión",
                "ordering": ["area", "orden", "id"],
            },
        ),
        migrations.CreateModel(
            name="AutoevaluacionInstitucional",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("anio", models.PositiveIntegerField(verbose_name="Año")),
                ("titulo", models.CharField(max_length=200, verbose_name="Título")),
                ("estado", models.CharField(
                    choices=[("BORRADOR", "Borrador"), ("EN_PROCESO", "En proceso"), ("CERRADA", "Cerrada")],
                    default="BORRADOR", max_length=12, verbose_name="Estado",
                )),
                ("creada_en", models.DateTimeField(auto_now_add=True)),
                ("cerrada_en", models.DateTimeField(blank=True, null=True)),
                ("creada_por", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="autoevaluaciones_creadas",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("institucion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="autoevaluaciones",
                    to="finanzas.institucioneducativa",
                    verbose_name="Institución",
                )),
            ],
            options={
                "verbose_name": "Autoevaluación institucional",
                "verbose_name_plural": "Autoevaluaciones institucionales",
                "ordering": ["-anio", "-creada_en"],
            },
        ),
        migrations.CreateModel(
            name="ValoracionGestion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("valor", models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Valoración (1–4)")),
                ("observaciones", models.TextField(blank=True, default="", verbose_name="Observaciones / evidencias")),
                ("accion_mejora", models.TextField(blank=True, default="", verbose_name="Acción de mejora")),
                ("autoevaluacion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="valoraciones",
                    to="autoevaluacion_institucional.autoevaluacioninstitucional",
                )),
                ("componente", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    to="autoevaluacion_institucional.componentegestion",
                )),
            ],
            options={
                "verbose_name": "Valoración de gestión",
                "verbose_name_plural": "Valoraciones de gestión",
                "ordering": ["componente__area", "componente__orden", "componente__id"],
                "unique_together": {("autoevaluacion", "componente")},
            },
        ),
    ]
