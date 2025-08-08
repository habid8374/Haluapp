from django.template import Library

register = Library()

@register.filter
def get_item(dictionary, key):
    """
    Permite acceder a un valor de un diccionario usando una variable como clave.
    Uso en la plantilla: {{ mi_diccionario|get_item:mi_variable_de_clave }}
    """
    if hasattr(dictionary, 'get'):
        return dictionary.get(key)
    return None