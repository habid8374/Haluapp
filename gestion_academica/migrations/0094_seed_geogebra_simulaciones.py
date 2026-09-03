# Siembra 4 herramientas oficiales de GeoGebra (no materiales de comunidad,
# que pueden desaparecer) en el catálogo público de Simulaciones STEAM.
# Cada URL es una app oficial de geogebra.org, verificada antes de sembrarla.
from django.db import migrations


SIMULACIONES = [
    (
        "GeoGebra: Calculadora Gráfica",
        "MATEMATICAS",
        "https://www.geogebra.org/graphing?lang=es",
        "bi-graph-up",
        "Grafica funciones, ecuaciones e inecuaciones y explora cómo cambian sus parámetros en tiempo real.",
    ),
    (
        "GeoGebra: Calculadora de Geometría",
        "MATEMATICAS",
        "https://www.geogebra.org/geometry?lang=es",
        "bi-diagram-3",
        "Construye figuras geométricas, mide ángulos y longitudes, y explora transformaciones de forma interactiva.",
    ),
    (
        "GeoGebra: Calculadora 3D",
        "MATEMATICAS",
        "https://www.geogebra.org/3d?lang=es",
        "bi-boxes",
        "Grafica funciones y superficies en 3D, construye sólidos geométricos y gíralos para verlos desde cualquier ángulo.",
    ),
    (
        "GeoGebra Classic (todo en uno)",
        "MATEMATICAS",
        "https://www.geogebra.org/classic?lang=es",
        "bi-calculator-fill",
        "La suite completa de GeoGebra: álgebra, geometría, estadística, cálculo y 3D en una sola herramienta.",
    ),
]


def sembrar(apps, schema_editor):
    SimulacionSTEAM = apps.get_model('gestion_academica', 'SimulacionSTEAM')
    for titulo, area, url, icono, descripcion in SIMULACIONES:
        SimulacionSTEAM.objects.get_or_create(
            institucion=None,
            titulo=titulo,
            defaults={
                'es_publica': True,
                'area': area,
                'url': url,
                'icono': icono,
                'descripcion': descripcion,
                'activo': True,
            },
        )


def revertir(apps, schema_editor):
    SimulacionSTEAM = apps.get_model('gestion_academica', 'SimulacionSTEAM')
    titulos = [s[0] for s in SIMULACIONES]
    SimulacionSTEAM.objects.filter(institucion__isnull=True, titulo__in=titulos).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("gestion_academica", "0093_reto_steam_categorias_electricidad_herramienta"),
    ]

    operations = [
        migrations.RunPython(sembrar, revertir),
    ]
