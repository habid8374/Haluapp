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
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from ..models import RetoSTEAM


def _retos_visibles_para(user):
    institucion = getattr(user, 'institucion_asociada', None)
    if user.is_superuser:
        return RetoSTEAM.objects.filter(activo=True)
    return RetoSTEAM.objects.filter(Q(es_publica=True) | Q(institucion=institucion), activo=True)


@login_required
@permission_required('gestion_academica.view_retosteam', raise_exception=True)
def catalogo_retos_steam(request):
    qs = _retos_visibles_para(request.user)

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


@login_required
@permission_required('gestion_academica.view_retosteam', raise_exception=True)
def abrir_reto_steam(request, pk):
    """Visor propio de Halu para la tarjeta informativa de una competencia
    externa (FIRST LEGO League, VEX…). A diferencia de las simulaciones
    PhET, estos sitios NO están pensados para incrustarse — la mayoría de
    páginas institucionales bloquean el "framing" por seguridad (evita
    clickjacking), así que lo más probable es que el iframe salga en
    blanco. Por eso el botón "Abrir en una pestaña nueva" siempre está
    visible desde el primer momento, no solo como respaldo ante un error."""
    reto = get_object_or_404(_retos_visibles_para(request.user), pk=pk)
    if not reto.enlace_externo:
        messages.error(request, _("Este reto no tiene un enlace externo."))
        return redirect('gestion_academica:catalogo_retos_steam')
    context = {
        'reto': reto,
        'titulo_pagina': reto.titulo,
    }
    return render(request, 'gestion_academica/visor_reto_steam.html', context)
