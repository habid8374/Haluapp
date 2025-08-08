# en gestion_academica/templatetags/horario_filters.py

from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Permite acceder a los valores de un diccionario usando una variable como clave.
    Versión corregida para manejar el caso en que el 'dictionary' sea None.
    """
    # --- INICIO DE LA CORRECCIÓN ---
    # Comprueba si el objeto 'dictionary' es un diccionario o un objeto similar
    # que tenga un método .get() antes de intentar usarlo.
    if hasattr(dictionary, 'get'):
        return dictionary.get(key)
    
    # Si no es un diccionario (probablemente porque es None), devuelve None.
    return None
    # --- FIN DE LA CORRECCIÓN ---

@register.filter(name='model_name')
def model_name(value):
    """
    Devuelve el nombre de la clase de un objeto de modelo.
    (Esta función se mantiene igual)
    """
    if hasattr(value, '__class__'):
        return value.__class__.__name__
    return ''