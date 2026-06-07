"""Helpers para leer credenciales solo desde InstitucionEducativa (multi-tenant)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from finanzas.models import InstitucionEducativa


def google_api_key(institucion: Optional["InstitucionEducativa"]) -> Optional[str]:
    """API key Gemini/Google para la institución; None si no está configurada."""
    if not institucion:
        return None
    key = (getattr(institucion, "google_api_key", None) or "").strip()
    return key or None


def mp_webhook_secret(institucion: Optional["InstitucionEducativa"]) -> Optional[str]:
    """Secret de firma de webhooks Mercado Pago para la institución."""
    if not institucion:
        return None
    secret = (getattr(institucion, "mp_webhook_secret", None) or "").strip()
    return secret or None
