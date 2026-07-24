import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("finanzas", "0023_institucioneducativa_claude_api_key"),
        ("gestion_academica", "0048_usuario_aceptacion_politica_datos"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Rompecabezas",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(max_length=200, verbose_name="Título")),
                ("instrucciones", models.TextField(blank=True, default="", verbose_name="Instrucciones")),
                ("imagen", models.ImageField(upload_to="rompecabezas/imagenes/", verbose_name="Imagen")),
                ("filas", models.PositiveIntegerField(default=3, verbose_name="Filas")),
                ("columnas", models.PositiveIntegerField(default=3, verbose_name="Columnas")),
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
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="rompecabezas",
                    to="gestion_academica.actividadcalificable",
                )),
                ("creado_por", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="rompecabezas_creados",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("curso", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rompecabezas",
                    to="gestion_academica.curso",
                    verbose_name="Curso",
                )),
                ("institucion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="rompecabezas",
                    to="finanzas.institucioneducativa",
                    verbose_name="Institución",
                )),
                ("tipo_actividad", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    to="gestion_academica.tipoactividad",
                    verbose_name="Categoría (para el libro de notas)",
                )),
            ],
            options={
                "verbose_name": "Rompecabezas",
                "verbose_name_plural": "Rompecabezas",
                "ordering": ["-creado_en"],
            },
        ),
        migrations.CreateModel(
            name="IntentoRompecabezas",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("completado", models.BooleanField(default=False)),
                ("movimientos", models.PositiveIntegerField(default=0, verbose_name="Movimientos")),
                ("tiempo_segundos", models.PositiveIntegerField(blank=True, null=True, verbose_name="Tiempo (segundos)")),
                ("puntaje", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("inicio", models.DateTimeField(auto_now_add=True)),
                ("fin", models.DateTimeField(blank=True, null=True)),
                ("estudiante", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="intentos_rompecabezas",
                    to="gestion_academica.estudiante",
                )),
                ("institucion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to="finanzas.institucioneducativa",
                )),
                ("rompecabezas", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="intentos",
                    to="rompecabezas.rompecabezas",
                )),
            ],
            options={
                "verbose_name": "Intento de rompecabezas",
                "verbose_name_plural": "Intentos de rompecabezas",
                "ordering": ["-inicio"],
                "unique_together": {("rompecabezas", "estudiante")},
            },
        ),
    ]
