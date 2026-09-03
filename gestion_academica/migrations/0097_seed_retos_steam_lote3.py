# Tercer lote del catálogo público de Retos STEAM: 6 plantillas más
# "hazlo tú mismo" inspiradas en proyectos clásicos y ampliamente
# documentados de ciencia/ingeniería escolar (sismógrafo, generador eólico,
# circuito con grafito de lápiz, alarma de circuito cerrado, cohete de agua
# y aire, grúa con poleas) — mismo criterio que los lotes anteriores
# (0088/0092): materiales de bajo costo, sin robot ni kit propietario.
from django.db import migrations


RETOS = [
    {
        'titulo': "Sismógrafo Casero",
        'categoria': 'CIENCIA_SOSTENIBILIDAD',
        'icono': 'bi-activity',
        'descripcion_corta': "Un sismógrafo de péndulo que registra vibraciones del suelo en una tira de papel en movimiento.",
        'reto_texto': "Diseña y construye un instrumento capaz de registrar, en papel, las vibraciones que se producen al golpear o sacudir la mesa donde está apoyado.",
        'materiales': "Caja de cartón, un peso (tuerca grande o piedra), hilo o cordel, un marcador o lápiz, una tira larga de papel, cinta adhesiva, tijeras.",
        'criterio_evaluacion': "El trazo debe mostrar diferencias claras y repetibles entre una vibración suave y una fuerte al mover la tira de papel a velocidad constante.",
        'hitos_sugeridos': [
            {'titulo': "Investigar cómo funciona un sismógrafo real"},
            {'titulo': "Diseñar el sistema de péndulo y el marcador"},
            {'titulo': "Construir el sismógrafo"},
            {'titulo': "Probar con vibraciones suaves y fuertes"},
            {'titulo': "Comparar los trazos y explicar las diferencias"},
        ],
    },
    {
        'titulo': "Generador Eólico Casero",
        'categoria': 'CIENCIA_SOSTENIBILIDAD',
        'icono': 'bi-lightbulb',
        'descripcion_corta': "Una turbina de aspas de cartón acoplada a un motor de CD que enciende un LED con el viento de un ventilador.",
        'reto_texto': "Construye una turbina eólica capaz de encender un LED usando únicamente la energía del viento generado por un ventilador o al soplar.",
        'materiales': "Un micromotor de corriente directa (CD) reciclado de un juguete, un LED, cartulina o botellas plásticas para las aspas, un eje (palito de madera), pegante, cinta adhesiva.",
        'criterio_evaluacion': "El LED debe encenderse de forma visible al exponer la turbina al viento de un ventilador a velocidad media, a una distancia fija acordada con el docente.",
        'hitos_sugeridos': [
            {'titulo': "Investigar la conversión de energía eólica a eléctrica"},
            {'titulo': "Diseñar la forma y el número de aspas"},
            {'titulo': "Construir las aspas y acoplarlas al motor"},
            {'titulo': "Conectar el LED y probar frente al ventilador"},
            {'titulo': "Ajustar el diseño para maximizar el brillo del LED"},
        ],
    },
    {
        'titulo': "Circuito Conductor con Grafito de Lápiz",
        'categoria': 'ELECTRICIDAD_ELECTRONICA',
        'icono': 'bi-pencil-fill',
        'descripcion_corta': "Dibuja un circuito con una mina de lápiz sobre papel y enciende un LED aprovechando que el grafito conduce electricidad.",
        'reto_texto': "Dibuja, con grafito de lápiz sobre papel, un trazo continuo que funcione como conductor de un circuito capaz de encender un LED.",
        'materiales': "Lápices blandos (2B o más blandos), papel grueso o cartulina, una pila de 9V o 2 pilas AA con portapilas, un LED, cinta de cobre o clips metálicos para las conexiones.",
        'criterio_evaluacion': "El LED debe encenderse al cerrar el circuito usando únicamente el trazo de grafito como conductor, sin cables adicionales en el tramo dibujado.",
        'hitos_sugeridos': [
            {'titulo': "Investigar por qué el grafito conduce electricidad"},
            {'titulo': "Diseñar el trazado del circuito en papel"},
            {'titulo': "Dibujar el circuito repasando varias veces el trazo"},
            {'titulo': "Conectar la pila y el LED a los extremos del trazo"},
            {'titulo': "Probar y ajustar el grosor del trazo si el LED no enciende"},
        ],
    },
    {
        'titulo': "Detector de Circuito Cerrado (Alarma Simple)",
        'categoria': 'ELECTRICIDAD_ELECTRONICA',
        'icono': 'bi-bell-fill',
        'descripcion_corta': "Una alarma que suena o enciende un LED cuando se abre una puerta o caja, al romperse el contacto de un circuito.",
        'reto_texto': "Diseña un sistema de alerta que active un LED o un timbre cuando se abra una puerta, cajón o caja, aprovechando la interrupción de un circuito cerrado.",
        'materiales': "Pila de 9V con portapilas, LED o timbre/zumbador de 9V, cable delgado, cinta de cobre o papel aluminio, cartón o caja pequeña para simular la puerta.",
        'criterio_evaluacion': "La alarma (LED o timbre) debe permanecer apagada con la puerta cerrada y activarse de inmediato al abrirla, sin falsos positivos en 3 pruebas seguidas.",
        'hitos_sugeridos': [
            {'titulo': "Investigar circuitos abiertos y cerrados"},
            {'titulo': "Diseñar dónde y cómo se rompe el contacto al abrir"},
            {'titulo': "Construir el circuito y fijarlo a la puerta o caja"},
            {'titulo': "Probar abriendo y cerrando la puerta varias veces"},
            {'titulo': "Ajustar el contacto para eliminar falsos positivos"},
        ],
    },
    {
        'titulo': "Cohete de Agua y Aire a Presión",
        'categoria': 'MOVIMIENTO_TRANSPORTE',
        'icono': 'bi-rocket-takeoff-fill',
        'descripcion_corta': "Una botella con agua y aire a presión que despega como cohete al liberar el aire comprimido.",
        'reto_texto': "Construye un cohete a partir de una botella plástica que use agua y aire a presión como propulsante y alcance la mayor altura o distancia posible.",
        'materiales': "Botella plástica de gaseosa (1.5 o 2 L), cartulina para las aletas, corcho o tapón perforado, bomba de inflar con aguja o adaptador de válvula, agua.",
        'criterio_evaluacion': "El cohete debe despegar de forma estable (sin desviarse bruscamente) y alcanzar una altura o distancia medible, comparada entre distintos diseños del grupo.",
        'hitos_sugeridos': [
            {'titulo': "Investigar la tercera ley de Newton y la presión de gases"},
            {'titulo': "Diseñar la forma del cohete y las aletas"},
            {'titulo': "Construir el cuerpo, las aletas y el sistema de sellado"},
            {'titulo': "Realizar el lanzamiento de prueba con agua y aire"},
            {'titulo': "Medir la altura o distancia y ajustar la cantidad de agua"},
        ],
    },
    {
        'titulo': "Grúa con Sistema de Poleas",
        'categoria': 'MOVIMIENTO_TRANSPORTE',
        'icono': 'bi-arrow-up-circle-fill',
        'descripcion_corta': "Una grúa de palitos de madera con poleas que levanta un peso aplicando menos fuerza gracias a la ventaja mecánica.",
        'reto_texto': "Construye una grúa con un sistema de poleas que permita levantar un peso determinado aplicando la menor fuerza posible.",
        'materiales': "Palitos de madera o pinchos para brocheta, carretes de hilo o tapas como poleas, hilo o cordel resistente, cinta adhesiva o pegante caliente, un peso de prueba (bolsa con monedas o arandelas).",
        'criterio_evaluacion': "La grúa debe levantar el peso de prueba, definido por el docente, hasta una altura mínima de 20 cm sin que la estructura colapse.",
        'hitos_sugeridos': [
            {'titulo': "Investigar poleas simples, compuestas y ventaja mecánica"},
            {'titulo': "Diseñar la estructura y el número de poleas"},
            {'titulo': "Construir el brazo y la base de la grúa"},
            {'titulo': "Instalar el sistema de poleas y el hilo de izado"},
            {'titulo': "Probar el levantamiento del peso y ajustar el diseño"},
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
        ("gestion_academica", "0096_seed_tinkercad_reto_steam"),
    ]

    operations = [
        migrations.RunPython(sembrar, revertir),
    ]
