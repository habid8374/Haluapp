"""Tareas Celery del módulo de Facturación Electrónica (Modo B — automático)."""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)


def _notificar_factura(factura_id: int) -> None:
    """Encola el correo de notificación de factura (helper para evitar importación circular)."""
    try:
        from gestion_academica.tasks_notificaciones import notificar_factura_electronica
        notificar_factura_electronica.delay(factura_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("_notificar_factura: no se pudo encolar correo para factura %s: %s", factura_id, exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def emitir_factura_async(self, pago_id: int):
    """Emite la factura electrónica de un pago en segundo plano.

    Reintenta ante errores de comunicación. No reintenta si el módulo no está
    operativo (no tiene sentido reintentar una configuración faltante).
    """
    from finanzas.models import PagoRegistrado
    from .emision import emitir_para_pago
    from .services import FactusError, FactusNoConfigurado

    pago = PagoRegistrado.objects.filter(pk=pago_id).first()
    if not pago:
        logger.warning("emitir_factura_async: pago %s no existe.", pago_id)
        return {"ok": False, "motivo": "pago_inexistente"}

    try:
        factura = emitir_para_pago(pago)
        # Notificar al estudiante y familiares una vez validada
        from django.db import transaction
        transaction.on_commit(
            lambda fid=factura.pk: _notificar_factura(fid)
        )
        return {"ok": True, "factura_id": factura.pk, "numero": factura.numero}
    except FactusNoConfigurado as exc:
        logger.info("emitir_factura_async: módulo no operativo para pago %s: %s", pago_id, exc)
        return {"ok": False, "motivo": "no_operativo"}
    except FactusError as exc:
        logger.error("emitir_factura_async: error Factus pago %s: %s", pago_id, exc)
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def emitir_factura_cuenta_async(self, cuenta_id: int):
    """Emite la factura electrónica de una CUENTA (causación mensual) en segundo plano."""
    from finanzas.models import CuentaPorCobrarEstudiante
    from .emision import emitir_para_cuenta
    from .services import FactusError, FactusNoConfigurado

    cuenta = CuentaPorCobrarEstudiante.objects.filter(pk=cuenta_id).first()
    if not cuenta:
        return {"ok": False, "motivo": "cuenta_inexistente"}
    try:
        factura = emitir_para_cuenta(cuenta)
        from django.db import transaction
        transaction.on_commit(
            lambda fid=factura.pk: _notificar_factura(fid)
        )
        return {"ok": True, "factura_id": factura.pk, "numero": factura.numero}
    except FactusNoConfigurado as exc:
        logger.info("emitir_factura_cuenta_async: módulo no operativo cuenta %s: %s", cuenta_id, exc)
        return {"ok": False, "motivo": "no_operativo"}
    except FactusError as exc:
        logger.error("emitir_factura_cuenta_async: error Factus cuenta %s: %s", cuenta_id, exc)
        raise self.retry(exc=exc)


@shared_task
def emitir_facturas_masivas_async(cuenta_ids: list):
    """Encola la emisión de factura electrónica para un lote de cuentas (facturación masiva)."""
    for cid in cuenta_ids or []:
        emitir_factura_cuenta_async.delay(cid)
    return {"encoladas": len(cuenta_ids or [])}
