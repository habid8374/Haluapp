"""Construcción del JSON de factura para Factus — ESQUEMA VALIDADO EN SANDBOX.

Probado contra https://api-sandbox.factus.com.co/v2/bills/validate (status 201).

Notas clave del esquema v2:
  * ``payment_details`` es un ARRAY: [{payment_form, payment_method_code, amount}]
  * Cliente usa ``identification_document_code`` con CÓDIGOS DIAN (13=CC, 31=NIT…)
  * Ítems requieren ``unit_measure_code``, ``standard_code`` y ``taxes``:[{code, rate}]
  * Educación formal: EXCLUIDA de IVA → is_excluded=1 + taxes [{code:'01', rate:'0.00'}]
"""
from __future__ import annotations

from datetime import date, timedelta

# ── Códigos DIAN de documento de identidad ──
DOC_CC = "13"   # Cédula de ciudadanía
DOC_NIT = "31"
DOC_TI = "12"
DOC_CE = "22"
DOC_PASAPORTE = "41"
DOC_NIT_OTRO_PAIS = "50"
DOC_CONSUMIDOR_FINAL = "13"  # por defecto CC

# ── Otros códigos (verificados en sandbox) ──
UNIT_MEASURE_CODE = "94"        # 94 = Unidad (servicio)
STANDARD_CODE = "999"           # Estándar de adopción del contribuyente
LEGAL_ORG_NATURAL = "2"         # Persona natural
LEGAL_ORG_JURIDICA = "1"        # Persona jurídica
CUSTOMER_TRIBUTE_NO_IVA = "21"  # No responsable de IVA
PRODUCT_TRIBUTE_IVA = "01"      # IVA (con rate 0.00 para excluido)

# Mapa método de pago interno -> código DIAN (verificado: 10=efectivo)
MAPA_METODO_PAGO = {
    "EFECTIVO": "10",
    "TRANSFERENCIA": "42",
    "TARJETA_DEBITO": "49",
    "TARJETA_CREDITO": "48",
    "PSE": "47",
    "MERCADO_PAGO": "48",
    "OTRO": "10",
}


def _payment_method_code(metodo_pago: str | None) -> str:
    return MAPA_METODO_PAGO.get((metodo_pago or "").upper(), "10")


# Mapa tipo de documento interno (modelo) -> código DIAN
MAPA_TIPO_DOC_DIAN = {
    "CC": "13", "TI": "12", "CE": "22", "PA": "41", "RC": "11", "NIT": "31", "OT": "13",
}


def _titular_factura(estudiante):
    """Devuelve los datos del ADQUIRIENTE (titular) de la factura.

    Prioridad: acudiente_responsable → primer familiar → el propio estudiante.
    Retorna un dict con: identification, names, email, address, phone, doc_code.
    """
    familiar = None
    if estudiante:
        familiar = getattr(estudiante, "acudiente_responsable", None)
        if not familiar:
            familiar = estudiante.familiares.first()

    if familiar:
        u = familiar.usuario
        return {
            "identification": str(familiar.documento_identidad or "222222222222"),
            "names": (u.get_full_name() if u else "") or "Acudiente",
            "email": (u.email if u else "") or "sincorreo@ejemplo.com",
            "address": familiar.direccion or "N/A",
            "phone": familiar.telefono or "",
            "doc_code": MAPA_TIPO_DOC_DIAN.get((familiar.tipo_documento or "CC").upper(), DOC_CC),
        }

    # Fallback: el estudiante (o consumidor final)
    if estudiante and estudiante.usuario:
        return {
            "identification": str(getattr(estudiante, "documento_identidad", None) or "222222222222"),
            "names": estudiante.usuario.get_full_name() or "Consumidor Final",
            "email": estudiante.usuario.email or "sincorreo@ejemplo.com",
            "address": getattr(estudiante, "direccion", "") or "N/A",
            "phone": "",
            "doc_code": MAPA_TIPO_DOC_DIAN.get((getattr(estudiante, "tipo_documento", None) or "CC").upper(), DOC_CC),
        }
    return {
        "identification": "222222222222", "names": "Consumidor Final",
        "email": "sincorreo@ejemplo.com", "address": "N/A", "phone": "", "doc_code": DOC_CC,
    }


def construir_payload_desde_pago(factura, config) -> dict:
    """Arma el JSON para POST /v2/bills/validate desde la factura interna.

    Funciona en dos modos:
      * Desde un PAGO (factura.pago): se factura el valor pagado.
      * Desde una CUENTA (factura.cuenta, sin pago): facturación al CAUSAR el
        cobro mensual (se factura el monto asignado de la cuenta).
    """
    pago = factura.pago
    cuenta = (pago.cuenta if pago else None) or factura.cuenta
    estudiante = factura.estudiante or (pago.estudiante if pago else None) or (cuenta.estudiante if cuenta else None)
    institucion = factura.institucion

    if pago:
        valor = float(pago.valor_pagado)
        metodo_code = _payment_method_code(getattr(pago, "metodo_pago", None))
        forma_pago = "1"   # contado — el dinero ya fue recibido
    else:
        valor = float(cuenta.monto_asignado) if cuenta and cuenta.monto_asignado else 0.0
        metodo_code = "10"
        forma_pago = "2"   # crédito — se factura al causar el cobro; aún no se ha cobrado
    concepto = (
        cuenta.concepto_pago.nombre_concepto
        if cuenta and cuenta.concepto_pago else "Servicio educativo"
    )

    # ── Cliente / Adquiriente = ACUDIENTE responsable (no el estudiante) ──
    titular = _titular_factura(estudiante)
    customer = {
        "identification": titular["identification"],
        "dv": "",
        "company": "",
        "trade_name": "",
        "names": titular["names"],
        "address": titular["address"] or (getattr(institucion, "direccion", "") or "N/A"),
        "email": titular["email"],
        "phone": titular["phone"] or (getattr(institucion, "telefono", "") or ""),
        "legal_organization_id": LEGAL_ORG_NATURAL,
        "tribute_id": CUSTOMER_TRIBUTE_NO_IVA,
        "identification_document_id": "3",
        "identification_document_code": titular["doc_code"],
        "municipality_id": _municipio_id(institucion),
    }

    # ── Vencimiento (contado) ──
    vence = (
        cuenta.fecha_vencimiento_especifica
        if cuenta and cuenta.fecha_vencimiento_especifica
        else date.today() + timedelta(days=30)
    )

    # ── Ítem: servicio educativo EXCLUIDO de IVA ──
    item = {
        "code_reference": str((cuenta.concepto_pago_id if cuenta else "EDU") or "EDU"),
        "name": concepto[:120],
        "quantity": 1,
        "discount_rate": 0,
        "price": valor,
        "tax_rate": "0.00",
        "unit_measure_id": 70,
        "unit_measure_code": UNIT_MEASURE_CODE,
        "standard_code_id": 1,
        "standard_code": STANDARD_CODE,
        "is_excluded": 1,
        "tribute_id": 1,
        "taxes": [{"code": PRODUCT_TRIBUTE_IVA, "rate": "0.00"}],
    }

    payload = {
        "numbering_range_id": config.numbering_range_id,
        "reference_code": factura.reference_code,
        "observation": f"{'Pago de' if pago else 'Cobro de'} {concepto}",
        "payment_form": forma_pago,   # "1"=contado (pago ya recibido) / "2"=crédito (por cobrar)
        "payment_due_date": vence.strftime("%Y-%m-%d"),
        "payment_method_code": metodo_code,
        "operation_type": "10",       # 10 = estándar
        "send_email": True,           # Factus envía PDF + XML al correo del acudiente
        "payment_details": [
            {"payment_form": forma_pago, "payment_method_code": metodo_code, "amount": valor},
        ],
        "customer": customer,
        "items": [item],
    }
    return payload


def _municipio_id(institucion) -> str:
    """ID de municipio DIAN. Por defecto Bogotá (980). TODO: mapear por ciudad real."""
    return str(getattr(institucion, "municipio_dane_id", None) or "980")


# ── Códigos de corrección DIAN ──
CORRECCION_NOTA_CREDITO = {
    "1": "Devolución parcial de bienes o servicios",
    "2": "Anulación de la factura",
    "3": "Rebaja o descuento total o parcial",
    "4": "Ajuste de precio",
    "5": "Otros",
}
CORRECCION_NOTA_DEBITO = {
    "1": "Intereses",
    "2": "Gastos por cobrar",
    "3": "Cambio del valor",
    "4": "Otros",
}


def construir_payload_nota(factura_nota, factura_origen, numbering_range_id, correction_code: str, monto=None) -> dict:
    """Arma el JSON de una nota crédito/débito a partir de la factura de origen.

    - Si ``monto`` es None: reutiliza los ítems completos de la factura original
      (caso típico de NOTA CRÉDITO total / anulación).
    - Si ``monto`` viene dado: arma un único ítem por ese valor (caso típico de
      NOTA DÉBITO: cargo adicional como interés/mora).
    """
    base = factura_origen.json_enviado or {}
    customer = base.get("customer", {})
    metodo_code = (base.get("payment_method_code") or "10")

    if monto is not None:
        items = [{
            "code_reference": "AJUSTE",
            "name": factura_nota.get_tipo_display(),
            "quantity": 1,
            "discount_rate": 0,
            "price": float(monto),
            "tax_rate": "0.00",
            "unit_measure_id": 70,
            "unit_measure_code": UNIT_MEASURE_CODE,
            "standard_code_id": 1,
            "standard_code": STANDARD_CODE,
            "is_excluded": 1,
            "tribute_id": 1,
            "taxes": [{"code": PRODUCT_TRIBUTE_IVA, "rate": "0.00"}],
        }]
        total = float(monto)
    else:
        items = base.get("items", [])
        total = sum(float(it.get("price", 0)) * float(it.get("quantity", 1)) for it in items) or 0.0

    return {
        "numbering_range_id": numbering_range_id,
        "reference_code": factura_nota.reference_code,
        "bill_number": factura_origen.numero,
        "correction_concept_code": str(correction_code),
        "observation": f"{factura_nota.get_tipo_display()} sobre {factura_origen.numero}",
        "send_email": True,           # Factus envía PDF + XML al correo del acudiente
        "payment_details": [
            {"payment_form": "1", "payment_method_code": metodo_code, "amount": total},
        ],
        "customer": customer,
        "items": items,
    }
