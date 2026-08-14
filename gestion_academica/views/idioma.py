# gestion_academica/views/idioma.py
"""Selector de idioma de la interfaz (ver docs/PLAN_MULTIIDIOMA.md)."""
from django.views.i18n import set_language as _django_set_language

IDIOMAS_VALIDOS = {'es', 'en', 'fr'}


def cambiar_idioma(request):
    if request.method == 'POST':
        idioma = request.POST.get('language', '')
        if idioma in IDIOMAS_VALIDOS and request.user.is_authenticated:
            request.user.idioma_preferido = idioma
            request.user.save(update_fields=['idioma_preferido'])
    return _django_set_language(request)
