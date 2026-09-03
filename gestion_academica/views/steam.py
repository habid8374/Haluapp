"""Panel «Halu STEAM» — Fase 1: agrupa bajo una sola pantalla las piezas que
la plataforma ya tenía dispersas y que son relevantes para colegios con
modalidad técnica/STEAM (Énfasis, recursos interactivos, simulacros), y deja
la puerta abierta a los componentes futuros (proyectos, insignias, portafolio).

No introduce ningún modelo nuevo: solo lee lo que ya existe. El acceso a esta
pantalla se controla igual que cualquier otro módulo de la plataforma —
catálogo `ModuloPlataforma` (código 'steam') + `modulos_contratados` por
institución — así que por defecto ningún colegio la ve hasta que se le active
desde el panel del propietario.

Quién ve el panel: coordinadores Y docentes (ambos grupos tienen
`view_proyectosteam` — ver la migración de permisos de Fase 2), no solo
rectores/administradores. `acceso_modulo_academico` NO sirve aquí: ese
permiso solo lo tiene el grupo 'rectores' (migración 0057), así que un
coordinador real —la audiencia principal de este panel— quedaría bloqueado
si se usara.
"""
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render

from ..models import Enfasis, Estudiante, Insignia, InsigniaObtenida, ItemMalla, ProyectoSTEAM
from ._main import get_current_institution


@login_required
@permission_required('gestion_academica.view_proyectosteam', raise_exception=True)
def panel_steam(request):
    """Panel de coordinación para la modalidad STEAM/técnica del colegio."""
    institucion = get_current_institution(request.user)

    enfasis_qs = Enfasis.objects.filter(institucion=institucion) if institucion else Enfasis.objects.none()
    estudiantes_con_enfasis = (
        Estudiante.objects.filter(institucion=institucion, enfasis__isnull=False).count()
        if institucion else 0
    )
    total_proyectos = ProyectoSTEAM.objects.filter(institucion=institucion).count() if institucion else 0
    total_insignias_catalogo = Insignia.objects.filter(institucion=institucion, activo=True).count() if institucion else 0
    total_insignias_otorgadas = InsigniaObtenida.objects.filter(institucion=institucion).count() if institucion else 0

    items_malla_qs = ItemMalla.objects.filter(malla__institucion=institucion) if institucion else ItemMalla.objects.none()
    total_items_malla = items_malla_qs.count()
    items_con_stem = sum(1 for it in items_malla_qs if it.principios_stem)
    cobertura_stem_general = round(items_con_stem / total_items_malla * 100) if total_items_malla else 0

    context = {
        'titulo_pagina': "Halu STEAM",
        'institucion': institucion,
        'enfasis_activos': enfasis_qs.filter(activo=True),
        'total_enfasis': enfasis_qs.count(),
        'estudiantes_con_enfasis': estudiantes_con_enfasis,
        'total_proyectos': total_proyectos,
        'total_insignias_catalogo': total_insignias_catalogo,
        'total_insignias_otorgadas': total_insignias_otorgadas,
        'total_items_malla': total_items_malla,
        'cobertura_stem_general': cobertura_stem_general,
    }
    return render(request, 'gestion_academica/panel_steam.html', context)
