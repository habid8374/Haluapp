"""Código de barras GS1-128 para recibos de "recaudo referenciado"
(el mecanismo que usan Bancolombia y otros bancos colombianos para que un
acudiente pague una factura en efectivo en cualquier oficina, escaneando
un código de barras). Estándar GS1 Colombia + Asobancaria, no exclusivo
de un banco.

Estructura codificada (identificadores de aplicación GS1):
  (415) código de convenio — asignado por el banco a la institución, fijo 13 dígitos.
  (8020) referencia de pago — generada por esta plataforma (ConsecutivoDocumento).
  (3900) valor a pagar en COP, sin decimales.
  (96) fecha límite de pago, AAAAMMDD.

IMPORTANTE: (8020) y (3900) son de longitud variable según el estándar
GS1 general, así que van seguidos del carácter FNC1 (separador de grupo)
cuando no son el último campo. (96) es de longitud fija (8) y va al final,
sin separador. Antes de imprimir/enviar recibos reales a padres, hay que
validar el primer código generado directamente con el banco que emitió el
convenio — cada banco puede tener variaciones menores sobre este estándar
general.
"""
import io

FNC1 = '\xf1'


def construir_datos_gs1(codigo_convenio, referencia, monto_cop, fecha_limite):
    """Arma la cadena de datos (sin el FNC1 inicial obligatorio — eso lo
    agrega la clase Gs1_128 de python-barcode al codificar)."""
    codigo_convenio = str(codigo_convenio).strip()
    referencia = str(referencia).strip()
    valor = str(int(monto_cop))
    return (
        f"415{codigo_convenio}"
        f"8020{referencia}{FNC1}"
        f"3900{valor}{FNC1}"
        f"96{fecha_limite.strftime('%Y%m%d')}"
    )


def generar_imagen_barcode_png(datos: str) -> bytes:
    """Renderiza el código GS1-128 como PNG (bytes), listo para incrustar
    en un PDF como data URI base64."""
    from barcode import get_barcode_class
    from barcode.writer import ImageWriter

    Gs1_128 = get_barcode_class('gs1_128')
    buffer = io.BytesIO()
    Gs1_128(datos, writer=ImageWriter()).write(buffer, options={'write_text': False})
    return buffer.getvalue()
