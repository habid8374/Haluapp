# Modelo AuditoriaExportacionContable

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("finanzas", "0006_institucioneducativa_acceso_modulo_finanzas"),
        ("gestion_academica", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditoriaExportacionContable",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("creado", models.DateTimeField(auto_now_add=True)),
                ("fecha_inicio", models.DateField()),
                ("fecha_fin", models.DateField()),
                ("tipo_transaccion", models.CharField(max_length=24)),
                ("formato", models.CharField(max_length=8)),
                ("registros", models.PositiveIntegerField(default=0)),
                (
                    "institucion",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="auditorias_exportacion_contable",
                        to="finanzas.institucioneducativa",
                    ),
                ),
                (
                    "periodo_academico",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="gestion_academica.periodoacademico",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="exportaciones_contables_generadas",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Auditoría de exportación contable",
                "verbose_name_plural": "Auditorías de exportación contable",
                "ordering": ["-creado"],
            },
        ),
    ]
