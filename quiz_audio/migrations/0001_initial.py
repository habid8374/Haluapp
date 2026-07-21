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
            name="QuizAudio",
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
                    related_name="quiz_audio", to="gestion_academica.actividadcalificable",
                )),
                ("creado_por", models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name="quices_audio_creados", to=settings.AUTH_USER_MODEL,
                )),
                ("curso", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="quices_audio",
                    to="gestion_academica.curso", verbose_name="Curso",
                )),
                ("institucion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="quices_audio",
                    to="finanzas.institucioneducativa", verbose_name="Institución",
                )),
                ("tipo_actividad", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, to="gestion_academica.tipoactividad",
                    verbose_name="Categoría (para el libro de notas)",
                )),
            ],
            options={
                "verbose_name": "Quiz de audio",
                "verbose_name_plural": "Quices de audio",
                "ordering": ["-creado_en"],
            },
        ),
        migrations.CreateModel(
            name="PreguntaAudio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("orden", models.PositiveIntegerField(default=0)),
                ("audio", models.FileField(upload_to="quiz_audio/audios/")),
                ("enunciado", models.CharField(blank=True, default="", max_length=200, verbose_name="Texto (opcional)")),
                ("quiz", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="preguntas",
                    to="quiz_audio.quizaudio",
                )),
            ],
            options={
                "verbose_name": "Pregunta de audio",
                "verbose_name_plural": "Preguntas de audio",
                "ordering": ["orden", "id"],
            },
        ),
        migrations.CreateModel(
            name="OpcionAudio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("orden", models.PositiveIntegerField(default=0)),
                ("imagen", models.ImageField(blank=True, null=True, upload_to="quiz_audio/imagenes/")),
                ("texto", models.CharField(blank=True, default="", max_length=60)),
                ("es_correcta", models.BooleanField(default=False)),
                ("pregunta", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="opciones",
                    to="quiz_audio.preguntaaudio",
                )),
            ],
            options={
                "verbose_name": "Opción de audio",
                "verbose_name_plural": "Opciones de audio",
                "ordering": ["orden", "id"],
            },
        ),
        migrations.CreateModel(
            name="IntentoQuizAudio",
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
                    on_delete=django.db.models.deletion.CASCADE, related_name="intentos_quiz_audio",
                    to="gestion_academica.estudiante",
                )),
                ("institucion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, to="finanzas.institucioneducativa",
                )),
                ("quiz", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE, related_name="intentos",
                    to="quiz_audio.quizaudio",
                )),
            ],
            options={
                "verbose_name": "Intento de quiz de audio",
                "verbose_name_plural": "Intentos de quiz de audio",
                "ordering": ["-inicio"],
                "unique_together": {("quiz", "estudiante")},
            },
        ),
    ]
