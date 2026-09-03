# Corrige íconos de Bootstrap Icons que resultaron ser clases inexistentes
# (se veían en blanco) en el catálogo de Simulaciones y Retos STEAM.
# Detectado en producción: "Simulaciones STEAM" usaba bi-atom, que no existe
# en Bootstrap Icons — se reemplaza por íconos verificados contra los que ya
# se usan (y se ven bien) en el resto de la plataforma.
from django.db import migrations


SIMULACIONES_FIX = {
    "Estados de la Materia: Básico": "bi-flask-fill",
    "Construye un Átomo": "bi-bullseye",
    "Escala de pH": "bi-circle-half",
    "Densidad": "bi-boxes",
}

RETOS_FIX = {
    "Puente Hidráulico con Jeringas": "bi-gear-fill",
    "Brazo Hidráulico con Jeringas": "bi-wrench-adjustable-circle-fill",
    "Auto Propulsado por Globo": "bi-speedometer2",
    "Aterrizaje Seguro del Huevo": "bi-shield-fill",
    "VEX IQ": "bi-cpu",
}


def corregir(apps, schema_editor):
    SimulacionSTEAM = apps.get_model('gestion_academica', 'SimulacionSTEAM')
    RetoSTEAM = apps.get_model('gestion_academica', 'RetoSTEAM')
    for titulo, icono in SIMULACIONES_FIX.items():
        SimulacionSTEAM.objects.filter(institucion__isnull=True, titulo=titulo).update(icono=icono)
    for titulo, icono in RETOS_FIX.items():
        RetoSTEAM.objects.filter(institucion__isnull=True, titulo=titulo).update(icono=icono)


def revertir(apps, schema_editor):
    # No hay un valor "anterior" que valga la pena restaurar (era el ícono roto).
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("gestion_academica", "0089_permisos_retos_steam"),
    ]

    operations = [
        migrations.RunPython(corregir, revertir),
    ]
