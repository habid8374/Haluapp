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
            name="MazoFlashcard",
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
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="mazo_flashcard",
                    to="gestion_academica.actividadcalificable",
                )),
                ("creado_por", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="mazos_flashcards_creados",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("curso", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="mazos_flashcards",
                    to="gestion_academica.curso",
                    verbose_name="Curso",
                )),
                ("institucion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="mazos_flashcards",
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
                "verbose_name": "Mazo de flash cards",
                "verbose_name_plural": "Mazos de flash cards",
                "ordering": ["-creado_en"],
            },
        ),
        migrations.CreateModel(
            name="TarjetaFlashcard",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("orden", models.PositiveIntegerField(default=0)),
                ("imagen", models.ImageField(blank=True, null=True, upload_to="flashcards/imagenes/")),
                ("pista", models.CharField(max_length=300, verbose_name="Descripción / pista")),
                ("audio", models.FileField(blank=True, null=True, upload_to="flashcards/audios/")),
                ("respuesta", models.CharField(max_length=80, verbose_name="Respuesta correcta")),
                ("mazo", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="tarjetas",
                    to="flashcards.mazoflashcard",
                )),
            ],
            options={
                "verbose_name": "Flash card",
                "verbose_name_plural": "Flash cards",
                "ordering": ["orden", "id"],
            },
        ),
        migrations.CreateModel(
            name="IntentoFlashcard",
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
                ("estudiante", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="intentos_flashcards",
                    to="gestion_academica.estudiante",
                )),
                ("institucion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to="finanzas.institucioneducativa",
                )),
                ("mazo", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="intentos",
                    to="flashcards.mazoflashcard",
                )),
            ],
            options={
                "verbose_name": "Intento de flash cards",
                "verbose_name_plural": "Intentos de flash cards",
                "ordering": ["-inicio"],
                "unique_together": {("mazo", "estudiante")},
            },
        ),
    ]
