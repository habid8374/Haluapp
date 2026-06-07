"""Decoradores transversales del módulo académico.

Este módulo contiene utilidades para proteger vistas que requieran que el
estudiante esté **al día** con sus pagos (Fase C — bloqueo real por mora).

Uso típico (vista de Django)::

    from gestion_academica.decorators import requiere_pagos_al_dia

    @login_required
    @requiere_pagos_al_dia
    def realizar_entrega_deber(request, ...):
        ...

Uso típico (DRF)::

    from gestion_academica.decorators import EstaAlDiaPermission

    class MiViewSet(viewsets.ModelViewSet):
        permission_classes = [IsAuthenticated, EstaAlDiaPermission]

Uso en vistas basadas en clase (misma política que el decorador)::

    from gestion_academica.decorators import redirect_si_moroso_estudiante

    class MiVista(View):
        def get(self, request, *args, **kwargs):
            r = redirect_si_moroso_estudiante(request)
            if r is not None:
                return r
            ...

Política de bloqueo:
    - Solo aplica al rol ``estudiante``.
    - Cualquier otro rol pasa transparente (incluido ``superuser``).
    - Respeta ``InstitucionEducativa.bloquear_portal_por_mora`` y
      ``dias_gracia_mora`` (ver ``Estudiante.esta_al_dia()``).
    - Si bloquea, redirige al dashboard del estudiante con un mensaje claro
      (en vistas Django) o devuelve 402 (en DRF) con detalle estructurado.
"""

from __future__ import annotations

import logging
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _get_estudiante_de_request(request):
    """Devuelve el ``Estudiante`` asociado al usuario o ``None`` si no aplica."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return None
    if getattr(user, "rol", None) != "estudiante":
        return None
    return getattr(user, "estudiante", None)


def estudiante_esta_al_dia(request) -> tuple[bool, "Estudiante | None"]:
    """Helper público: devuelve ``(esta_al_dia, estudiante_o_None)``.

    - Si el usuario no es estudiante, devuelve ``(True, None)``.
    - Si es estudiante pero no tiene perfil cargado, también ``(True, None)``
      (se considera fallo de configuración no atribuible al estudiante).
    """
    estudiante = _get_estudiante_de_request(request)
    if estudiante is None:
        return True, None
    try:
        return estudiante.esta_al_dia(), estudiante
    except Exception:
        logger.exception(
            "Error evaluando esta_al_dia() para estudiante=%s — se permite acceso por seguridad operativa.",
            getattr(estudiante, "pk", "?"),
        )
        return True, estudiante


# ---------------------------------------------------------------------------
# Decorator para vistas Django clásicas
# ---------------------------------------------------------------------------

def requiere_pagos_al_dia(view_func):
    """Bloquea la vista si el estudiante tiene cuentas vencidas.

    Solo afecta a usuarios con ``rol == 'estudiante'``. Otros roles pasan
    transparente. Si el estudiante está moroso, redirige a
    ``gestion_academica:dashboard_estudiante`` con un ``messages.error``.
    """

    @wraps(view_func)
    def _wrapper(request, *args, **kwargs):
        r = redirect_si_moroso_estudiante(request)
        if r is not None:
            return r
        return view_func(request, *args, **kwargs)

    return _wrapper


def redirect_si_moroso_estudiante(request):
    """
    Para vistas basadas en clase: si el estudiante está en mora, aplica el mismo
    mensaje y redirección que ``requiere_pagos_al_dia``. Si no aplica, devuelve ``None``.
    """
    al_dia, estudiante = estudiante_esta_al_dia(request)
    if al_dia or estudiante is None:
        return None
    if getattr(request.user, "rol", None) != "estudiante":
        return None
    try:
        dias = estudiante.dias_de_atraso_max
    except Exception:
        dias = 0
    msg = (
        "Tu portal académico está bloqueado por mensualidades vencidas "
        f"(atraso de hasta {dias} día{'s' if dias != 1 else ''}). "
        "Realiza el pago para recuperar el acceso."
    )
    messages.error(request, msg)
    try:
        return redirect("gestion_academica:dashboard_estudiante")
    except Exception:
        logger.warning(
            "No fue posible redirigir a dashboard_estudiante; se redirige a '/'.",
        )
        return redirect("/")


# ---------------------------------------------------------------------------
# Permission class para DRF (lazy import para no exigir DRF si no está)
# ---------------------------------------------------------------------------

try:
    from rest_framework.permissions import BasePermission
except Exception:  # pragma: no cover - DRF debería estar instalado
    BasePermission = object  # type: ignore[assignment, misc]


class EstaAlDiaPermission(BasePermission):  # type: ignore[misc]
    """Permission class de DRF: niega 402 al estudiante moroso.

    Devuelve mensaje en ``request.detail`` (a través de ``message``) listo para
    ser interpretado por el frontend.
    """

    message = (
        "El portal está bloqueado por mensualidades vencidas. Realiza el pago "
        "para recuperar el acceso a esta función."
    )

    def has_permission(self, request, view):
        al_dia, _ = estudiante_esta_al_dia(request)
        return bool(al_dia)
