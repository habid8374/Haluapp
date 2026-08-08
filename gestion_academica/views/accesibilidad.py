# gestion_academica/views/accesibilidad.py
"""Preferencias de accesibilidad del usuario (Ola 1 — base WCAG).

Guarda los ajustes de interfaz (tamaño de texto, alto contraste, fuente
legible, espaciado, reducir animaciones, lectura fácil) en el propio usuario,
para que le sigan entre dispositivos. No son datos sensibles: son ajustes de
presentación. El endpoint valida contra una lista blanca y nunca confía en
claves arbitrarias del cliente.
"""
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

# Ajustes permitidos y su tipo esperado.
_OPCIONES_BOOL = {'contrast', 'dyslexia', 'spacing', 'reduce_motion', 'easy_read'}
_OPCION_FONT = {'normal', 'lg', 'xl'}


def _limpiar_preferencias(data):
    """Devuelve solo las claves válidas y normalizadas (defensivo)."""
    limpio = {}
    if not isinstance(data, dict):
        return limpio
    font = data.get('font')
    if font in _OPCION_FONT:
        limpio['font'] = font
    for clave in _OPCIONES_BOOL:
        if clave in data:
            limpio[clave] = bool(data.get(clave))
    return limpio


@login_required
@require_POST
def guardar_preferencias_accesibilidad(request):
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)

    prefs = _limpiar_preferencias(payload)
    request.user.preferencias_accesibilidad = prefs
    request.user.save(update_fields=['preferencias_accesibilidad'])
    return JsonResponse({'ok': True, 'preferencias': prefs})


# ─────────────────────────────────────────────────────────────────────────────
#  Perfil de Accesibilidad del estudiante (Ola 2) — ligado al PIAR
# ─────────────────────────────────────────────────────────────────────────────

def _puede_gestionar_perfil(user):
    """Datos de apoyo ligados a la condición del estudiante → acceso restringido
    a coordinación, dirección y psicoorientación (no a cualquier docente)."""
    rol = getattr(user, 'rol', '') or ''
    return user.is_superuser or rol in (
        'coordinador', 'administrador', 'admin_institucion', 'rector', 'psicologo'
    )


@login_required
def editar_perfil_accesibilidad(request, estudiante_pk):
    from gestion_academica.models import Estudiante, PerfilAccesibilidad
    from gestion_academica.forms import PerfilAccesibilidadForm

    if not _puede_gestionar_perfil(request.user):
        raise PermissionDenied

    institucion = getattr(request.user, 'institucion_asociada', None)
    filtro = {'pk': estudiante_pk}
    if not request.user.is_superuser:
        filtro['institucion'] = institucion
    estudiante = get_object_or_404(Estudiante, **filtro)

    perfil, creado = PerfilAccesibilidad.objects.get_or_create(
        estudiante=estudiante,
        defaults={'institucion': estudiante.institucion},
    )

    # Si es nuevo, sugerir apoyos a partir de la condición del PIAR vigente.
    sugerencia_condicion = None
    if creado:
        piar = estudiante.piars.order_by('-año_lectivo').first()
        if piar is not None:
            sug = PerfilAccesibilidad.sugerencias_por_condicion(piar.condicion)
            for campo, valor in sug.items():
                setattr(perfil, campo, valor)
            perfil.save()
            sugerencia_condicion = piar.get_condicion_display()

    if request.method == 'POST':
        form = PerfilAccesibilidadForm(request.POST, instance=perfil)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.institucion = estudiante.institucion  # nunca del POST
            obj.save()
            messages.success(request, _("Perfil de accesibilidad actualizado."))
            return redirect('gestion_academica:editar_perfil_accesibilidad', estudiante_pk=estudiante.pk)
    else:
        form = PerfilAccesibilidadForm(instance=perfil)

    return render(request, 'gestion_academica/perfil_accesibilidad_form.html', {
        'titulo_pagina': _("Accesibilidad de %(est)s") % {'est': estudiante.usuario.get_full_name() or estudiante},
        'form': form,
        'estudiante': estudiante,
        'perfil': perfil,
        'sugerencia_condicion': sugerencia_condicion,
    })
