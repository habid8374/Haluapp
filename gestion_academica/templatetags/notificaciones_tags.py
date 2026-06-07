from django import template
from gestion_academica.models import Notificacion

register = template.Library()

@register.inclusion_tag('gestion_academica/tags/notificaciones_bell.html', takes_context=True)
def notificaciones_bell(context):
    """
    Renderiza el ícono de campana con dropdown de notificaciones recientes.
    """
    request = context.get('request')
    unread_count = 0
    recientes = []

    if request and request.user.is_authenticated:
        qs = Notificacion.objects.filter(
            destinatario=request.user
        ).order_by('-fecha_creacion')

        unread_count = qs.filter(leido=False).count()
        recientes    = list(qs[:6])   # últimas 6 para el dropdown

    return {
        'unread_count': unread_count,
        'recientes':    recientes,
        'request':      request,
    }
