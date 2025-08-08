# en gestion_academica/templatetags/notificaciones_tags.py

from django import template
from gestion_academica.models import Notificacion

register = template.Library()

@register.inclusion_tag('gestion_academica/tags/notificaciones_bell.html', takes_context=True)
def notificaciones_bell(context):
    """
    Este tag renderiza el ícono de la campana y obtiene la cantidad
    de notificaciones no leídas para el usuario actual.
    """
    request = context.get('request')
    if request and request.user.is_authenticated:
        unread_count = Notificacion.objects.filter(destinatario=request.user, leido=False).count()
    else:
        unread_count = 0
        
    return {
        'unread_count': unread_count
    }