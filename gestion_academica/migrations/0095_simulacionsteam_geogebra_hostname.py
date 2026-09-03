# Habilita GeoGebra como segunda fuente válida de Simulaciones STEAM
# (junto a PhET): actualiza el ícono por defecto (bi-atom no existe en
# Bootstrap Icons — mismo bug ya corregido en 0090 para datos ya sembrados,
# esto corrige el default del campo) y el texto de ayuda de la URL.
#
# NOTA: separada a mano del autogenerado por `makemigrations`, que agrupaba
# esto con un `AlterField` de `justificacioninasistencia.id` no relacionado
# (drift preexistente de la BD) — mismo criterio que en migraciones
# anteriores de este módulo (0078/0080/.../0093).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestion_academica", "0094_seed_geogebra_simulaciones"),
    ]

    operations = [
        migrations.AlterField(
            model_name="simulacionsteam",
            name="icono",
            field=models.CharField(
                default="bi-graph-up-arrow", max_length=40, verbose_name="Ícono"
            ),
        ),
        migrations.AlterField(
            model_name="simulacionsteam",
            name="url",
            field=models.URLField(
                help_text="Por ahora solo se permiten enlaces de phet.colorado.edu o geogebra.org.",
                verbose_name="Enlace a la simulación",
            ),
        ),
    ]
