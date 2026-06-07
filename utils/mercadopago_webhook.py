"""
Validación de notificaciones webhook de Mercado Pago (cabecera x-signature).

Referencia: https://www.mercadopago.com/developers/en/docs/your-integrations/notifications/webhooks
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Optional

from django.http import HttpRequest

logger = logging.getLogger(__name__)


def parse_x_signature_header(x_signature: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """Extrae ts y v1 (hex HMAC esperado) del header x-signature."""
    if not x_signature:
        return None, None
    ts_val, v1_val = None, None
    for part in x_signature.split(","):
        part = part.strip()
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key, value = key.strip(), value.strip()
        if key == "ts":
            ts_val = value
        elif key == "v1":
            v1_val = value
    return ts_val, v1_val


def resolve_notification_data_id(request: HttpRequest, payment_id_body: str) -> str:
    """
    Mercado Pago puede enviar data.id en query string; si no, se usa el id del JSON.
    """
    q = request.GET.get("data.id")
    if q is not None and str(q).strip() != "":
        return str(q).strip()
    return str(payment_id_body).strip()


def verify_mercadopago_webhook_signature(
    secret: Optional[str],
    *,
    data_id: str,
    x_request_id: Optional[str],
    x_signature_header: Optional[str],
) -> bool:
    """
    Sin secret no se puede validar la firma: devuelve False (rechazar la notificación).
    Con secret configurado, exige cabeceras y HMAC válido (comparación en tiempo constante).
    """
    effective = (secret or "").strip()
    if not effective:
        logger.warning(
            "Mercado Pago webhook: mp_webhook_secret vacío para la institución; "
            "se rechaza la notificación (no se valida x-signature)."
        )
        return False
    if not x_signature_header or not x_request_id:
        logger.warning("Mercado Pago webhook: x-signature o x-request-id ausentes con secret configurado.")
        return False
    ts, v1 = parse_x_signature_header(x_signature_header)
    if not ts or not v1:
        return False
    manifest = f"id:{data_id};request-id:{x_request_id};ts:{ts};"
    digest = hmac.new(effective.encode(), msg=manifest.encode(), digestmod=hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest.lower(), v1.lower())
