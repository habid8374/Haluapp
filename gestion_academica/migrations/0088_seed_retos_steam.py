# Siembra el catálogo público (institucion=NULL, es_publica=True) de retos
# de ingeniería/robótica STEAM: 6 plantillas "hazlo tú mismo" con materiales
# de bajo costo (clásicos documentados de educación STEM, sin marca/kit
# propietario) + 2 tarjetas informativas de competencias externas reales
# (FIRST LEGO League Colombia, VEX IQ) — sus enlaces se verificaron contra
# las páginas oficiales antes de sembrarlos.
from django.db import migrations


RETOS = [
    {
        'titulo': "Puente de Espagueti",
        'categoria': 'ESTRUCTURAS',
        'icono': 'bi-diagram-3',
        'descripcion_corta': "Diseña y construye un puente con espagueti que resista la mayor carga posible.",
        'reto_texto': "Diseña y construye un puente que cruce una separación de al menos 30 cm usando únicamente espagueti crudo y pegante, y que resista la mayor carga posible sin colapsar.",
        'materiales': "Espagueti crudo (varios paquetes), pegante caliente o blanco, regla, tijeras, pesas o bolsas con arena/monedas para la prueba de carga, balanza.",
        'criterio_evaluacion': "Se mide la carga máxima que soporta el puente antes de colapsar, dividida entre el peso del propio puente (relación resistencia/peso). Gana quien logre la mayor relación.",
        'hitos_sugeridos': [
            {'titulo': "Investigar tipos de estructuras de puentes (armaduras)"},
            {'titulo': "Diseñar el boceto y calcular el peso estimado"},
            {'titulo': "Construir el puente"},
            {'titulo': "Probar con cargas crecientes"},
            {'titulo': "Presentar resultados y lecciones aprendidas"},
        ],
    },
    {
        'titulo': "Torre de Papel Más Alta",
        'categoria': 'ESTRUCTURAS',
        'icono': 'bi-building',
        'descripcion_corta': "Construye la torre autosoportada más alta posible usando solo papel y cinta.",
        'reto_texto': "Construye la torre autosoportada más alta posible usando solo hojas de papel y cinta adhesiva, que se mantenga en pie sin apoyos externos durante al menos 1 minuto.",
        'materiales': "Hojas de papel tamaño carta (20-30), cinta adhesiva (un rollo), regla o metro.",
        'criterio_evaluacion': "Se mide la altura de la torre desde la base hasta la punta más alta; debe sostenerse sola durante al menos 1 minuto.",
        'hitos_sugeridos': [
            {'titulo': "Explorar formas que dan estabilidad (tubos, triángulos, base ancha)"},
            {'titulo': "Diseñar la estructura por niveles"},
            {'titulo': "Construir la base y verificar estabilidad"},
            {'titulo': "Construir hacia arriba y ajustar el equilibrio"},
            {'titulo': "Medir y documentar la altura final"},
        ],
    },
    {
        'titulo': "Puente Hidráulico con Jeringas",
        'categoria': 'HIDRAULICA_NEUMATICA',
        'icono': 'bi-gear-fill',
        'descripcion_corta': "Un puente levadizo que se abre y cierra con el principio de Pascal, sin motores.",
        'reto_texto': "Construye un puente levadizo que se abra y cierre usando el principio de Pascal: jeringas llenas de agua conectadas por mangueras, sin ningún motor eléctrico.",
        'materiales': "Jeringas plásticas (4-6), manguera delgada flexible, palos de madera o pitillos, cartón o icopor para la base, agua, silicona.",
        'criterio_evaluacion': "El puente debe abrirse y cerrarse completamente accionando solo las jeringas, sin fugas de agua.",
        'hitos_sugeridos': [
            {'titulo': "Investigar el principio de Pascal"},
            {'titulo': "Diseñar el mecanismo de bisagra"},
            {'titulo': "Armar el circuito hidráulico (jeringas y mangueras)"},
            {'titulo': "Construir la estructura del puente"},
            {'titulo': "Probar y ajustar fugas o atascos"},
        ],
    },
    {
        'titulo': "Brazo Hidráulico con Jeringas",
        'categoria': 'HIDRAULICA_NEUMATICA',
        'icono': 'bi-wrench-adjustable-circle-fill',
        'descripcion_corta': "Un brazo articulado que se mueve con jeringas como pistones hidráulicos.",
        'reto_texto': "Construye un brazo mecánico articulado que se mueva usando jeringas como pistones hidráulicos, capaz de levantar un objeto pequeño.",
        'materiales': "Jeringas plásticas (6-8), manguera delgada, palos de madera o icopor, agua, silicona o cinta.",
        'criterio_evaluacion': "El brazo debe levantar y sostener un objeto de al menos 20 gramos usando solo la presión del agua en las jeringas.",
        'hitos_sugeridos': [
            {'titulo': "Investigar cómo funciona un pistón hidráulico"},
            {'titulo': "Diseñar las articulaciones del brazo"},
            {'titulo': "Construir la estructura del brazo"},
            {'titulo': "Instalar el sistema de jeringas y mangueras"},
            {'titulo': "Probar levantando distintos objetos"},
        ],
    },
    {
        'titulo': "Auto Propulsado por Globo",
        'categoria': 'MOVIMIENTO_TRANSPORTE',
        'icono': 'bi-speedometer2',
        'descripcion_corta': "Un vehículo que se mueve solo con el aire de un globo — acción y reacción.",
        'reto_texto': "Diseña y construye un vehículo que se mueva únicamente con el aire liberado de un globo inflado, y que recorra la mayor distancia posible en línea recta.",
        'materiales': "Globos, botella o cartón para el chasis, pitillos, tapas de gaseosa o CDs para las ruedas, palillos de madera para los ejes, cinta.",
        'criterio_evaluacion': "Se mide la distancia recorrida en línea recta con un solo globo, desde la salida hasta donde se detiene.",
        'hitos_sugeridos': [
            {'titulo': "Investigar el principio de acción y reacción"},
            {'titulo': "Diseñar el chasis y las ruedas"},
            {'titulo': "Construir el vehículo"},
            {'titulo': "Ajustar el sistema de propulsión (globo y boquilla)"},
            {'titulo': "Medir y comparar distancias en varias pruebas"},
        ],
    },
    {
        'titulo': "Aterrizaje Seguro del Huevo",
        'categoria': 'MOVIMIENTO_TRANSPORTE',
        'icono': 'bi-shield-fill',
        'descripcion_corta': "Diseña una estructura que proteja un huevo crudo en una caída desde 3 metros.",
        'reto_texto': "Diseña una estructura protectora que permita que un huevo crudo caiga desde al menos 3 metros de altura sin romperse.",
        'materiales': "Huevos crudos, pitillos, algodón, cartón, globos, papel periódico, cinta, bolsas plásticas.",
        'criterio_evaluacion': "El huevo debe sobrevivir intacto la caída desde la altura acordada; entre los que sobreviven, gana la estructura más liviana.",
        'hitos_sugeridos': [
            {'titulo': "Investigar cómo absorber impactos"},
            {'titulo': "Diseñar el sistema de amortiguación"},
            {'titulo': "Construir la estructura protectora"},
            {'titulo': "Realizar la prueba de caída"},
            {'titulo': "Analizar qué falló o funcionó y mejorar el diseño"},
        ],
    },
    {
        'titulo': "FIRST LEGO League Colombia",
        'categoria': 'COMPETENCIA_EXTERNA',
        'icono': 'bi-robot',
        'descripcion_corta': "Competencia internacional de robótica LEGO para colegios — sede oficial en Colombia (UNIMINUTO). Requiere inscripción y kits LEGO propios.",
        'enlace_externo': "https://unno.uniminuto.edu/inscripciones-first-lego-league-2025-2026/",
    },
    {
        'titulo': "VEX IQ",
        'categoria': 'COMPETENCIA_EXTERNA',
        'icono': 'bi-cpu',
        'descripcion_corta': "Actividades y retos de robótica VEX IQ, con currículo gratuito para el aula. Requiere kits VEX propios.",
        'enlace_externo': "https://education.vex.com/stemlabs/iq",
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
        ("gestion_academica", "0087_reto_steam"),
    ]

    operations = [
        migrations.RunPython(sembrar, revertir),
    ]
