"""Vistas del panel de control de la plataforma (superadmin).

Acceso: /halu-control/
Requiere: usuario Django is_superuser + clave maestra (SUPERADMIN_MASTER_PASSWORD).
"""
from __future__ import annotations

import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import (
    Case, CharField, Count, DecimalField, Q, Sum, Value, When,
)
from django.db.models.functions import Coalesce
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import SuperAdminLoginForm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Decorador de doble autenticación
# ---------------------------------------------------------------------------

def _superadmin_required(view_func):
    """Requiere is_superuser + sesión 'superadmin_autenticado'."""
    from functools import wraps

    @wraps(view_func)
    def _wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("platform_control:login")
        if not request.user.is_superuser:
            return HttpResponseForbidden("Solo super-admins.")
        if not request.session.get("superadmin_autenticado"):
            return redirect("platform_control:login")
        return view_func(request, *args, **kwargs)

    return _wrapper


# ---------------------------------------------------------------------------
# Login / Lock
# ---------------------------------------------------------------------------

def login_view(request):
    from django.contrib.auth import authenticate, login as auth_login

    if (request.user.is_authenticated
            and request.user.is_superuser
            and request.session.get("superadmin_autenticado")):
        return redirect("platform_control:dashboard")

    if request.method == "POST":
        form = SuperAdminLoginForm(request.POST)
        if form.is_valid():
            username       = form.cleaned_data["username"]
            password       = form.cleaned_data["password"]
            master_entered = form.cleaned_data["master_password"]
            master_ok      = getattr(settings, "SUPERADMIN_MASTER_PASSWORD", None)

            user = authenticate(request, username=username, password=password)
            if user is None:
                messages.error(request, "Usuario o contraseña incorrectos.")
            elif not user.is_superuser:
                messages.error(request, "Esta área es exclusiva para super-administradores.")
            elif master_entered != master_ok:
                messages.error(request, "Clave maestra incorrecta.")
            else:
                auth_login(request, user)
                request.session["superadmin_autenticado"] = True
                return redirect("platform_control:dashboard")
    else:
        form = SuperAdminLoginForm()

    return render(request, "platform_control/login.html", {"form": form})


@login_required
@user_passes_test(lambda u: u.is_superuser)
def lock_view(request):
    request.session.pop("superadmin_autenticado", None)
    messages.info(request, "Panel de control bloqueado.")
    return redirect("gestion_academica:inicio_academico")


# ---------------------------------------------------------------------------
# Dashboard principal
# ---------------------------------------------------------------------------

@_superadmin_required
def dashboard(request):
    from finanzas.models import InstitucionEducativa, PagoRegistrado, Gasto
    from gestion_academica.models import Estudiante, TicketSoporte

    total_instituciones = InstitucionEducativa.objects.count()
    total_estudiantes = Estudiante.objects.count()
    total_ingresos = PagoRegistrado.objects.aggregate(t=Sum("valor_pagado"))["t"] or 0
    total_gastos = Gasto.objects.aggregate(t=Sum("monto"))["t"] or 0

    ingresos_data = InstitucionEducativa.objects.annotate(
        total_ingresos=Coalesce(Sum("pagoregistrado__valor_pagado"), 0, output_field=DecimalField())
    ).order_by("-total_ingresos")

    chart_labels = [i.nombre for i in ingresos_data]
    chart_data = [float(i.total_ingresos) for i in ingresos_data]

    instituciones = InstitucionEducativa.objects.annotate(
        num_estudiantes=Count("estudiantes", distinct=True),
        test_keys_ok=Case(
            When(
                Q(mp_public_key_test__isnull=False, mp_public_key_test__gt="")
                & Q(mp_access_token_test__isnull=False, mp_access_token_test__gt=""),
                then=Value("OK"),
            ),
            default=Value("Pendiente"),
            output_field=CharField(),
        ),
        prod_keys_ok=Case(
            When(
                Q(mp_public_key_prod__isnull=False, mp_public_key_prod__gt="")
                & Q(mp_access_token_prod__isnull=False, mp_access_token_prod__gt=""),
                then=Value("OK"),
            ),
            default=Value("Pendiente"),
            output_field=CharField(),
        ),
    ).order_by("nombre")

    tickets_abiertos_count = TicketSoporte.objects.filter(
        Q(estado="ABIERTO") | Q(estado="EN_PROGRESO")
    ).count()

    context = {
        "titulo_pagina": "Panel de Control",
        "total_instituciones": total_instituciones,
        "total_estudiantes": total_estudiantes,
        "total_ingresos": total_ingresos,
        "total_gastos": total_gastos,
        "chart_labels": json.dumps(chart_labels),
        "chart_data": json.dumps(chart_data),
        "instituciones": instituciones,
        "ingresos_por_institucion": ingresos_data,
        "tickets_abiertos_count": tickets_abiertos_count,
    }
    return render(request, "platform_control/dashboard.html", context)


# ---------------------------------------------------------------------------
# Gestión de instituciones
# ---------------------------------------------------------------------------

@require_POST
@user_passes_test(lambda u: u.is_superuser)
def toggle_institucion(request, pk):
    from finanzas.models import InstitucionEducativa

    institucion = get_object_or_404(InstitucionEducativa, pk=pk)
    institucion.activa = not institucion.activa
    institucion.save(update_fields=["activa"])
    estado = "activada" if institucion.activa else "bloqueada"
    messages.success(request, f"La institución '{institucion.nombre}' ha sido {estado}.")
    return redirect("platform_control:dashboard")


# ---------------------------------------------------------------------------
# Soporte / Tickets
# ---------------------------------------------------------------------------

@_superadmin_required
def tickets_view(request):
    from gestion_academica.models import TicketSoporte

    todos = TicketSoporte.objects.select_related(
        "usuario_reporta", "institucion"
    ).order_by("estado", "-ultima_actualizacion")

    return render(request, "platform_control/tickets.html", {
        "titulo_pagina": "Soporte — Todos los Tickets",
        "tickets": todos,
    })


@_superadmin_required
def ticket_detail_view(request, ticket_id):
    from gestion_academica.models import TicketSoporte, RespuestaTicket
    from gestion_academica.forms import RespuestaTicketForm  # reutilizamos el form existente

    ticket = get_object_or_404(TicketSoporte, ticket_id=ticket_id)

    if request.method == "POST":
        form = RespuestaTicketForm(request.POST, request.FILES)
        if form.is_valid():
            respuesta = form.save(commit=False)
            respuesta.ticket = ticket
            respuesta.autor = request.user
            respuesta.save()
            if ticket.estado == TicketSoporte.Estado.ABIERTO:
                ticket.estado = TicketSoporte.Estado.EN_PROGRESO
                ticket.save(update_fields=["estado", "ultima_actualizacion"])
            messages.success(request, "Respuesta añadida al ticket.")
            return redirect("platform_control:ticket_detail", ticket_id=ticket.ticket_id)
    else:
        form = RespuestaTicketForm()

    return render(request, "platform_control/ticket_detail.html", {
        "titulo_pagina": f"Ticket [{ticket.ticket_id}]",
        "ticket": ticket,
        "respuestas": ticket.respuestas.select_related("autor").order_by("fecha_creacion"),
        "form": form,
    })


@require_POST
@user_passes_test(lambda u: u.is_superuser)
def cerrar_ticket_view(request, ticket_id):
    from gestion_academica.models import TicketSoporte

    ticket = get_object_or_404(TicketSoporte, ticket_id=ticket_id)
    ticket.estado = TicketSoporte.Estado.CERRADO
    ticket.save(update_fields=["estado", "ultima_actualizacion"])
    messages.success(request, f"Ticket [{ticket.ticket_id}] cerrado.")
    return redirect("platform_control:ticket_detail", ticket_id=ticket.ticket_id)


# ---------------------------------------------------------------------------
# Mantenimiento / Health-check
# ---------------------------------------------------------------------------

@_superadmin_required
def mantenimiento_dashboard(request):
    from finanzas.models import EjecucionHealthCheck, InstitucionEducativa

    ultima = EjecucionHealthCheck.objects.first()
    historico = EjecucionHealthCheck.objects.select_related(
        "iniciado_por", "institucion_filtro"
    )[:20]
    instituciones = InstitucionEducativa.objects.order_by("nombre")

    return render(request, "platform_control/mantenimiento_dashboard.html", {
        "titulo_pagina": "Mantenimiento del Sistema",
        "ultima_ejecucion": ultima,
        "historico": historico,
        "instituciones": instituciones,
        "PASOS_TOTALES": 8,
    })


@_superadmin_required
@require_POST
def mantenimiento_ejecutar(request):
    from finanzas.models import EjecucionHealthCheck
    from finanzas.tasks import run_health_check_task

    institucion_id_str = (request.POST.get("institucion_id") or "").strip()
    institucion_id = int(institucion_id_str) if institucion_id_str.isdigit() else None

    ejecucion = EjecucionHealthCheck.objects.create(
        iniciado_por=request.user,
        institucion_filtro_id=institucion_id,
        estado=EjecucionHealthCheck.Estado.PENDIENTE,
    )

    try:
        result = run_health_check_task.delay(ejecucion.pk, institucion_id)
        ejecucion.task_id = result.id or ""
        ejecucion.save(update_fields=["task_id"])
    except Exception as exc:
        ejecucion.estado = EjecucionHealthCheck.Estado.FALLIDO
        ejecucion.error_excepcion = f"No se pudo encolar la tarea Celery: {exc}"
        ejecucion.save(update_fields=["estado", "error_excepcion"])
        messages.error(request, f"No se pudo encolar el diagnóstico: {exc}")
        return redirect("platform_control:mantenimiento")

    messages.info(request, f"Diagnóstico #{ejecucion.pk} iniciado.")
    return redirect("platform_control:mantenimiento_detalle", pk=ejecucion.pk)


@_superadmin_required
def mantenimiento_detalle(request, pk):
    from finanzas.models import EjecucionHealthCheck

    ejecucion = get_object_or_404(EjecucionHealthCheck, pk=pk)
    return render(request, "platform_control/mantenimiento_detalle.html", {
        "titulo_pagina": f"Diagnóstico #{ejecucion.pk}",
        "ejecucion": ejecucion,
        "PASOS_TOTALES": 8,
    })


@_superadmin_required
def mantenimiento_estado_api(request, pk):
    from finanzas.models import EjecucionHealthCheck

    ejecucion = get_object_or_404(EjecucionHealthCheck, pk=pk)
    return JsonResponse({
        "id": ejecucion.pk,
        "estado": ejecucion.estado,
        "errores_count": ejecucion.errores_count,
        "warnings_count": ejecucion.warnings_count,
        "pasos_completados": ejecucion.pasos_completados,
        "pasos_totales": 8,
        "iniciado_at": ejecucion.iniciado_at.isoformat(),
        "terminado_at": ejecucion.terminado_at.isoformat() if ejecucion.terminado_at else None,
        "duracion_segundos": ejecucion.duracion_segundos,
        "eventos": ejecucion.eventos or [],
        "error_excepcion": ejecucion.error_excepcion,
    })
