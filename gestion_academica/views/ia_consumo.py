# gestion_academica/views/ia_consumo.py
"""Panel de consumo de IA para rector/coordinador: ver lo consumido en el mes,
el tope y poder ampliarlo desde la interfaz."""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _


def _puede_ver_ia(user):
    rol = getattr(user, 'rol', '') or ''
    return user.is_superuser or rol in ('coordinador', 'rector', 'administrador', 'admin_institucion')


@login_required
def consumo_ia(request):
    if not _puede_ver_ia(request.user):
        raise PermissionDenied
    institucion = getattr(request.user, 'institucion_asociada', None)
    if institucion is None:
        raise PermissionDenied("Sin institución asociada.")

    from finanzas import ia as ia_gate
    from finanzas.models import ConsumoIA

    if request.method == 'POST':
        crudo = (request.POST.get('ia_tope_mensual_cop') or '0')
        # Acepta "50000", "50.000", "$50.000" → solo dígitos.
        solo_digitos = ''.join(c for c in crudo if c.isdigit())
        try:
            institucion.ia_tope_mensual_cop = Decimal(solo_digitos or '0')
            institucion.ia_bloquear_al_superar = bool(request.POST.get('ia_bloquear_al_superar'))
            institucion.save(update_fields=['ia_tope_mensual_cop', 'ia_bloquear_al_superar'])
            messages.success(request, _("Tope de IA actualizado."))
        except (InvalidOperation, ValueError):
            messages.error(request, _("El tope debe ser un número válido en pesos."))
        return redirect('gestion_academica:consumo_ia')

    resumen = ia_gate.resumen_mes(institucion)
    historial = (ConsumoIA.objects
                 .filter(institucion=institucion)
                 .order_by('-anio', '-mes')[:12])
    return render(request, 'gestion_academica/consumo_ia.html', {
        'titulo_pagina': _('Consumo de IA'),
        'institucion': institucion,
        'r': resumen,
        'historial': historial,
    })
