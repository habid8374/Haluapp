"""Lógica central de emisión de factura electrónica para un pago.

Usada por:
  * el botón manual (views.emitir_factura)
  * la tarea Celery de emisión automática (tasks.emitir_factura_async)

Mantener aquí la lógica evita duplicación entre el Modo A (manual) y el Modo B (auto).
"""
import logging
from decimal import Decimal

from django.utils import timezone

from .models import ConfiguracionFactus, FacturaElectronica
from .payload import construir_payload_desde_pago, construir_payload_nota
from .services import FactusClient, FactusError, FactusNoConfigurado

logger = logging.getLogger(__name__)


def extraer_datos_respuesta(respuesta: dict) -> dict:
    """Extrae número/CUFE/PDF/QR de la respuesta de Factus (esquema v2 validado)."""
    data = (respuesta or {}).get("data", respuesta) or {}
    links = data.get("links") or {}

    # public_url a veces viene SIN el hash del documento (notas en sandbox):
    # termina en '.../credit-notes/' o '.../bills/'. En ese caso lo descartamos
    # y el visor será el enlace QR de la DIAN (que siempre funciona).
    public_url = (links.get("public_url") or "").rstrip()
    if public_url.rstrip("/").endswith(("credit-notes", "debit-notes", "bills")):
        public_url = ""

    return {
        "numero": data.get("number") or "",
        # Facturas usan CUFE; notas usan CUDE. Guardamos en el mismo campo.
        "cufe": data.get("cufe") or data.get("cude") or "",
        "url_pdf": public_url,
        "url_xml": links.get("xml") or "",
        "qr": links.get("qr") or "",
    }


def emitir_para_pago(pago) -> FacturaElectronica:
    """Emite (o recupera) la factura electrónica de un ``PagoRegistrado``.

    Idempotente: una factura por pago (reference_code = PAGO-<id>).
    Lanza FactusNoConfigurado / FactusError ante problemas (el llamador decide
    cómo notificar). En error, deja la ``FacturaElectronica`` en estado ERROR.
    """
    institucion = pago.institucion
    config = ConfiguracionFactus.objects.filter(institucion=institucion).first()
    if not config or not config.operativo:
        raise FactusNoConfigurado(
            "El módulo de facturación electrónica no está operativo (activo + credenciales + rango)."
        )

    reference_code = f"PAGO-{pago.pk}"
    factura, created = FacturaElectronica.objects.get_or_create(
        institucion=institucion,
        reference_code=reference_code,
        defaults={
            "pago": pago,
            "estudiante": pago.estudiante,
            "ambiente": config.ambiente,
        },
    )
    if not created and factura.estado == FacturaElectronica.Estado.VALIDADA:
        return factura  # ya emitida

    payload = construir_payload_desde_pago(factura, config)
    factura.json_enviado = payload
    factura.save(update_fields=["json_enviado"])

    try:
        respuesta = FactusClient(config).crear_factura(payload)
    except (FactusError, FactusNoConfigurado) as exc:
        factura.estado = FacturaElectronica.Estado.ERROR
        factura.mensaje = str(exc)[:2000]
        factura.save(update_fields=["estado", "mensaje"])
        logger.error("Factura electrónica pago %s falló: %s", pago.pk, exc)
        raise

    datos = extraer_datos_respuesta(respuesta)
    factura.marcar_validada(respuesta=respuesta, **datos)

    ConfiguracionFactus.objects.filter(pk=config.pk).update(
        facturas_emitidas=config.facturas_emitidas + 1
    )
    logger.info("Factura electrónica emitida pago=%s numero=%s", pago.pk, datos["numero"])
    return factura


def emitir_para_cuenta(cuenta) -> FacturaElectronica:
    """Emite la factura electrónica al CAUSAR el cobro (mensual), sin requerir pago.

    El titular es el acudiente responsable del estudiante (lo resuelve el payload).
    Idempotente: una factura por cuenta (reference_code = CUENTA-<id>).
    """
    institucion = cuenta.institucion
    config = ConfiguracionFactus.objects.filter(institucion=institucion).first()
    if not config or not config.operativo:
        raise FactusNoConfigurado("El módulo de facturación electrónica no está operativo.")

    reference_code = f"CUENTA-{cuenta.pk}"
    factura, created = FacturaElectronica.objects.get_or_create(
        institucion=institucion,
        reference_code=reference_code,
        defaults={
            "cuenta": cuenta,
            "estudiante": cuenta.estudiante,
            "ambiente": config.ambiente,
        },
    )
    if not created and factura.estado == FacturaElectronica.Estado.VALIDADA:
        return factura

    payload = construir_payload_desde_pago(factura, config)
    factura.json_enviado = payload
    factura.save(update_fields=["json_enviado"])

    try:
        respuesta = FactusClient(config).crear_factura(payload)
    except (FactusError, FactusNoConfigurado) as exc:
        factura.estado = FacturaElectronica.Estado.ERROR
        factura.mensaje = str(exc)[:2000]
        factura.save(update_fields=["estado", "mensaje"])
        raise

    datos = extraer_datos_respuesta(respuesta)
    factura.marcar_validada(respuesta=respuesta, **datos)
    ConfiguracionFactus.objects.filter(pk=config.pk).update(
        facturas_emitidas=config.facturas_emitidas + 1
    )
    return factura


def emitir_nota(factura_origen, tipo: str, correction_code: str, monto=None) -> FacturaElectronica:
    """Emite una NOTA CRÉDITO o DÉBITO sobre una factura ya validada.

    ``tipo`` = FacturaElectronica.Tipo.NOTA_CREDITO / NOTA_DEBITO.
    ``correction_code`` = código de corrección DIAN (ver payload.CORRECCION_*).
    ``monto`` = (solo NOTA DÉBITO) valor del cargo adicional. Para NOTA CRÉDITO
    se deja None (anula/acredita el total de la factura).
    """
    institucion = factura_origen.institucion
    config = ConfiguracionFactus.objects.filter(institucion=institucion).first()
    if not config or not config.operativo:
        raise FactusNoConfigurado("El módulo de facturación electrónica no está operativo.")

    if factura_origen.tipo != FacturaElectronica.Tipo.FACTURA:
        raise FactusError("Solo se pueden emitir notas sobre una factura de venta.")
    if factura_origen.estado != FacturaElectronica.Estado.VALIDADA or not factura_origen.numero:
        raise FactusError("La factura de origen debe estar validada antes de emitir una nota.")

    if tipo == FacturaElectronica.Tipo.NOTA_CREDITO:
        rango = config.numbering_range_id_nota_credito
        metodo = "crear_nota_credito"
        prefijo = "NC"
    else:
        rango = config.numbering_range_id_nota_debito
        metodo = "crear_nota_debito"
        prefijo = "ND"
    if not rango:
        raise FactusNoConfigurado(
            f"Falta configurar el rango de numeración de {'Nota Crédito' if prefijo == 'NC' else 'Nota Débito'}."
        )

    n = factura_origen.notas.filter(tipo=tipo).count() + 1
    reference_code = f"{prefijo}-{factura_origen.pk}-{n}"

    nota = FacturaElectronica.objects.create(
        institucion=institucion,
        tipo=tipo,
        documento_origen=factura_origen,
        pago=factura_origen.pago,
        estudiante=factura_origen.estudiante,
        ambiente=config.ambiente,
        reference_code=reference_code,
    )
    payload = construir_payload_nota(nota, factura_origen, rango, correction_code, monto=monto)
    nota.json_enviado = payload
    nota.save(update_fields=["json_enviado"])

    client = FactusClient(config)
    try:
        respuesta = getattr(client, metodo)(payload)
    except (FactusError, FactusNoConfigurado) as exc:
        nota.estado = FacturaElectronica.Estado.ERROR
        nota.mensaje = str(exc)[:2000]
        nota.save(update_fields=["estado", "mensaje"])
        logger.error("Nota %s sobre factura %s falló: %s", prefijo, factura_origen.numero, exc)
        raise

    datos = extraer_datos_respuesta(respuesta)
    nota.marcar_validada(respuesta=respuesta, **datos)
    ConfiguracionFactus.objects.filter(pk=config.pk).update(
        facturas_emitidas=config.facturas_emitidas + 1
    )

    # ── Efecto contable inmediato ──
    try:
        _aplicar_efecto_contable(nota, monto)
    except Exception as exc:  # la nota ya está validada en DIAN; no la revertimos
        logger.error("Nota %s validada pero falló el ajuste contable: %s", nota.numero, exc, exc_info=True)
        nota.mensaje = (nota.mensaje + " | AVISO: ajuste contable falló, revisar manualmente.").strip()
        nota.save(update_fields=["mensaje"])

    logger.info("Nota %s emitida numero=%s sobre factura=%s", prefijo, datos["numero"], factura_origen.numero)
    return nota


def _aplicar_efecto_contable(nota, monto):
    """Sincroniza la contabilidad tras validar una nota.

    - NOTA CRÉDITO: anula el pago de origen (deja de contar en el saldo) → la
      cuenta vuelve a quedar pendiente/vencida.
    - NOTA DÉBITO: aumenta el monto_asignado de la cuenta de origen por ``monto``
      → genera saldo pendiente adicional.
    """
    origen = nota.documento_origen
    pago = origen.pago if origen else None
    if not pago:
        logger.warning("Nota %s sin pago de origen: no se aplica efecto contable.", nota.numero)
        return

    if nota.tipo == FacturaElectronica.Tipo.NOTA_CREDITO:
        if not pago.anulado:
            pago.anulado = True
            pago.anulado_en = timezone.now()
            pago.anulado_motivo = f"Nota crédito {nota.numero}"
            pago.save()  # el signal recalcula la cuenta (vuelve a pendiente)
            logger.info("Pago %s ANULADO por nota crédito %s", pago.pk, nota.numero)

    elif nota.tipo == FacturaElectronica.Tipo.NOTA_DEBITO and monto:
        cuenta = pago.cuenta
        if cuenta:
            cuenta.monto_asignado = (cuenta.monto_asignado or Decimal("0")) + Decimal(str(monto))
            cuenta.save()  # recalcula saldo/estado → queda saldo pendiente adicional
            logger.info("Cuenta %s aumentada en %s por nota débito %s", cuenta.pk, monto, nota.numero)


def disparar_emision_automatica(pago):
    """Hook seguro para el flujo de pagos (efectivo / Mercado Pago).

    No hace NADA salvo que la institución tenga el módulo operativo Y la
    emisión automática activada. Encola la tarea Celery (Modo B).
    Nunca lanza excepción (no debe romper el registro del pago).
    """
    try:
        config = ConfiguracionFactus.objects.filter(institucion=pago.institucion).first()
        if not (config and config.operativo and config.emision_automatica):
            return
        from .tasks import emitir_factura_async
        emitir_factura_async.delay(pago.pk)
    except Exception as exc:  # nunca romper el flujo de pago
        logger.warning("No se pudo disparar emisión automática para pago %s: %s", getattr(pago, "pk", "?"), exc)
