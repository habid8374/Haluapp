from django.template import Library
from django.utils.safestring import mark_safe
import bleach

register = Library()

@register.filter
def get_item(dictionary, key):
    if hasattr(dictionary, 'get'):
        return dictionary.get(key)
    return None


# Etiquetas HTML permitidas en contenido educativo (enunciados, logros, etc.)
_SAFE_TAGS = ['b', 'i', 'u', 'em', 'strong', 'p', 'br', 'ul', 'ol', 'li', 'sub', 'sup']
_SAFE_ATTRS: dict = {}  # sin atributos — elimina href, style, on*, etc.

@register.filter(name='safe_html')
def safe_html(value):
    """Renderiza HTML permitiendo solo etiquetas seguras. Elimina <script>, on*, href, style."""
    if not value:
        return ''
    cleaned = bleach.clean(str(value), tags=_SAFE_TAGS, attributes=_SAFE_ATTRS, strip=True)
    return mark_safe(cleaned)