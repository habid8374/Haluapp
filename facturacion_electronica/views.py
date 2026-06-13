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
from django.http import HttpResponse, JsonResponse
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
def factura_pdf(request, factura_id):
    """Genera la representación gráfica propia de la factura electrónica como PDF."""
    from django.template.loader import render_to_string

    institucion = _get_institucion(request)
    factura = get_object_or_404(
        FacturaElectronica.objects.select_related(
            "estudiante__usuario", "estudiante__grado_actual",
            "pago", "institucion",
        ),
        pk=factura_id, institucion=institucion,
    )

    enviado = factura.json_enviado or {}
    items_raw = enviado.get("items", []) or []
    customer = enviado.get("customer", {}) or {}

    # Calcular total por ítem (price * quantity)
    items = []
    total = 0
    for it in items_raw:
        precio = float(it.get("price", 0))
        qty = float(it.get("quantity", 1))
        subtotal = precio * qty
        total += subtotal
        items.append({**it, "total": subtotal})

    # Datos del adquiriente desde el JSON enviado a Factus
    customer_name = customer.get("names") or customer.get("name") or "—"
    customer_doc = customer.get("identification") or "—"
    customer_doc_type = "CC"
    doc_code = str(customer.get("identification_document_code", "13"))
    if doc_code == "31":
        customer_doc_type = "NIT"
    elif doc_code == "12":
        customer_doc_type = "TI"
    customer_email = customer.get("email") or ""
    customer_address = customer.get("address") or ""

    # Logo del COLEGIO: el mismo que usa la plataforma (ConfiguracionInstitucion),
    # con fallback al logo de InstitucionEducativa. Se incrusta como data URI
    # leyendo directo del storage (no depende de que /media/ sea servible).
    config_inst = getattr(factura.institucion, "configuracioninstitucion", None)
    logo_field = (config_inst.logo if config_inst and config_inst.logo else None) or (
        factura.institucion.logo if factura.institucion.logo else None
    )
    logo_url = ""
    logo_error = ""
    if logo_field:
        try:
            import base64
            import mimetypes
            with logo_field.open("rb") as f:
                logo_bytes = f.read()
            mime = mimetypes.guess_type(logo_field.name)[0] or "image/png"
            logo_url = f"data:{mime};base64,{base64.b64encode(logo_bytes).decode()}"
        except Exception as exc:
            logo_error = f"{type(exc).__name__}: {exc}"
            logger.warning("factura_pdf: no se pudo leer el logo: %s", exc)
    else:
        logo_error = "La institución no tiene logo configurado en la base de datos."

    # Modo diagnóstico: solo en DEBUG y para superusuarios (A05 — info disclosure)
    from django.conf import settings as _settings
    if request.GET.get("debug") and _settings.DEBUG and request.user.is_superuser:
        from django.core.files.storage import default_storage
        info = [
            f"logo ConfiguracionInstitucion: {config_inst.logo.name if config_inst and config_inst.logo else '(vacío)'}",
            f"logo InstitucionEducativa: {factura.institucion.logo.name if factura.institucion.logo else '(vacío)'}",
            f"logo elegido: {logo_field.name if logo_field else '(ninguno)'}",
            f"storage: {type(default_storage).__name__}",
            f"existe en storage: {default_storage.exists(logo_field.name) if logo_field else 'N/A'}",
            f"logo cargado para el PDF: {'SÍ (' + str(len(logo_url)) + ' chars base64)' if logo_url else 'NO'}",
            f"error: {logo_error or '(ninguno)'}",
        ]
        return HttpResponse("\n".join(info), content_type="text/plain; charset=utf-8")

    # QR de verificación DIAN — generado como imagen PNG base64
    qr_b64 = ""
    if factura.qr:
        try:
            import base64
            import io
            import qrcode
            qr_img = qrcode.make(factura.qr)
            buf = io.BytesIO()
            qr_img.save(buf, format="PNG")
            qr_b64 = base64.b64encode(buf.getvalue()).decode()
        except Exception as exc:
            logger.warning("factura_pdf: no se pudo generar QR: %s", exc)

    try:
        html = render_to_string("facturacion_electronica/factura_pdf.html", {
            "factura": factura,
            "institucion": factura.institucion,
            "logo_url": logo_url,
            "qr_b64": qr_b64,
            "items": items,
            "customer_name": customer_name,
            "customer_doc": customer_doc,
            "customer_doc_type": customer_doc_type,
            "customer_email": customer_email,
            "customer_address": customer_address,
            "total": total,
        }, request=request)

        from weasyprint import HTML as WP_HTML
        pdf = WP_HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()
        filename = f"FEV_{factura.numero or factura.reference_code}.pdf"
        response = HttpResponse(pdf, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{filename}"'
        return response
    except Exception as exc:
        logger.error("factura_pdf error: %s", exc, exc_info=True)
        return HttpResponse(f"Error generando PDF: {exc}", status=500)


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
@permission_required("finanzas.change_institucioneducativa", raise_exception=True)
@require_POST
def reenviar_correo_factura(request, factura_id):
    """Reenvía el correo de notificación de la factura electrónica al estudiante y familiares."""
    institucion = _get_institucion(request)
    factura = get_object_or_404(FacturaElectronica, pk=factura_id, institucion=institucion)

    if factura.estado != FacturaElectronica.Estado.VALIDADA:
        messages.warning(request, "Solo se puede reenviar el correo de facturas validadas por la DIAN.")
        return redirect("facturacion_electronica:detalle_factura", factura_id=factura_id)

    try:
        from gestion_academica.tasks_notificaciones import notificar_factura_electronica
        notificar_factura_electronica.delay(factura.pk)
        messages.success(request, "Correo de factura electrónica encolado. Llegará en unos segundos.")
    except Exception as exc:
        logger.error("reenviar_correo_factura: error al encolar tarea: %s", exc)
        messages.error(request, "No se pudo encolar el correo. Verifica que el servicio de tareas esté activo.")

    return redirect("facturacion_electronica:detalle_factura", factura_id=factura_id)


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

    # Notificar al estudiante y familiares por correo
    from django.db import transaction as _tx
    from facturacion_electronica.tasks import _notificar_factura
    _tx.on_commit(lambda fid=factura.pk: _notificar_factura(fid))

    messages.success(
        request,
        f"✅ Factura electrónica emitida y validada (No. {factura.numero or factura.reference_code}). "
        f"Se notificará por correo al acudiente.",
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
