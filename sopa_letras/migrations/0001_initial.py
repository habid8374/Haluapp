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
            name="Sopa",
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
                ("tamano", models.PositiveIntegerField(default=0)),
                ("grid", models.JSONField(blank=True, default=list)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actividad_calificable", models.OneToOneField(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="sopa_letras",
                    to="gestion_academica.actividadcalificable",
                )),
                ("creado_por", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="sopas_creadas",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("curso", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="sopas_letras",
                    to="gestion_academica.curso",
                    verbose_name="Curso",
                )),
                ("institucion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="sopas_letras",
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
                "verbose_name": "Sopa de letras",
                "verbose_name_plural": "Sopas de letras",
                "ordering": ["-creado_en"],
            },
        ),
        migrations.CreateModel(
            name="PalabraSopa",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("texto", models.CharField(max_length=40, verbose_name="Palabra")),
                ("orden", models.PositiveIntegerField(default=0)),
                ("fila", models.IntegerField(blank=True, null=True)),
                ("columna", models.IntegerField(blank=True, null=True)),
                ("df", models.IntegerField(blank=True, null=True)),
                ("dc", models.IntegerField(blank=True, null=True)),
                ("sopa", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="palabras",
                    to="sopa_letras.sopa",
                )),
            ],
            options={
                "verbose_name": "Palabra de sopa",
                "verbose_name_plural": "Palabras de sopa",
                "ordering": ["orden", "id"],
            },
        ),
        migrations.CreateModel(
            name="IntentoSopa",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("completado", models.BooleanField(default=False)),
                ("encontradas", models.PositiveIntegerField(default=0)),
                ("total", models.PositiveIntegerField(default=0)),
                ("porcentaje", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("puntaje", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("selecciones", models.JSONField(blank=True, default=list)),
                ("inicio", models.DateTimeField(auto_now_add=True)),
                ("fin", models.DateTimeField(blank=True, null=True)),
                ("estudiante", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="intentos_sopa",
                    to="gestion_academica.estudiante",
                )),
                ("institucion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to="finanzas.institucioneducativa",
                )),
                ("sopa", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="intentos",
                    to="sopa_letras.sopa",
                )),
            ],
            options={
                "verbose_name": "Intento de sopa",
                "verbose_name_plural": "Intentos de sopa",
                "ordering": ["-inicio"],
                "unique_together": {("sopa", "estudiante")},
            },
        ),
    ]
