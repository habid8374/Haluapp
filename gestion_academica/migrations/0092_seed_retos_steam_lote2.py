# Segundo lote del catálogo público de Retos STEAM: 6 plantillas más
# "hazlo tú mismo" con materiales de bajo costo, clásicos documentados de
# educación STEM (horno solar, catapulta, filtro de agua, domo geodésico,
# barco de tensión superficial, autómata de levas) — mismo criterio que el
# primer lote en 0088_seed_retos_steam.py.
from django.db import migrations


RETOS = [
    {
        'titulo': "Horno Solar con Caja de Zapatos",
        'categoria': 'CIENCIA_SOSTENIBILIDAD',
        'icono': 'bi-lightbulb-fill',
        'descripcion_corta': "Concentra la radiación solar en una caja para derretir queso o malvaviscos sin electricidad.",
        'reto_texto': "Diseña y construye un dispositivo térmico capaz de concentrar radiación solar para derretir queso o malvaviscos sin electricidad ni fuego.",
        'materiales': "Caja de cartón, papel aluminio, papel film transparente (vinipel), cartulina negra, regla, cinta adhesiva.",
        'criterio_evaluacion': "El dispositivo debe superar la temperatura ambiente exterior en al menos 15 °C en 20 minutos, o fundir el alimento de prueba.",
        'hitos_sugeridos': [
            {'titulo': "Investigar el efecto invernadero y la transferencia de calor"},
            {'titulo': "Diseñar la forma y el ángulo de los reflectores"},
            {'titulo': "Construir el horno solar"},
            {'titulo': "Medir la temperatura cada 5 minutos durante la prueba"},
            {'titulo': "Analizar los resultados y proponer mejoras"},
        ],
    },
    {
        'titulo': "Catapulta de Precisión con Elásticos",
        'categoria': 'MOVIMIENTO_TRANSPORTE',
        'icono': 'bi-bullseye',
        'descripcion_corta': "Una catapulta de palitos de helado que lanza un proyectil ligero a un blanco fijo.",
        'reto_texto': "Construye una máquina simple de torsión o tensión que lance un proyectil ligero a un blanco fijo ubicado a distancias variables.",
        'materiales': "10 palitos de helado, 6 bandas elásticas (ligas), 1 tapa plástica de botella, cinta adhesiva, un proyectil ligero (pompón o bolita de papel).",
        'criterio_evaluacion': "Lanzar el proyectil e impactar una diana situada a 1.5 metros de distancia con al menos 3 aciertos en 5 intentos.",
        'hitos_sugeridos': [
            {'titulo': "Investigar energía potencial elástica y tiro parabólico"},
            {'titulo': "Diseñar la estructura de palanca"},
            {'titulo': "Construir la catapulta"},
            {'titulo': "Calibrar la puntería con lanzamientos de prueba"},
            {'titulo': "Competir por precisión contra el blanco"},
        ],
    },
    {
        'titulo': "Filtro Casero de Purificación de Agua",
        'categoria': 'CIENCIA_SOSTENIBILIDAD',
        'icono': 'bi-funnel-fill',
        'descripcion_corta': "Una columna de filtración por capas que clarifica agua turbia con sedimentos.",
        'reto_texto': "Diseña una columna de filtración estratificada para clarificar agua turbia con sedimentos orgánicos.",
        'materiales': "Botella plástica transparente de 1.5 L cortada, algodón, arena fina, arena gruesa, grava pequeña, carbón activo triturado, agua turbia de muestra.",
        'criterio_evaluacion': "El agua filtrada debe presentar una reducción visual del 80% en turbidez respecto a la muestra original y retener todas las partículas visibles.",
        'hitos_sugeridos': [
            {'titulo': "Investigar porosidad, sedimentación y adsorción"},
            {'titulo': "Diseñar el orden de las capas del filtro"},
            {'titulo': "Armar el filtro por capas"},
            {'titulo': "Filtrar la muestra de agua turbia"},
            {'titulo': "Comparar el agua antes y después y documentar resultados"},
        ],
    },
    {
        'titulo': "Domo Geodésico de Periódico",
        'categoria': 'ESTRUCTURAS',
        'icono': 'bi-globe',
        'descripcion_corta': "Una cúpula autosoportada de tubos de periódico triangulados que resiste peso en su cúspide.",
        'reto_texto': "Crea una cúpula semiesférica autosoportada basada en triángulos que soporte peso vertical en su cúspide.",
        'materiales': "Hojas de periódico enrolladas en tubos rígidos, cinta adhesiva gruesa o grapas, tijeras, regla.",
        'criterio_evaluacion': "El domo debe tener al menos 50 cm de diámetro, mantenerse en pie sin apoyos auxiliares y resistir un libro de texto sobre su cúspide sin colapsar.",
        'hitos_sugeridos': [
            {'titulo': "Investigar la triangulación y la distribución de cargas"},
            {'titulo': "Diseñar la cantidad y el largo de los tubos"},
            {'titulo': "Enrollar los tubos de periódico"},
            {'titulo': "Ensamblar la estructura triangulada"},
            {'titulo': "Probar la resistencia con peso en la cúspide"},
        ],
    },
    {
        'titulo': "Barco Propulsado por Tensión Superficial",
        'categoria': 'MOVIMIENTO_TRANSPORTE',
        'icono': 'bi-flask-fill',
        'descripcion_corta': "Un barco que avanza en el agua usando solo jabón para romper la tensión superficial.",
        'reto_texto': "Construye una embarcación a escala que se mueva en una bandeja de agua únicamente alterando la tensión superficial del líquido.",
        'materiales': "Cartón encerado (cajas de leche o tetrapak) o plástico fino, tijeras, un recipiente hondo con agua, jabón líquido lavaplatos, copitos de algodón.",
        'criterio_evaluacion': "El barco debe desplazarse de un extremo al otro del recipiente de forma autónoma al aplicar una gota de jabón en la popa.",
        'hitos_sugeridos': [
            {'titulo': "Investigar la tensión superficial del agua"},
            {'titulo': "Diseñar la forma del casco y el canal de propulsión"},
            {'titulo': "Construir el barco"},
            {'titulo': "Probar el desplazamiento con jabón"},
            {'titulo': "Ajustar el diseño para mejorar la distancia recorrida"},
        ],
    },
    {
        'titulo': "Autómata de Movimiento con Levas de Cartón",
        'categoria': 'MOVIMIENTO_TRANSPORTE',
        'icono': 'bi-arrow-repeat',
        'descripcion_corta': "Un juguete mecánico de manivela que transforma el giro en el movimiento vertical de una figura.",
        'reto_texto': "Diseña un juguete mecánico manual que transforme el movimiento circular de una manivela en un movimiento lineal vertical de un personaje o figura.",
        'materiales': "Caja pequeña de cartón, pinchos de madera para brocheta, tapas plásticas o discos de cartón (levas), pajillas/pitillos, papel para decorar.",
        'criterio_evaluacion': "El mecanismo debe completar 5 rotaciones continuas fluidas de manivela sin trabarse, elevando y descendiendo la figura decorada de forma sincronizada.",
        'hitos_sugeridos': [
            {'titulo': "Investigar mecanismos de levas y seguidores"},
            {'titulo': "Diseñar la forma de la leva y el eje"},
            {'titulo': "Construir la caja y el sistema de manivela"},
            {'titulo': "Instalar la figura decorada"},
            {'titulo': "Probar y ajustar la fluidez del movimiento"},
        ],
    },
]


def sembrar(apps, schema_editor):
    RetoSTEAM = apps.get_model('gestion_academica', 'RetoSTEAM')
    for datos in RETOS:
        RetoSTEAM.objects.get_or_create(
            institucion=None,
            titulo=datos['titulo'],
            defaults={
                'es_publica': True,
                'activo': True,
                **{k: v for k, v in datos.items() if k != 'titulo'},
            },
        )


def revertir(apps, schema_editor):
    RetoSTEAM = apps.get_model('gestion_academica', 'RetoSTEAM')
    titulos = [r['titulo'] for r in RETOS]
    RetoSTEAM.objects.filter(institucion__isnull=True, titulo__in=titulos).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("gestion_academica", "0091_reto_steam_categoria_ciencia_sostenibilidad"),
    ]

    operations = [
        migrations.RunPython(sembrar, revertir),
    ]
