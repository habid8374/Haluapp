# finanzas/mixins.py

import logging
from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import render

logger = logging.getLogger(__name__)


def _finanzas_no_disponible(inst):
    """True si la institución NO debe ver el módulo de finanzas: es pública o
    tiene el módulo financiero desactivado explícitamente."""
    if not inst:
        return False
    return inst.tipo_institucion == 'publico' or not getattr(inst, 'usa_modulo_financiero', True)


def solo_institucion_privada(view_func):
    """Bloquea el acceso a vistas de finanzas para instituciones públicas o que
    tengan el módulo financiero desactivado (``usa_modulo_financiero=False``)."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        inst = getattr(request.user, 'institucion_asociada', None)
        if _finanzas_no_disponible(inst):
            return render(request, 'finanzas/acceso_no_disponible.html', status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped


class SoloInstitucionPrivadaMixin:
    """Versión mixin para Clases Basadas en Vistas."""
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            inst = getattr(request.user, 'institucion_asociada', None)
            if _finanzas_no_disponible(inst):
                return render(request, 'finanzas/acceso_no_disponible.html', status=403)
        return super().dispatch(request, *args, **kwargs)

class InstitucionOwnedMixin:
    """
    Mixin para Clases Basadas en Vistas que filtra el queryset para que un usuario
    solo vea los objetos pertenecientes a su institución.
    Los superusuarios pueden ver todo.
    """
    def get_queryset(self):
        # Obtiene el queryset original definido en la vista
        queryset = super().get_queryset()
        
        
        if not self.request.user.is_superuser:
            institucion_usuario = getattr(self.request.user, 'institucion_asociada', None)
            if institucion_usuario:
                return queryset.filter(institucion=institucion_usuario)
            else:
                logger.warning(f"Usuario sin institución: {self.request.user.username}")
                return queryset.none()
        return queryset