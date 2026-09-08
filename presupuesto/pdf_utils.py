"""Helpers para los documentos PDF de Presupuesto FSE (CDP, RP, Obligación,
Orden de Pago, Comprobante de Egreso, Reportes).

Cada app de la plataforma mantiene su propia copia de `_link_callback_pdf`
en vez de importarla entre apps (mismo criterio ya usado en `piar` y
`gestion_academica`) — es la única pieza sensible a seguridad (resuelve
rutas de archivos para xhtml2pdf, con protección contra path traversal).
`valor_en_letras` es una utilidad pura sin dependencias de la app, se
duplica aquí por el mismo criterio de aislamiento entre apps.
"""
import logging
import os
from decimal import Decimal

from django.conf import settings

logger = logging.getLogger(__name__)


def link_callback_pdf(uri, rel):
    media_url = getattr(settings, 'MEDIA_URL', '') or ''
    media_root = getattr(settings, 'MEDIA_ROOT', None)
    if media_url and media_root and uri.startswith(media_url):
        path = os.path.join(media_root, uri.replace(media_url, "", 1))
        allowed_root = os.path.realpath(media_root)
    elif uri.startswith(settings.STATIC_URL):
        path = os.path.join(settings.STATICFILES_DIRS[0], uri.replace(settings.STATIC_URL, "", 1))
        allowed_root = os.path.realpath(settings.STATICFILES_DIRS[0])
    else:
        return uri
    real_path = os.path.realpath(path)
    if not real_path.startswith(allowed_root + os.sep) and real_path != allowed_root:
        logger.warning("link_callback_pdf: path traversal bloqueado para URI: %s", uri)
        return None
    if not os.path.isfile(real_path):
        return None
    return real_path


def valor_en_letras(monto, moneda: str = "PESOS M/CTE") -> str:
    """Convierte un monto a letras en español. Devuelve cadena vacía si
    `num2words` no está disponible."""
    if monto is None:
        return ""
    try:
        from num2words import num2words

        entero = int(Decimal(str(monto)).quantize(Decimal("1")))
        palabras = num2words(entero, lang="es")
        return f"{palabras.upper()} {moneda}"
    except Exception as exc:  # pragma: no cover - dependencia opcional
        logger.warning("No se pudo convertir el monto a letras: %s", exc)
        return ""
