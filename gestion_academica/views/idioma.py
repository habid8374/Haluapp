# gestion_academica/views/idioma.py
"""Selector de idioma de la interfaz (ver docs/PLAN_MULTIIDIOMA.md)."""
from django.shortcuts import redirect
from django.views.i18n import set_language as _django_set_language


def _idiomas_permitidos(user):
    """Códigos de idioma que este usuario puede elegir: español siempre, más los
    idiomas de interfaz que SU institución haya contratado. Multi-tenant: un
    usuario no puede activar un idioma que su colegio no contrató."""
    permitidos = {'es'}
    if getattr(user, 'is_authenticated', False):
        institucion = getattr(user, 'institucion_asociada', None)
        if institucion is not None:
            try:
                permitidos.update(institucion.codigos_idioma_interfaz())
            except Exception:
                pass
    return permitidos


def cambiar_idioma(request):
    if request.method == 'POST':
        idioma = request.POST.get('language', '')
        if idioma in _idiomas_permitidos(request.user):
            if request.user.is_authenticated:
                request.user.idioma_preferido = idioma
                request.user.save(update_fields=['idioma_preferido'])
            return _django_set_language(request)
        # Idioma no contratado por este colegio: no se cambia nada.
        next_url = request.POST.get('next') or request.GET.get('next') or '/'
        return redirect(next_url)
    return _django_set_language(request)
