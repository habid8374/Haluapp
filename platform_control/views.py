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
from django_ratelimit.decorators import ratelimit

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
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]

            user = authenticate(request, username=username, password=password)
            if user is None:
                messages.error(request, "Usuario o contraseña incorrectos.")
            elif not user.is_superuser:
                messages.error(request, "Esta área es exclusiva para super-administradores.")
            else:
                auth_login(request, user)
                try:
                    tiene_2fa = user.dispositivo_totp.confirmado
                except Exception:
                    tiene_2fa = False

                if tiene_2fa:
                    request.session["superadmin_2fa_pending"] = True
                    return redirect("platform_control:verificar_2fa")
                else:
                    request.session["superadmin_autenticado"] = True
                    return redirect("platform_control:dashboard")
    else:
        form = SuperAdminLoginForm()

    return render(request, "platform_control/login.html", {"form": form})


@ratelimit(key='user', rate='5/m', method='POST', block=True)
def verificar_2fa_superadmin(request):
    """4ta capa de seguridad: TOTP para el panel superadmin."""
    if not request.user.is_authenticated or not request.user.is_superuser:
        return redirect("platform_control:login")
    if not request.session.get("superadmin_2fa_pending"):
        return redirect("platform_control:login")

    try:
        disp = request.user.dispositivo_totp
    except Exception:
        request.session["superadmin_autenticado"] = True
        request.session.pop("superadmin_2fa_pending", None)
        return redirect("platform_control:dashboard")

    if request.method == "POST":
        codigo = request.POST.get("codigo", "").strip().replace(" ", "")
        if disp.verificar(codigo):
            request.session.pop("superadmin_2fa_pending", None)
            request.session["superadmin_autenticado"] = True
            return redirect("platform_control:dashboard")
        else:
            messages.error(request, "Código incorrecto. Intenta de nuevo.")

    return render(request, "platform_control/verificar_2fa.html")


@login_required
@user_passes_test(lambda u: u.is_superuser)
def lock_view(request):
    request.session.pop("superadmin_autenticado", None)
    request.session.pop("superadmin_2fa_pending", None)
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

@_superadmin_required
def consumo_ia_global(request):
    """Panel consolidado del consumo de IA de TODAS las instituciones (mes actual)."""
    from finanzas.models import ConsumoIA
    from django.utils import timezone
    from decimal import Decimal
    ahora = timezone.now()
    anio = int(request.GET.get('anio') or ahora.year)
    mes = int(request.GET.get('mes') or ahora.month)

    filas = list(
        ConsumoIA.objects
        .filter(anio=anio, mes=mes)
        .select_related('institucion')
        .order_by('-costo_estimado_cop')
    )
    total_costo = sum((f.costo_estimado_cop for f in filas), Decimal('0'))
    total_ops = sum((f.operaciones for f in filas), 0)
    # Marca cuáles superaron su tope.
    for f in filas:
        tope = f.institucion.ia_tope_mensual_cop or 0
        f.tope_cop = tope
        f.supero = bool(tope and f.costo_estimado_cop >= tope)
        f.pct = (float(f.costo_estimado_cop / tope * 100) if tope else None)

    return render(request, "platform_control/consumo_ia.html", {
        "filas": filas,
        "anio": anio,
        "mes": mes,
        "total_costo": total_costo,
        "total_ops": total_ops,
    })


@require_POST
@_superadmin_required
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
@_superadmin_required
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
def mantenimiento_descargar(request, pk, formato):
    """Descarga el log del diagnóstico en .txt o .json."""
    from django.http import HttpResponse
    from finanzas.models import EjecucionHealthCheck
    import json as _json

    ejecucion = get_object_or_404(EjecucionHealthCheck, pk=pk)
    eventos = ejecucion.eventos or []
    base = f"diagnostico_{ejecucion.pk}"

    if formato == 'json':
        data = {
            "id": ejecucion.pk,
            "estado": ejecucion.estado,
            "iniciado_por": getattr(ejecucion.iniciado_por, 'email', '') or str(ejecucion.iniciado_por or ''),
            "institucion_filtro": getattr(ejecucion.institucion_filtro, 'nombre', None),
            "iniciado_at": ejecucion.iniciado_at.isoformat() if ejecucion.iniciado_at else None,
            "terminado_at": ejecucion.terminado_at.isoformat() if ejecucion.terminado_at else None,
            "duracion_segundos": ejecucion.duracion_segundos,
            "errores_count": ejecucion.errores_count,
            "warnings_count": ejecucion.warnings_count,
            "pasos_completados": ejecucion.pasos_completados,
            "error_excepcion": ejecucion.error_excepcion,
            "eventos": eventos,
        }
        resp = HttpResponse(
            _json.dumps(data, ensure_ascii=False, indent=2),
            content_type='application/json; charset=utf-8',
        )
        resp['Content-Disposition'] = f'attachment; filename="{base}.json"'
        return resp

    # .txt (por defecto) — reproduce el log tal como se ve en pantalla
    lineas = [
        f"Diagnóstico #{ejecucion.pk}",
        f"Estado: {ejecucion.get_estado_display()}",
        f"Iniciado: {ejecucion.iniciado_at:%Y-%m-%d %H:%M:%S}" if ejecucion.iniciado_at else "Iniciado: —",
        f"Por: {getattr(ejecucion.iniciado_por, 'email', '') or ejecucion.iniciado_por or '—'}",
        f"Errores: {ejecucion.errores_count} · Advertencias: {ejecucion.warnings_count} · Pasos: {ejecucion.pasos_completados}/8",
        "=" * 60,
        "",
    ]
    for ev in eventos:
        nivel = (ev.get('nivel') or '').upper()
        if nivel == 'INFO' and ev.get('paso'):
            lineas.append(f"[{ev.get('paso')}] {ev.get('titulo', '')}")
        else:
            pref = {'OK': '  [OK]   ', 'WARN': '  [WARN] ', 'ERR': '  [ERR]  '}.get(nivel, '        ')
            lineas.append(f"{pref}{ev.get('mensaje', '')}")
    if ejecucion.error_excepcion:
        lineas += ["", "EXCEPCIÓN:", ejecucion.error_excepcion]
    resp = HttpResponse("\n".join(lineas), content_type='text/plain; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="{base}.txt"'
    return resp


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


# ---------------------------------------------------------------------------
# Onboarding de nuevo colegio
# ---------------------------------------------------------------------------

class _OnboardingForm:
    """Formulario ligero sin Django forms para el onboarding."""

    def __init__(self, data=None):
        self.data = data or {}
        self.errors: dict[str, str] = {}
        self.non_field_errors: list[str] = []
        self._cleaned: dict = {}

    # Atributos compatibles con el template (acceso via form.field.value / form.field.errors)
    class _Field:
        def __init__(self, value, errors):
            self._value = value
            self.errors = errors

        def value(self):
            return self._value

    def __getattr__(self, name):
        if name.startswith("_") or name in ("data", "errors", "non_field_errors"):
            raise AttributeError(name)
        return self._Field(
            value=self.data.get(name, ""),
            errors=[self.errors.get(name)] if name in self.errors else [],
        )

    def is_valid(self) -> bool:
        d = self.data
        nombre = (d.get("nombre") or "").strip()
        nit = (d.get("nit") or "").strip()
        admin_email = (d.get("admin_email") or "").strip()
        niveles = d.getlist("niveles") if hasattr(d, "getlist") else d.get("niveles", [])

        if not nombre:
            self.errors["nombre"] = "Este campo es obligatorio."
        if not nit:
            self.errors["nit"] = "Este campo es obligatorio."
        if not admin_email:
            self.errors["admin_email"] = "Este campo es obligatorio."
        elif "@" not in admin_email:
            self.errors["admin_email"] = "Ingresa un email válido."
        if not niveles:
            self.errors["niveles"] = "Selecciona al menos un nivel educativo."

        self._cleaned = {
            "nombre": nombre,
            "nit": nit,
            "direccion": (d.get("direccion") or "").strip(),
            "telefono": (d.get("telefono") or "").strip(),
            "correo_electronico": (d.get("correo_electronico") or "").strip(),
            "admin_email": admin_email,
            "niveles": niveles if isinstance(niveles, list) else [niveles],
        }
        return not self.errors

    @property
    def cleaned_data(self):
        return self._cleaned


def _aprovisionar_colegio(cleaned: dict) -> dict:
    """Crea la institución con toda su estructura y devuelve un dict con el resumen."""
    import random
    import string
    from datetime import date

    from django.contrib.auth.hashers import make_password

    from finanzas.models import InstitucionEducativa
    from gestion_academica.models import (
        Grado, NivelEscolaridad, PeriodoAcademico, Usuario,
    )

    # ── Grados estándar por nivel ─────────────────────────────────────────
    GRADOS_POR_NIVEL = {
        "preescolar": [
            ("Pre-jardín", 0),
            ("Jardín", 1),
            ("Transición", 2),
        ],
        "primaria": [
            ("Primero", 1),
            ("Segundo", 2),
            ("Tercero", 3),
            ("Cuarto", 4),
            ("Quinto", 5),
        ],
        "secundaria": [
            ("Sexto", 6),
            ("Séptimo", 7),
            ("Octavo", 8),
            ("Noveno", 9),
        ],
        "media": [
            ("Décimo", 10),
            ("Undécimo", 11),
        ],
    }

    NOMBRE_NIVEL = {
        "preescolar": "Preescolar",
        "primaria": "Primaria",
        "secundaria": "Secundaria",
        "media": "Media",
    }

    ORDEN_NIVEL = {
        "preescolar": 1,
        "primaria": 2,
        "secundaria": 3,
        "media": 4,
    }

    # ── 1. Crear institución ──────────────────────────────────────────────
    institucion = InstitucionEducativa.objects.create(
        nombre=cleaned["nombre"],
        nit=cleaned["nit"],
        direccion=cleaned["direccion"] or None,
        telefono=cleaned["telefono"] or None,
        correo_electronico=cleaned["correo_electronico"] or None,
    )

    # ── 2. Crear niveles y grados ─────────────────────────────────────────
    niveles_grados: dict[str, list] = {}
    todos_grados: list = []

    for clave in cleaned["niveles"]:
        clave = clave.lower()
        if clave not in GRADOS_POR_NIVEL:
            continue
        nombre_nivel = NOMBRE_NIVEL[clave]
        orden_nivel = ORDEN_NIVEL[clave]

        nivel_obj, _ = NivelEscolaridad.objects.get_or_create(
            nombre=nombre_nivel,
            institucion=institucion,
            defaults={"orden": orden_nivel},
        )

        grados_nivel: list = []
        for nombre_grado, orden_grado in GRADOS_POR_NIVEL[clave]:
            grado_obj, _ = Grado.objects.get_or_create(
                nombre=nombre_grado,
                institucion=institucion,
                defaults={
                    "nivel_escolaridad": nivel_obj,
                    "orden": orden_grado,
                },
            )
            grados_nivel.append(grado_obj)
            todos_grados.append(grado_obj)

        niveles_grados[nombre_nivel] = grados_nivel

    # ── 3. Crear períodos académicos del año actual ───────────────────────
    anio = date.today().year
    PERIODOS = [
        ("Período 1", date(anio, 1, 14),  date(anio, 3, 28)),
        ("Período 2", date(anio, 4, 1),   date(anio, 6, 20)),
        ("Período 3", date(anio, 7, 14),  date(anio, 9, 26)),
        ("Período 4", date(anio, 9, 29),  date(anio, 11, 28)),
    ]

    periodos_creados = []
    for idx, (nombre_p, fecha_inicio, fecha_fin) in enumerate(PERIODOS, start=1):
        p, _ = PeriodoAcademico.objects.get_or_create(
            nombre=nombre_p,
            año_escolar=anio,
            institucion=institucion,
            defaults={
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin,
                "activo": (idx == 1),
            },
        )
        periodos_creados.append(p)

    # ── 4. Crear usuario admin_institucion ────────────────────────────────
    admin_email = cleaned["admin_email"]
    base_username = admin_email.split("@")[0].replace(".", "_").replace("+", "_")
    username = base_username
    suffix = 1
    while Usuario.objects.filter(username=username).exists():
        username = f"{base_username}_{suffix}"
        suffix += 1

    temp_password = (
        "".join(random.choices(string.ascii_uppercase, k=3))
        + "".join(random.choices(string.digits, k=4))
        + "".join(random.choices(string.ascii_lowercase, k=3))
    )

    admin_user = Usuario.objects.create(
        username=username,
        email=admin_email,
        rol="administrador",
        institucion_asociada=institucion,
        password=make_password(temp_password),
        is_staff=True,
    )

    return {
        "institucion": institucion,
        "niveles_grados": niveles_grados,
        "grados": todos_grados,
        "periodos": periodos_creados,
        "admin_username": admin_user.username,
        "admin_email": admin_user.email,
        "admin_password": temp_password,
        "anio": anio,
    }


@_superadmin_required
def onboarding_nuevo_colegio(request):
    resultado = None

    if request.method == "POST":
        form = _OnboardingForm(request.POST)
        if form.is_valid():
            try:
                resultado = _aprovisionar_colegio(form.cleaned_data)
                messages.success(
                    request,
                    f"Colegio «{resultado['institucion'].nombre}» aprovisionado correctamente.",
                )
                # Renderizamos directamente el resumen (no redirect-after-POST)
                # para que el contexto con la contraseña temporal esté disponible
                # en el template sin necesidad de sesión temporal.
                return render(
                    request,
                    "platform_control/onboarding_colegio.html",
                    {
                        "titulo_pagina": "Colegio aprovisionado",
                        "resultado": resultado,
                        "form": _OnboardingForm(),
                    },
                )
            except Exception as exc:
                logger.exception("onboarding_nuevo_colegio: error aprovisionando: %s", exc)
                messages.error(
                    request,
                    f"Error al aprovisionar el colegio: {exc}",
                )
    else:
        form = _OnboardingForm()

    return render(
        request,
        "platform_control/onboarding_colegio.html",
        {
            "titulo_pagina": "Aprovisionar Nuevo Colegio",
            "form": form,
            "resultado": resultado,
        },
    )


# ---------------------------------------------------------------------------
# Backups
# ---------------------------------------------------------------------------

@_superadmin_required
def backup_view(request):
    """Lista los backups en R2/S3 y permite generar uno manual."""
    import os
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    bucket = os.environ.get("AWS_STORAGE_BUCKET_NAME", "")
    endpoint = os.environ.get("AWS_S3_ENDPOINT_URL") or None
    backups = []
    s3_error = None

    if bucket:
        try:
            s3 = boto3.client(
                "s3",
                endpoint_url=endpoint,
                aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
                region_name=os.environ.get("AWS_S3_REGION_NAME", "auto"),
            )
            result = s3.list_objects_v2(Bucket=bucket, Prefix="backups/")
            for obj in result.get("Contents", []):
                key = obj["Key"]
                if key == "backups/":
                    continue
                backups.append({
                    "nombre": key.replace("backups/", ""),
                    "key": key,
                    "fecha": obj["LastModified"],
                    "tamano_kb": round(obj["Size"] / 1024, 1),
                })
            backups.sort(key=lambda x: x["fecha"], reverse=True)
        except (BotoCoreError, ClientError) as e:
            s3_error = str(e)
            logger.warning("Error listando backups en R2: %s", e)
    else:
        s3_error = "AWS_STORAGE_BUCKET_NAME no configurado."

    return render(request, "platform_control/backup.html", {
        "titulo_pagina": "Copias de Seguridad",
        "backups": backups,
        "s3_error": s3_error,
        "bucket": bucket,
    })


@_superadmin_required
@require_POST
def backup_ejecutar(request):
    """Ejecuta el backup directamente (síncrono) y también encola en Celery si está disponible."""
    from django.core.management import call_command
    from io import StringIO

    out = StringIO()
    try:
        call_command('backup_database', stdout=out, stderr=out)
        resultado = out.getvalue()
        if '✅' in resultado:
            messages.success(request, "✅ Backup generado y subido a R2 correctamente.")
        else:
            messages.warning(request, f"Backup ejecutado con advertencias: {resultado.strip()}")
    except Exception as e:
        logger.error("Error al ejecutar backup: %s", e, exc_info=True)
        messages.error(request, f"No se pudo ejecutar el backup: {e}")
    return redirect("platform_control:backup")


# ---------------------------------------------------------------------------
# Conexiones y Seguridad — usuarios conectados, historial, cierre remoto
# ---------------------------------------------------------------------------

def _terminar_sesiones_de_usuario(user_id):
    """Elimina todas las sesiones activas de un usuario. Devuelve cuántas cerró."""
    from django.contrib.sessions.models import Session
    from django.utils import timezone

    eliminadas = 0
    for s in Session.objects.filter(expire_date__gte=timezone.now()):
        try:
            if str(s.get_decoded().get('_auth_user_id')) == str(user_id):
                s.delete()
                eliminadas += 1
        except Exception:
            continue
    return eliminadas


@_superadmin_required
def conexiones_view(request):
    """Muestra usuarios conectados ahora + historial de conexiones con filtros."""
    from django.contrib.auth import get_user_model
    from django.contrib.sessions.models import Session
    from django.core.paginator import Paginator
    from django.utils import timezone
    from finanzas.models import InstitucionEducativa
    from auditoria.models import RegistroSesion

    import datetime as _dt

    Usuario = get_user_model()
    ahora = timezone.now()
    tz = timezone.get_current_timezone()

    # --- Conectados ahora: sesiones activas en BD ---
    uid_por_key = {}
    sesiones_data = {}  # session_key -> dict decodificado de la sesión
    for s in Session.objects.filter(expire_date__gte=ahora):
        try:
            data = s.get_decoded()
        except Exception:
            continue
        uid = data.get('_auth_user_id')
        if uid:
            uid_por_key[s.session_key] = (uid, s.expire_date)
            sesiones_data[s.session_key] = data

    usuarios = {
        str(u.pk): u
        for u in Usuario.objects.filter(
            pk__in=[v[0] for v in uid_por_key.values()]
        ).select_related('institucion_asociada')
    }

    # Último LOGIN por session_key → IP/dispositivo/hora de inicio (respaldo)
    login_info = {}
    if uid_por_key:
        for r in RegistroSesion.objects.filter(
            session_key__in=list(uid_por_key.keys()), tipo_evento='LOGIN'
        ).order_by('fecha'):
            login_info[r.session_key] = r  # el último gana

    conectados = []
    for key, (uid, expira) in uid_por_key.items():
        u = usuarios.get(str(uid))
        if u is None:
            continue
        info = login_info.get(key)
        data = sesiones_data.get(key, {})

        # IP/dispositivo EN VIVO desde la sesión; si no hay, caemos al login.
        ip_vivo = data.get('_halu_ip')
        ua_vivo = data.get('_halu_ua')
        seen = data.get('_halu_seen')
        ultima = _dt.datetime.fromtimestamp(seen, tz=tz) if seen else None

        conectados.append({
            'usuario': u,
            'institucion': getattr(u, 'institucion_asociada', None),
            'ip': ip_vivo or (info.ip_address if info else None),
            'user_agent': ua_vivo or (info.user_agent if info else ''),
            'inicio': info.fecha if info else None,
            'ultima': ultima,
            'session_key': key,
            'expira': expira,
        })

    def _orden(a):
        t = a['ultima'] or a['inicio']
        return (t is not None, t)
    conectados.sort(key=_orden, reverse=True)

    # --- Historial con filtros ---
    historial_qs = RegistroSesion.objects.select_related(
        'usuario', 'institucion', 'ejecutado_por'
    )
    f_inst = request.GET.get('inst') or ''
    f_q = (request.GET.get('q') or '').strip()
    f_tipo = request.GET.get('tipo') or ''
    f_ip = (request.GET.get('ip') or '').strip()
    f_desde = request.GET.get('desde') or ''
    f_hasta = request.GET.get('hasta') or ''

    if f_inst:
        historial_qs = historial_qs.filter(institucion_id=f_inst)
    if f_tipo:
        historial_qs = historial_qs.filter(tipo_evento=f_tipo)
    if f_ip:
        historial_qs = historial_qs.filter(ip_address__icontains=f_ip)
    if f_q:
        historial_qs = historial_qs.filter(
            Q(usuario__email__icontains=f_q)
            | Q(usuario__username__icontains=f_q)
            | Q(usuario__first_name__icontains=f_q)
            | Q(usuario__last_name__icontains=f_q)
        )
    if f_desde:
        historial_qs = historial_qs.filter(fecha__date__gte=f_desde)
    if f_hasta:
        historial_qs = historial_qs.filter(fecha__date__lte=f_hasta)

    page = Paginator(historial_qs, 40).get_page(request.GET.get('page'))

    return render(request, "platform_control/conexiones.html", {
        "titulo_pagina": "Conexiones y Seguridad",
        "conectados": conectados,
        "total_conectados": len(conectados),
        "historial": page,
        "instituciones": InstitucionEducativa.objects.order_by('nombre'),
        "tipos_evento": RegistroSesion.EVENTOS,
        "f_inst": f_inst, "f_q": f_q, "f_tipo": f_tipo,
        "f_ip": f_ip, "f_desde": f_desde, "f_hasta": f_hasta,
    })


@require_POST
@_superadmin_required
def cerrar_sesion_remota(request):
    """Cierra UNA sesión activa (por session_key) — expulsa al instante."""
    from django.contrib.sessions.models import Session
    from django.contrib.auth import get_user_model
    from auditoria.models import RegistroSesion
    from auditoria.middleware import _get_client_ip

    session_key = request.POST.get('session_key', '')
    s = Session.objects.filter(session_key=session_key).first()
    if not s:
        messages.warning(request, "Esa sesión ya no está activa.")
        return redirect("platform_control:conexiones")

    uid = None
    try:
        uid = s.get_decoded().get('_auth_user_id')
    except Exception:
        pass
    Usuario = get_user_model()
    afectado = Usuario.objects.filter(pk=uid).first() if uid else None

    s.delete()
    RegistroSesion.objects.create(
        usuario=afectado,
        institucion=getattr(afectado, 'institucion_asociada', None) if afectado else None,
        tipo_evento='CIERRE_REMOTO',
        ip_address=_get_client_ip(request),
        session_key=session_key,
        ejecutado_por=request.user,
    )
    nombre = (afectado.get_full_name() or afectado.username) if afectado else "usuario"
    messages.success(request, f"Sesión de {nombre} cerrada correctamente.")
    return redirect("platform_control:conexiones")


@require_POST
@_superadmin_required
def cerrar_sesiones_usuario(request, user_id):
    """Cierra TODAS las sesiones activas de un usuario."""
    from django.contrib.auth import get_user_model
    from auditoria.models import RegistroSesion
    from auditoria.middleware import _get_client_ip

    Usuario = get_user_model()
    afectado = get_object_or_404(Usuario, pk=user_id)
    n = _terminar_sesiones_de_usuario(user_id)

    RegistroSesion.objects.create(
        usuario=afectado,
        institucion=getattr(afectado, 'institucion_asociada', None),
        tipo_evento='CIERRE_REMOTO',
        ip_address=_get_client_ip(request),
        ejecutado_por=request.user,
    )
    nombre = afectado.get_full_name() or afectado.username
    messages.success(request, f"Se cerraron {n} sesión(es) de {nombre}.")
    return redirect("platform_control:conexiones")


@require_POST
@_superadmin_required
def restablecer_password_emergencia(request, user_id):
    """Bloqueo de emergencia: contraseña temporal aleatoria + cierre de todas
    las sesiones del usuario. Para casos de credenciales comprometidas."""
    from django.contrib.auth import get_user_model
    from django.utils.crypto import get_random_string
    from auditoria.models import RegistroSesion
    from auditoria.middleware import _get_client_ip

    Usuario = get_user_model()
    afectado = get_object_or_404(Usuario, pk=user_id)

    # No permitir restablecer a OTRO super-administrador por esta vía.
    if afectado.is_superuser and afectado.pk != request.user.pk:
        messages.error(request, "No puedes restablecer la contraseña de otro super-administrador desde aquí.")
        return redirect("platform_control:conexiones")

    # Contraseña temporal fuerte pero legible (sin caracteres ambiguos).
    alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    temporal = get_random_string(12, alfabeto)
    afectado.set_password(temporal)
    afectado.save(update_fields=["password"])

    n = _terminar_sesiones_de_usuario(user_id)

    RegistroSesion.objects.create(
        usuario=afectado,
        institucion=getattr(afectado, 'institucion_asociada', None),
        tipo_evento='RESET_EMERGENCIA',
        ip_address=_get_client_ip(request),
        ejecutado_por=request.user,
    )
    nombre = afectado.get_full_name() or afectado.username
    messages.success(
        request,
        f"Acceso bloqueado: contraseña de {nombre} restablecida y {n} sesión(es) cerradas. "
        f"Contraseña temporal (se muestra UNA sola vez): {temporal}  ·  "
        f"Entrégala por un canal seguro; el usuario debe cambiarla al ingresar."
    )
    return redirect("platform_control:conexiones")
