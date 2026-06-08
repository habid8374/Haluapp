"""Vistas del módulo de Facturación Electrónica (Factus).

Reglas:
  * Multi-institución: todo se filtra por la institución del usuario.
  * El módulo solo opera si ``ConfiguracionFactus.activo`` (lo activa el propietario).
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from finanzas.models import PagoRegistrado

from .emision import emitir_nota, emitir_para_pago
from .forms import ConfiguracionFactusForm
from .models import ConfiguracionFactus, FacturaElectronica
from .services import FactusClient, FactusError, FactusNoConfigurado

logger = logging.getLogger(__name__)


def _get_institucion(request):
    return getattr(request.user, "institucion_asociada", None)


@login_required
@permission_required("finanzas.change_institucioneducativa", raise_exception=True)
def configuracion(request):
    institucion = _get_institucion(request)
    if not institucion and not request.user.is_superuser:
        messages.error(request, "Tu usuario no está asociado a ninguna institución.")
        return redirect("gestion_academica:inicio_academico")

    config, _ = ConfiguracionFactus.objects.get_or_create(institucion=institucion)

    if request.method == "POST":
        form = ConfiguracionFactusForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, "Configuración de Factus guardada correctamente.")
            return redirect("facturacion_electronica:configuracion")
    else:
        form = ConfiguracionFactusForm(instance=config)

    return render(request, "facturacion_electronica/configuracion.html", {
        "form": form,
        "config": config,
        "titulo_pagina": "Facturación Electrónica — Configuración",
    })


@login_required
@permission_required("finanzas.change_institucioneducativa", raise_exception=True)
@require_POST
def probar_conexion(request):
    institucion = _get_institucion(request)
    config = get_object_or_404(ConfiguracionFactus, institucion=institucion)
    try:
        FactusClient(config).probar_conexion()
        messages.success(request, "✅ Conexión con Factus exitosa: las credenciales son válidas.")
    except FactusNoConfigurado as exc:
        messages.warning(request, f"Configuración incompleta: {exc}")
    except FactusError as exc:
        messages.error(request, f"No se pudo conectar con Factus: {exc}")
    return redirect("facturacion_electronica:configuracion")


@login_required
@permission_required("finanzas.change_institucioneducativa", raise_exception=True)
def listar_rangos(request):
    """Devuelve los rangos de numeración DIAN disponibles en Factus como JSON."""
    institucion = _get_institucion(request)
    config = ConfiguracionFactus.objects.filter(institucion=institucion).first()
    if not config:
        return JsonResponse({"ok": False, "error": "Guarda primero las credenciales de Factus."})
    try:
        rangos, raw = FactusClient(config).listar_rangos_numeracion()
        return JsonResponse({"ok": True, "rangos": rangos, "_raw": raw})
    except FactusNoConfigurado as exc:
        return JsonResponse({"ok": False, "error": f"Configuración incompleta: {exc}"})
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc)})


@login_required
def lista_facturas(request):
    institucion = _get_institucion(request)
    config = ConfiguracionFactus.objects.filter(institucion=institucion).first()

    qs = (
        FacturaElectronica.objects.filter(institucion=institucion)
        .select_related("estudiante__usuario", "pago", "documento_origen")
    )

    # ── KPIs (sobre el total, antes de filtrar) ──
    stats = qs.aggregate(
        total=Count("id"),
        validadas=Count("id", filter=Q(estado="VALIDADA")),
        facturas=Count("id", filter=Q(tipo="FACTURA", estado="VALIDADA")),
        notas_credito=Count("id", filter=Q(tipo="NOTA_CREDITO", estado="VALIDADA")),
        notas_debito=Count("id", filter=Q(tipo="NOTA_DEBITO", estado="VALIDADA")),
        errores=Count("id", filter=Q(estado="ERROR")),
    )
    monto_facturado = (
        qs.filter(tipo="FACTURA", estado="VALIDADA", pago__isnull=False)
        .aggregate(s=Sum("pago__valor_pagado"))["s"] or 0
    )

    # ── Filtros ──
    q = (request.GET.get("q") or "").strip()
    f_tipo = request.GET.get("tipo") or ""
    f_estado = request.GET.get("estado") or ""
    f_desde = request.GET.get("desde") or ""
    f_hasta = request.GET.get("hasta") or ""

    if q:
        qs = qs.filter(
            Q(numero__icontains=q) | Q(cufe__icontains=q) | Q(reference_code__icontains=q)
            | Q(estudiante__usuario__first_name__icontains=q)
            | Q(estudiante__usuario__last_name__icontains=q)
            | Q(estudiante__documento_identidad__icontains=q)
        )
    if f_tipo:
        qs = qs.filter(tipo=f_tipo)
    if f_estado:
        qs = qs.filter(estado=f_estado)
    if f_desde:
        qs = qs.filter(fecha_creacion__date__gte=f_desde)
    if f_hasta:
        qs = qs.filter(fecha_creacion__date__lte=f_hasta)

    paginator = Paginator(qs.order_by("-fecha_creacion"), 50)
    page = paginator.get_page(request.GET.get("page"))

    # Form de facturación masiva para el offcanvas
    form_masiva = None
    smtp_ok = False
    try:
        from finanzas.forms import FacturacionMasivaForm
        form_masiva = FacturacionMasivaForm(user=request.user)
        smtp_ok = bool(
            institucion
            and getattr(institucion, "email_host_user", None)
            and getattr(institucion, "email_host_password", None)
        )
    except Exception:
        pass

    return render(request, "facturacion_electronica/lista_facturas.html", {
        "facturas": page,
        "page_obj": page,
        "config": config,
        "modulo_activo": bool(config and config.activo),
        "stats": stats,
        "monto_facturado": monto_facturado,
        "consumo": getattr(config, "facturas_emitidas", 0) if config else 0,
        "filtros": {"q": q, "tipo": f_tipo, "estado": f_estado, "desde": f_desde, "hasta": f_hasta},
        "titulo_pagina": "Facturas Electrónicas",
        "form_masiva": form_masiva,
        "smtp_ok": smtp_ok,
    })


@login_required
def detalle_factura(request, factura_id):
    institucion = _get_institucion(request)
    factura = get_object_or_404(
        FacturaElectronica.objects.select_related("estudiante__usuario", "pago", "documento_origen"),
        pk=factura_id, institucion=institucion,
    )
    notas = factura.notas.all().order_by("-fecha_creacion")
    enviado = factura.json_enviado or {}
    items = enviado.get("items", []) or []
    customer = enviado.get("customer", {}) or {}
    total = sum(float(i.get("price", 0)) * float(i.get("quantity", 1)) for i in items)
    return render(request, "facturacion_electronica/detalle_factura.html", {
        "factura": factura,
        "notas": notas,
        "items": items,
        "customer": customer,
        "total": total,
        "titulo_pagina": f"Documento {factura.numero or factura.reference_code}",
    })


@login_required
@permission_required("finanzas.add_pagoregistrado", raise_exception=True)
@require_POST
def emitir_factura(request, pago_id):
    """Emite la factura electrónica de un PagoRegistrado vía Factus."""
    institucion = _get_institucion(request)
    pago = get_object_or_404(PagoRegistrado, pk=pago_id, institucion=institucion)

    try:
        factura = emitir_para_pago(pago)
    except (FactusError, FactusNoConfigurado) as exc:
        messages.error(request, f"No se pudo emitir la factura electrónica: {exc}")
        return redirect("finanzas:historial_cuentas_estudiante", estudiante_id=pago.estudiante_id)

    messages.success(
        request,
        f"✅ Factura electrónica emitida y validada (No. {factura.numero or factura.reference_code}).",
    )
    return redirect("finanzas:historial_cuentas_estudiante", estudiante_id=pago.estudiante_id)


@login_required
@permission_required("finanzas.add_pagoregistrado", raise_exception=True)
@require_POST
def emitir_nota_credito(request, factura_id):
    return _emitir_nota(request, factura_id, FacturaElectronica.Tipo.NOTA_CREDITO, default_code="2")


@login_required
@permission_required("finanzas.add_pagoregistrado", raise_exception=True)
@require_POST
def emitir_nota_debito(request, factura_id):
    return _emitir_nota(request, factura_id, FacturaElectronica.Tipo.NOTA_DEBITO, default_code="4")


def _emitir_nota(request, factura_id, tipo, default_code):
    institucion = _get_institucion(request)
    factura = get_object_or_404(FacturaElectronica, pk=factura_id, institucion=institucion)
    correction_code = request.POST.get("correction_code") or default_code

    # Monto solo aplica a NOTA DÉBITO (cargo adicional)
    monto = None
    if tipo == FacturaElectronica.Tipo.NOTA_DEBITO:
        try:
            monto = float(request.POST.get("monto") or 0)
        except (TypeError, ValueError):
            monto = 0
        if monto <= 0:
            messages.error(request, "Debes indicar un monto válido para la nota débito.")
            return redirect("facturacion_electronica:lista_facturas")

    etiqueta = "nota crédito" if tipo == FacturaElectronica.Tipo.NOTA_CREDITO else "nota débito"
    try:
        nota = emitir_nota(factura, tipo, correction_code, monto=monto)
    except (FactusError, FactusNoConfigurado) as exc:
        messages.error(request, f"No se pudo emitir la {etiqueta}: {exc}")
        return redirect("facturacion_electronica:lista_facturas")

    messages.success(request, f"✅ {etiqueta.capitalize()} emitida (No. {nota.numero or nota.reference_code}).")
    return redirect("facturacion_electronica:lista_facturas")
