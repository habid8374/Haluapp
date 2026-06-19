# facturacion_electronica/pdf_utils.py
"""
Utilidades para generar la representación gráfica (PDF) de una factura
electrónica y empaquetar el documento (PDF + XML) en un ZIP descargable.

Reutilizable desde vistas (con request) y desde tareas en segundo plano
(sin request, p. ej. el envío del correo al acudiente).
"""
import base64
import io
import logging
import mimetypes

from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def construir_contexto_pdf(factura) -> dict:
    """Arma el contexto de la plantilla del PDF a partir de la factura.

    No depende de ``request``: el logo y el QR se incrustan como data URI /
    base64 leyendo directo del storage, igual que la vista ``factura_pdf``.
    """
    enviado = factura.json_enviado or {}
    items_raw = enviado.get("items", []) or []
    customer = enviado.get("customer", {}) or {}

    items = []
    total = 0
    for it in items_raw:
        precio = float(it.get("price", 0))
        qty = float(it.get("quantity", 1))
        subtotal = precio * qty
        total += subtotal
        items.append({**it, "total": subtotal})

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

    # Logo del colegio (ConfiguracionInstitucion con fallback a InstitucionEducativa)
    config_inst = getattr(factura.institucion, "configuracioninstitucion", None)
    logo_field = (config_inst.logo if config_inst and config_inst.logo else None) or (
        factura.institucion.logo if factura.institucion.logo else None
    )
    logo_url = ""
    if logo_field:
        try:
            with logo_field.open("rb") as f:
                logo_bytes = f.read()
            mime = mimetypes.guess_type(logo_field.name)[0] or "image/png"
            logo_url = f"data:{mime};base64,{base64.b64encode(logo_bytes).decode()}"
        except Exception as exc:
            logger.warning("construir_contexto_pdf: no se pudo leer el logo: %s", exc)

    # QR de verificación DIAN como imagen PNG base64
    qr_b64 = ""
    if factura.qr:
        try:
            import qrcode
            qr_img = qrcode.make(factura.qr)
            buf = io.BytesIO()
            qr_img.save(buf, format="PNG")
            qr_b64 = base64.b64encode(buf.getvalue()).decode()
        except Exception as exc:
            logger.warning("construir_contexto_pdf: no se pudo generar QR: %s", exc)

    return {
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
    }


def generar_pdf_factura(factura, base_url: str = None) -> bytes:
    """Renderiza el PDF (representación gráfica Halu) de la factura.

    Devuelve los bytes del PDF. Funciona sin ``request``.
    """
    contexto = construir_contexto_pdf(factura)
    html = render_to_string("facturacion_electronica/factura_pdf.html", contexto)
    from weasyprint import HTML as WP_HTML
    if base_url:
        return WP_HTML(string=html, base_url=base_url).write_pdf()
    return WP_HTML(string=html).write_pdf()


def descargar_xml_factura(factura, timeout: int = 20) -> bytes:
    """Descarga el XML firmado de la DIAN desde ``factura.url_xml``.

    Devuelve los bytes del XML, o ``None`` si no hay URL o falla la descarga
    (p. ej. en sandbox cuando Factus no expone el XML del documento).
    """
    url = (factura.url_xml or "").strip()
    if not url:
        return None
    try:
        import requests
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.content
    except Exception as exc:
        logger.warning(
            "descargar_xml_factura: no se pudo descargar el XML de la factura %s (%s): %s",
            factura.pk, url, exc,
        )
        return None


def construir_zip_factura(factura, base_url: str = None) -> tuple:
    """Empaqueta el PDF (Halu) y el XML (DIAN) de la factura en un ZIP.

    Devuelve ``(nombre_zip, bytes_zip, incluye_xml)``. El PDF siempre se
    incluye; el XML solo si está disponible (``incluye_xml`` lo indica).
    """
    import zipfile

    base_nombre = f"FEV_{factura.numero or factura.reference_code}".replace("/", "-")

    pdf_bytes = generar_pdf_factura(factura, base_url=base_url)
    xml_bytes = descargar_xml_factura(factura)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{base_nombre}.pdf", pdf_bytes)
        if xml_bytes:
            zf.writestr(f"{base_nombre}.xml", xml_bytes)
    buf.seek(0)
    return f"{base_nombre}.zip", buf.getvalue(), bool(xml_bytes)
