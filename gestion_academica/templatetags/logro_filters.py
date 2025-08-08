# gestion_academica/templatetags/logro_filters.py

from django.template import Library

register = Library()

@register.filter
def get_item(dictionary, key):
    """
    Permite acceder a un valor de un diccionario usando una variable como clave en las plantillas.
    Uso: {{ mi_diccionario|get_item:mi_variable_de_clave }}
    """
    if hasattr(dictionary, 'get'):
        return dictionary.get(key)
    return None