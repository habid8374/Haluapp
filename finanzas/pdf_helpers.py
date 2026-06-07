"""Helpers para los documentos PDF de finanzas (Orden de Pago / recibos).

Funciones reutilizables para:
  * Generar un código QR como data-URI base64 (embebible en <img> para xhtml2pdf).
  * Convertir un monto numérico a letras en español (formato moneda colombiana).

Ambas son tolerantes a fallos: si una dependencia opcional no está disponible,
devuelven None / cadena vacía en vez de romper la generación del PDF.
"""
from __future__ import annotations

import base64
import logging
from decimal import Decimal
from io import BytesIO

logger = logging.getLogger(__name__)


def generar_qr_base64(data: str) -> str | None:
    """Devuelve un código QR de ``data`` como data-URI PNG base64.

    Listo para usar en una plantilla: ``<img src="{{ qr }}">``.
    Devuelve None si la librería ``qrcode`` no está disponible o falla.
    """
    if not data:
        return None
    try:
        import qrcode

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        b64 = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/png;base64,{b64}"
    except Exception as exc:  # pragma: no cover - dependencia opcional
        logger.warning("No se pudo generar el QR de pago: %s", exc)
        return None


def valor_en_letras(monto, moneda: str = "PESOS M/CTE") -> str:
    """Convierte un monto a letras en español. Ej: 465926 -> 'CUATROCIENTOS ...'.

    Devuelve cadena vacía si ``num2words`` no está disponible.
    """
    if monto is None:
        return ""
    try:
        from num2words import num2words

        # Redondeamos a entero (los volantes colombianos suelen no usar centavos)
        entero = int(Decimal(str(monto)).quantize(Decimal("1")))
        palabras = num2words(entero, lang="es")
        return f"{palabras.upper()} {moneda}"
    except Exception as exc:  # pragma: no cover - dependencia opcional
        logger.warning("No se pudo convertir el monto a letras: %s", exc)
        return ""
