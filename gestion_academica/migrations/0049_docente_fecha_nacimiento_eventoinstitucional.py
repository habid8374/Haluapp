import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("finanzas", "0023_institucioneducativa_claude_api_key"),
        ("gestion_academica", "0048_usuario_aceptacion_politica_datos"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="docente",
            name="fecha_nacimiento",
            field=models.DateField(blank=True, null=True, verbose_name="Fecha de Nacimiento"),
        ),
        migrations.CreateModel(
            name="EventoInstitucional",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(max_length=150, verbose_name="Título del evento")),
                ("descripcion", models.TextField(blank=True, default="", verbose_name="Descripción")),
                ("categoria", models.CharField(
                    choices=[
                        ("CULTURAL", "Cultural / Cívico"),
                        ("ACADEMICO", "Académico"),
                        ("INSTITUCIONAL", "Institucional"),
                        ("OTRO", "Otro"),
                    ],
                    default="INSTITUCIONAL", max_length=20,
                )),
                ("fecha", models.DateField(verbose_name="Fecha (de este año)")),
                ("recurrente_anual", models.BooleanField(
                    default=False,
                    help_text="Actívalo para festivos o celebraciones que caen en la misma fecha todos los años (ej. Amor y Amistad, fiestas patronales).",
                    verbose_name="¿Se repite cada año?",
                )),
                ("dias_aviso_previo", models.PositiveSmallIntegerField(
                    default=3,
                    help_text="Con cuántos días de anticipación se notifica a los destinatarios.",
                    verbose_name="Días de aviso previo",
                )),
                ("para_docentes", models.BooleanField(default=True, verbose_name="Avisar a docentes")),
                ("para_estudiantes", models.BooleanField(default=True, verbose_name="Avisar a estudiantes")),
                ("para_familiares", models.BooleanField(default=True, verbose_name="Avisar a familiares")),
                ("para_coordinadores", models.BooleanField(default=True, verbose_name="Avisar a coordinadores/administrador")),
                ("activo", models.BooleanField(default=True, verbose_name="¿Activo?")),
                ("ultima_alerta_fecha", models.DateField(
                    blank=True, null=True,
                    help_text="La usa el sistema para no enviar la misma alerta dos veces — no editar a mano.",
                    verbose_name="Fecha de la última ocurrencia ya avisada",
                )),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("creado_por", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="eventos_institucionales_creados",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("institucion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="eventos_institucionales",
                    to="finanzas.institucioneducativa",
                    verbose_name="Institución",
                )),
            ],
            options={
                "verbose_name": "Evento Institucional",
                "verbose_name_plural": "Eventos Institucionales",
                "ordering": ["fecha"],
            },
        ),
    ]
