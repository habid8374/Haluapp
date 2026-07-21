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
            name="TableroTrazado",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(max_length=200, verbose_name="Título")),
                ("instrucciones", models.TextField(blank=True, default="", verbose_name="Instrucciones")),
                ("nota_maxima", models.DecimalField(decimal_places=2, default=5.0, max_digits=4, verbose_name="Nota máxima")),
                ("estado", models.CharField(
                    choices=[("BORRADOR", "Borrador"), ("PUBLICADO", "Publicado"), ("CERRADO", "Cerrado")],
                    default="BORRADOR", max_length=10, verbose_name="Estado",
                )),
                ("fecha_inicio", models.DateTimeField(blank=True, null=True, verbose_name="Disponible desde")),
                ("fecha_fin", models.DateTimeField(blank=True, null=True, verbose_name="Plazo final")),
                ("fecha_cierre", models.DateTimeField(blank=True, null=True, verbose_name="Cierre")),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actividad_calificable", models.OneToOneField(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="tablero_trazado", to="gestion_academica.actividadcalificable",
                )),
                ("creado_por", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="tableros_trazado_creados", to=settings.AUTH_USER_MODEL,
                )),
                ("curso", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="tableros_trazado",
                    to="gestion_academica.curso", verbose_name="Curso",
                )),
                ("institucion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="tableros_trazado",
                    to="finanzas.institucioneducativa", verbose_name="Institución",
                )),
                ("tipo_actividad", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, to="gestion_academica.tipoactividad",
                    verbose_name="Categoría (para el libro de notas)",
                )),
            ],
            options={
                "verbose_name": "Tablero de trazado",
                "verbose_name_plural": "Tableros de trazado",
                "ordering": ["-creado_en"],
            },
        ),
        migrations.CreateModel(
            name="PlantillaTrazado",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("orden", models.PositiveIntegerField(default=0)),
                ("texto", models.CharField(max_length=20, verbose_name="Letra o palabra a trazar")),
                ("audio", models.FileField(blank=True, null=True, upload_to="trazado/audios/")),
                ("tablero", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="plantillas",
                    to="trazado.tablerotrazado",
                )),
            ],
            options={
                "verbose_name": "Plantilla de trazado",
                "verbose_name_plural": "Plantillas de trazado",
                "ordering": ["orden", "id"],
            },
        ),
        migrations.CreateModel(
            name="IntentoTrazado",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("completado", models.BooleanField(default=False)),
                ("total", models.PositiveIntegerField(default=0)),
                ("hechas", models.PositiveIntegerField(default=0)),
                ("porcentaje", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("puntaje", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("inicio", models.DateTimeField(auto_now_add=True)),
                ("fin", models.DateTimeField(blank=True, null=True)),
                ("estudiante", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="intentos_trazado",
                    to="gestion_academica.estudiante",
                )),
                ("institucion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, to="finanzas.institucioneducativa",
                )),
                ("tablero", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="intentos",
                    to="trazado.tablerotrazado",
                )),
            ],
            options={
                "verbose_name": "Intento de trazado",
                "verbose_name_plural": "Intentos de trazado",
                "ordering": ["-inicio"],
                "unique_together": {("tablero", "estudiante")},
            },
        ),
        migrations.CreateModel(
            name="TrazoEstudiante",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("imagen", models.ImageField(upload_to="trazado/trazos/")),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("intento", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="trazos",
                    to="trazado.intentotrazado",
                )),
                ("plantilla", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, to="trazado.plantillatrazado",
                )),
            ],
            options={
                "verbose_name": "Trazo del estudiante",
                "verbose_name_plural": "Trazos del estudiante",
                "unique_together": {("intento", "plantilla")},
            },
        ),
    ]
