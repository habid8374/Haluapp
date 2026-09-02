"""Panel «Halu STEAM» — Fase 1: agrupa bajo una sola pantalla las piezas que
la plataforma ya tenía dispersas y que son relevantes para colegios con
modalidad técnica/STEAM (Énfasis, recursos interactivos, simulacros), y deja
la puerta abierta a los componentes futuros (proyectos, insignias, portafolio).

No introduce ningún modelo nuevo: solo lee lo que ya existe. El acceso a esta
pantalla se controla igual que cualquier otro módulo de la plataforma —
catálogo `ModuloPlataforma` (código 'steam') + `modulos_contratados` por
institución — así que por defecto ningún colegio la ve hasta que se le active
desde el panel del propietario.
"""
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render

from ..models import Enfasis, Estudiante
from ._main import get_current_institution


@login_required
@permission_required('gestion_academica.acceso_modulo_academico', raise_exception=True)
def panel_steam(request):
    """Panel de coordinación para la modalidad STEAM/técnica del colegio."""
    institucion = get_current_institution(request.user)

    enfasis_qs = Enfasis.objects.filter(institucion=institucion) if institucion else Enfasis.objects.none()
    estudiantes_con_enfasis = (
        Estudiante.objects.filter(institucion=institucion, enfasis__isnull=False).count()
        if institucion else 0
    )

    context = {
        'titulo_pagina': "Halu STEAM",
        'institucion': institucion,
        'enfasis_activos': enfasis_qs.filter(activo=True),
        'total_enfasis': enfasis_qs.count(),
        'estudiantes_con_enfasis': estudiantes_con_enfasis,
    }
    return render(request, 'gestion_academica/panel_steam.html', context)
