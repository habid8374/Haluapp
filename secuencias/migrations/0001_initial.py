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
            name="SecuenciaActividad",
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
                    related_name="secuencia", to="gestion_academica.actividadcalificable",
                )),
                ("creado_por", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="secuencias_creadas", to=settings.AUTH_USER_MODEL,
                )),
                ("curso", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="secuencias",
                    to="gestion_academica.curso", verbose_name="Curso",
                )),
                ("institucion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="secuencias",
                    to="finanzas.institucioneducativa", verbose_name="Institución",
                )),
                ("tipo_actividad", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, to="gestion_academica.tipoactividad",
                    verbose_name="Categoría (para el libro de notas)",
                )),
            ],
            options={
                "verbose_name": "Secuencia",
                "verbose_name_plural": "Secuencias",
                "ordering": ["-creado_en"],
            },
        ),
        migrations.CreateModel(
            name="ItemSecuencia",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("posicion_correcta", models.PositiveIntegerField(verbose_name="Posición correcta")),
                ("imagen", models.ImageField(blank=True, null=True, upload_to="secuencias/imagenes/")),
                ("texto", models.CharField(blank=True, default="", max_length=60)),
                ("actividad", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="items",
                    to="secuencias.secuenciaactividad",
                )),
            ],
            options={
                "verbose_name": "Elemento de secuencia",
                "verbose_name_plural": "Elementos de secuencia",
                "ordering": ["posicion_correcta", "id"],
            },
        ),
        migrations.CreateModel(
            name="IntentoSecuencia",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("completado", models.BooleanField(default=False)),
                ("aciertos", models.PositiveIntegerField(default=0)),
                ("total", models.PositiveIntegerField(default=0)),
                ("porcentaje", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("puntaje", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("respuestas", models.JSONField(blank=True, default=dict)),
                ("inicio", models.DateTimeField(auto_now_add=True)),
                ("fin", models.DateTimeField(blank=True, null=True)),
                ("actividad", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="intentos",
                    to="secuencias.secuenciaactividad",
                )),
                ("estudiante", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="intentos_secuencia",
                    to="gestion_academica.estudiante",
                )),
                ("institucion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, to="finanzas.institucioneducativa",
                )),
            ],
            options={
                "verbose_name": "Intento de secuencia",
                "verbose_name_plural": "Intentos de secuencia",
                "ordering": ["-inicio"],
                "unique_together": {("actividad", "estudiante")},
            },
        ),
    ]
