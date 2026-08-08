# gestion_academica/views/accesibilidad.py
"""Preferencias de accesibilidad del usuario (Ola 1 — base WCAG).

Guarda los ajustes de interfaz (tamaño de texto, alto contraste, fuente
legible, espaciado, reducir animaciones, lectura fácil) en el propio usuario,
para que le sigan entre dispositivos. No son datos sensibles: son ajustes de
presentación. El endpoint valida contra una lista blanca y nunca confía en
claves arbitrarias del cliente.
"""
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
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
