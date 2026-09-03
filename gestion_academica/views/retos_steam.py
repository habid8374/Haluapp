"""Halu STEAM — Catálogo de Retos de ingeniería/robótica (ABP).

Dos tipos de tarjeta en el mismo catálogo (ver `RetoSTEAM.es_plantilla_usable`):
- Plantillas «hazlo tú mismo» (materiales de bajo costo, sin robot): el
  docente pulsa "Usar esta plantilla" y llega a `crear_proyecto_steam` con
  el título, el reto y los hitos ya precargados (mismo mecanismo que el
  planeador IA — ver `_crear_hitos_sugeridos_ia` en proyectos_steam.py).
- Tarjetas informativas de competencias externas (FIRST LEGO League, VEX):
  solo enlazan a la página oficial — requieren kits/inscripción que Halu no
  gestiona.
"""
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q
from django.shortcuts import render

from ..models import RetoSTEAM


@login_required
@permission_required('gestion_academica.view_retosteam', raise_exception=True)
def catalogo_retos_steam(request):
    institucion = getattr(request.user, 'institucion_asociada', None)
    if request.user.is_superuser:
        qs = RetoSTEAM.objects.filter(activo=True)
    else:
        qs = RetoSTEAM.objects.filter(Q(es_publica=True) | Q(institucion=institucion), activo=True)

    categoria = request.GET.get('categoria', '')
    if categoria:
        qs = qs.filter(categoria=categoria)

    context = {
        'retos': qs.order_by('categoria', 'titulo'),
        'categorias': RetoSTEAM.Categoria.choices,
        'categoria_seleccionada': categoria,
        'titulo_pagina': "Catálogo de Retos STEAM",
    }
    return render(request, 'gestion_academica/catalogo_retos_steam.html', context)
