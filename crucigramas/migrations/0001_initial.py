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
            name="Crucigrama",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(max_length=200, verbose_name="Título")),
                ("instrucciones", models.TextField(blank=True, default="", verbose_name="Instrucciones")),
                ("nota_maxima", models.DecimalField(decimal_places=2, default=5.0, max_digits=4, verbose_name="Nota máxima")),
                ("estado", models.CharField(
                    choices=[("BORRADOR", "Borrador"), ("PUBLICADO", "Publicado"), ("CERRADO", "Cerrado")],
                    default="BORRADOR", max_length=10, verbose_name="Estado",
                )),
                ("fecha_cierre", models.DateTimeField(blank=True, null=True, verbose_name="Cierre")),
                ("filas", models.PositiveIntegerField(default=0)),
                ("columnas", models.PositiveIntegerField(default=0)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actividad_calificable", models.OneToOneField(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="crucigrama",
                    to="gestion_academica.actividadcalificable",
                )),
                ("creado_por", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="crucigramas_creados",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("curso", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="crucigramas",
                    to="gestion_academica.curso",
                    verbose_name="Curso",
                )),
                ("institucion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="crucigramas",
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
                "verbose_name": "Crucigrama",
                "verbose_name_plural": "Crucigramas",
                "ordering": ["-creado_en"],
            },
        ),
        migrations.CreateModel(
            name="PalabraCrucigrama",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("respuesta", models.CharField(max_length=40, verbose_name="Respuesta")),
                ("pista", models.CharField(max_length=300, verbose_name="Pista")),
                ("orden", models.PositiveIntegerField(default=0)),
                ("fila", models.IntegerField(blank=True, null=True)),
                ("columna", models.IntegerField(blank=True, null=True)),
                ("direccion", models.CharField(
                    blank=True, null=True,
                    choices=[("H", "Horizontal"), ("V", "Vertical")], max_length=1,
                )),
                ("numero", models.PositiveIntegerField(blank=True, null=True, verbose_name="N.º de pista")),
                ("crucigrama", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="palabras",
                    to="crucigramas.crucigrama",
                )),
            ],
            options={
                "verbose_name": "Palabra de crucigrama",
                "verbose_name_plural": "Palabras de crucigrama",
                "ordering": ["numero", "orden", "id"],
            },
        ),
        migrations.CreateModel(
            name="IntentoCrucigrama",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("completado", models.BooleanField(default=False)),
                ("porcentaje", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("puntaje", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("aciertos", models.PositiveIntegerField(default=0)),
                ("total", models.PositiveIntegerField(default=0)),
                ("respuestas", models.JSONField(blank=True, default=dict)),
                ("inicio", models.DateTimeField(auto_now_add=True)),
                ("fin", models.DateTimeField(blank=True, null=True)),
                ("crucigrama", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="intentos",
                    to="crucigramas.crucigrama",
                )),
                ("estudiante", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="intentos_crucigrama",
                    to="gestion_academica.estudiante",
                )),
                ("institucion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to="finanzas.institucioneducativa",
                )),
            ],
            options={
                "verbose_name": "Intento de crucigrama",
                "verbose_name_plural": "Intentos de crucigrama",
                "ordering": ["-inicio"],
                "unique_together": {("crucigrama", "estudiante")},
            },
        ),
    ]
