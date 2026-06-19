from urllib.parse import urlparse
from django import template

register = template.Library()


@register.filter
def safe_url(value):
    """Devuelve True solo si la URL usa http:// o https:// con hostname válido.

    Previene que valores como 'javascript:...' o 'data:...' lleguen a
    atributos href en el template (A03 OWASP — XSS vía protocolo javascript:).
    """
    if not value or not isinstance(value, str):
        return False
    try:
        p = urlparse(value.strip())
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False
