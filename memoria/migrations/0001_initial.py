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
            name="JuegoMemoria",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(max_length=200, verbose_name="Título")),
                ("instrucciones", models.TextField(blank=True, default="", verbose_name="Instrucciones")),
                ("nota_maxima", models.DecimalField(decimal_places=2, default=5.0, max_digits=4, verbose_name="Nota máxima")),
                ("modo_nota", models.CharField(
                    choices=[
                        ("COMPLETAR", "Completar el juego = nota máxima"),
                        ("EFICIENCIA", "Por eficiencia (menos intentos, mejor nota)"),
                    ],
                    default="COMPLETAR", max_length=12, verbose_name="Cómo se califica",
                )),
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
                    related_name="juego_memoria",
                    to="gestion_academica.actividadcalificable",
                )),
                ("creado_por", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name="juegos_memoria_creados",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("curso", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="juegos_memoria",
                    to="gestion_academica.curso",
                    verbose_name="Curso",
                )),
                ("institucion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="juegos_memoria",
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
                "verbose_name": "Juego de memoria",
                "verbose_name_plural": "Juegos de memoria",
                "ordering": ["-creado_en"],
            },
        ),
        migrations.CreateModel(
            name="ParejaMemoria",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("orden", models.PositiveIntegerField(default=0)),
                ("imagen_a", models.ImageField(blank=True, null=True, upload_to="memoria/imagenes/")),
                ("texto_a", models.CharField(blank=True, default="", max_length=60)),
                ("audio_a", models.FileField(blank=True, null=True, upload_to="memoria/audios/")),
                ("imagen_b", models.ImageField(blank=True, null=True, upload_to="memoria/imagenes/")),
                ("texto_b", models.CharField(blank=True, default="", max_length=60)),
                ("audio_b", models.FileField(blank=True, null=True, upload_to="memoria/audios/")),
                ("juego", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="parejas",
                    to="memoria.juegomemoria",
                )),
            ],
            options={
                "verbose_name": "Pareja de memoria",
                "verbose_name_plural": "Parejas de memoria",
                "ordering": ["orden", "id"],
            },
        ),
        migrations.CreateModel(
            name="IntentoMemoria",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("completado", models.BooleanField(default=False)),
                ("movimientos", models.PositiveIntegerField(default=0, verbose_name="Volteos de 2 tarjetas")),
                ("parejas_total", models.PositiveIntegerField(default=0)),
                ("porcentaje", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("puntaje", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("inicio", models.DateTimeField(auto_now_add=True)),
                ("fin", models.DateTimeField(blank=True, null=True)),
                ("estudiante", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="intentos_memoria",
                    to="gestion_academica.estudiante",
                )),
                ("institucion", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to="finanzas.institucioneducativa",
                )),
                ("juego", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="intentos",
                    to="memoria.juegomemoria",
                )),
            ],
            options={
                "verbose_name": "Intento de memoria",
                "verbose_name_plural": "Intentos de memoria",
                "ordering": ["-inicio"],
                "unique_together": {("juego", "estudiante")},
            },
        ),
    ]
