# Siembra el catálogo público (institucion=NULL, es_publica=True) de
# simulaciones PhET (Universidad de Colorado Boulder — código abierto,
# licencia CC-BY: https://phet.colorado.edu/en/about/source-code).
#
# Cada URL fue verificada como una página real y vigente de phet.colorado.edu
# antes de sembrarla — no se inventó ningún enlace.
from django.db import migrations


SIMULACIONES = [
    # (titulo, area, url, icono, descripcion)
    (
        "Kit de Construcción de Circuitos: CD",
        "FISICA",
        "https://phet.colorado.edu/en/simulations/circuit-construction-kit-dc",
        "bi-lightning-charge-fill",
        "Arma circuitos eléctricos con pilas, resistencias, bombillos e interruptores y observa cómo fluye la corriente.",
    ),
    (
        "Kit de Construcción de Circuitos: CD — Laboratorio Virtual",
        "FISICA",
        "https://phet.colorado.edu/en/simulations/circuit-construction-kit-dc-virtual-lab",
        "bi-lightning-charge-fill",
        "Versión avanzada del kit de circuitos: mide voltaje y corriente con un multímetro virtual.",
    ),
    (
        "Fuerzas y Movimiento: Básico",
        "FISICA",
        "https://phet.colorado.edu/en/simulations/forces-and-motion-basics",
        "bi-arrow-left-right",
        "Explora cómo la fuerza, la fricción y la masa afectan el movimiento de los objetos.",
    ),
    (
        "Ley de Ohm",
        "FISICA",
        "https://phet.colorado.edu/en/simulations/ohms-law",
        "bi-plug-fill",
        "Ve cómo se relacionan voltaje, corriente y resistencia en un circuito simple.",
    ),
    (
        "Balancín",
        "FISICA",
        "https://phet.colorado.edu/en/simulations/balancing-act",
        "bi-arrows-collapse",
        "Descubre las reglas del equilibrio y el torque jugando con un sube y baja.",
    ),
    (
        "Estados de la Materia: Básico",
        "QUIMICA",
        "https://phet.colorado.edu/en/simulations/states-of-matter-basics",
        "bi-droplet-half",
        "Calienta y enfría sustancias para ver cómo cambian entre sólido, líquido y gas.",
    ),
    (
        "Construye un Átomo",
        "QUIMICA",
        "https://phet.colorado.edu/en/simulations/build-an-atom",
        "bi-magnet-fill",
        "Agrega protones, neutrones y electrones para construir un átomo y descubre el elemento, la masa y la carga.",
    ),
    (
        "Escala de pH",
        "QUIMICA",
        "https://phet.colorado.edu/en/simulations/ph-scale",
        "bi-eyedropper",
        "Prueba el pH de líquidos cotidianos y de tu propia mezcla — ¿ácido, neutro o básico?",
    ),
    (
        "Densidad",
        "QUIMICA",
        "https://phet.colorado.edu/en/simulations/density",
        "bi-box-seam",
        "Compara masa, volumen y densidad de distintos materiales y descubre por qué unos flotan y otros se hunden.",
    ),
    (
        "Graficar Líneas",
        "MATEMATICAS",
        "https://phet.colorado.edu/en/simulations/graphing-lines",
        "bi-graph-up",
        "Explora la relación entre ecuaciones lineales, pendiente y gráficas — incluye un juego de retos.",
    ),
    (
        "Comparador de Fracciones",
        "MATEMATICAS",
        "https://phet.colorado.edu/en/simulations/fraction-matcher",
        "bi-pie-chart-fill",
        "Empareja representaciones visuales, numéricas y en la recta numérica de una misma fracción.",
    ),
    (
        "Selección Natural",
        "BIOLOGIA",
        "https://phet.colorado.edu/en/simulations/natural-selection",
        "bi-bug-fill",
        "Observa cómo distintos rasgos ayudan o perjudican la supervivencia de una población ante el ambiente.",
    ),
    (
        "Expresión Génica: Lo Esencial",
        "BIOLOGIA",
        "https://phet.colorado.edu/en/simulations/gene-expression-essentials",
        "bi-diagram-3-fill",
        "Simula cómo una célula usa el ADN para fabricar proteínas — transcripción y traducción paso a paso.",
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
        ("gestion_academica", "0084_simulaciones_steam"),
    ]

    operations = [
        migrations.RunPython(sembrar, revertir),
    ]
