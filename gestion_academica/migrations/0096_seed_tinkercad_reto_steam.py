# Tarjeta informativa de Tinkercad (Autodesk) en el catálogo de Retos STEAM:
# herramienta gratuita de diseño 3D + simulador de circuitos/Arduino +
# programación por bloques. No es un reto "hazlo tú mismo" ni una
# competencia — es una herramienta externa que un docente puede usar para
# construir sus propios retos de electrónica/diseño (categoría
# HERRAMIENTA_EXTERNA, agregada en 0093). Mismo patrón que las tarjetas de
# FIRST LEGO League / VEX en 0088_seed_retos_steam.py: solo `enlace_externo`,
# sin reto_texto/materiales/hitos (no es una plantilla "usable").
#
# Se enlaza únicamente a la URL principal, ya verificada
# (https://www.tinkercad.com/) — el sub-path de circuitos (/circuits) no se
# pudo confirmar con una fuente oficial suficientemente sólida.
from django.db import migrations


RETOS = [
    {
        'titulo': "Tinkercad (Autodesk)",
        'categoria': 'HERRAMIENTA_EXTERNA',
        'icono': 'bi-tools',
        'descripcion_corta': "Herramienta gratuita de Autodesk para diseño 3D, simulación de circuitos/Arduino y programación por bloques. Ideal para prototipar retos de electrónica.",
        'enlace_externo': "https://www.tinkercad.com/",
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
        ("gestion_academica", "0095_simulacionsteam_geogebra_hostname"),
    ]

    operations = [
        migrations.RunPython(sembrar, revertir),
    ]
