"""Integración e-learning con Finanzas (cuentas, acceso al aula, certificado)."""

from decimal import Decimal
import logging

from django.db import IntegrityError

from finanzas.models import CuentaPorCobrarEstudiante, default_fecha_vencimiento

logger = logging.getLogger(__name__)


def oferta_requiere_pago(curso) -> bool:
    if curso.precio is None or curso.precio <= Decimal("0"):
        return False
    return bool(curso.concepto_pago_asociado_id)


def obtener_cuenta_elearning(inscripcion):
    """Cuenta en Finanzas vinculada a la inscripción (FK o búsqueda por observaciones legacy)."""
    if inscripcion.cuenta_por_cobrar_id:
        return inscripcion.cuenta_por_cobrar
    curso = inscripcion.curso
    if not oferta_requiere_pago(curso):
        return None
    marker = f"inscripción id={inscripcion.pk}"
    return (
        CuentaPorCobrarEstudiante.objects.filter(
            estudiante=inscripcion.estudiante,
            observaciones_internas__icontains=marker,
        )
        .order_by("-pk")
        .first()
    )


def inscripcion_acceso_contenido_pagado(inscripcion) -> bool:
    """True si puede ver aula / rendir evaluación (oferta gratuita o cuenta saldada)."""
    if not oferta_requiere_pago(inscripcion.curso):
        return True
    cuenta = obtener_cuenta_elearning(inscripcion)
    if not cuenta:
        return False
    try:
        pendiente = cuenta.saldo_pendiente
    except Exception:
        pendiente = Decimal("0")
    return pendiente <= Decimal("0")


def registrar_cuenta_por_inscripcion_elearning(inscripcion):
    """
    Crea cuenta por cobrar y vincula la inscripción.
    Devuelve (éxito, mensaje_error_opcional).
    """
    curso = inscripcion.curso
    if inscripcion.cuenta_por_cobrar_id:
        return True, None
    existente = obtener_cuenta_elearning(inscripcion)
    if existente:
        inscripcion.cuenta_por_cobrar = existente
        inscripcion.save(update_fields=["cuenta_por_cobrar"])
        return True, None

    if curso.precio is None or curso.precio <= Decimal("0"):
        return True, None
    if not curso.concepto_pago_asociado_id:
        return False, (
            f"La oferta «{curso.nombre}» tiene precio pero no tiene concepto de pago asociado; "
            "configúrelo en la ficha de la oferta para generar la cuenta en Finanzas."
        )
    try:
        cuenta = CuentaPorCobrarEstudiante.objects.create(
            estudiante=inscripcion.estudiante,
            concepto_pago=curso.concepto_pago_asociado,
            monto_asignado=curso.precio,
            fecha_vencimiento_especifica=default_fecha_vencimiento(),
            observaciones_internas=(
                f"E-learning — inscripción id={inscripcion.pk} — {curso.nombre}"
            ),
            institucion=inscripcion.estudiante.institucion,
        )
    except IntegrityError as exc:
        logger.warning("Cuenta e-learning no creada (integridad): %s", exc)
        return False, (
            "No se pudo crear la cuenta en Finanzas: posible duplicado del mismo concepto "
            "y periodo para este estudiante. Revise cartera o use un concepto distinto por oferta."
        )
    inscripcion.cuenta_por_cobrar = cuenta
    inscripcion.save(update_fields=["cuenta_por_cobrar"])
    return True, None
