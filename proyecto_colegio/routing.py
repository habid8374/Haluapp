# proyecto_colegio/routing.py

from django.urls import re_path

from admisiones import consumers as admisiones_consumers
from finanzas import consumers as finanzas_consumers
from mensajeria import consumers as mensajeria_consumers

websocket_urlpatterns = [
    re_path(r'ws/notifications/$', admisiones_consumers.NotificationConsumer.as_asgi()),
    re_path(
        r'ws/healthcheck/(?P<ejecucion_id>\d+)/$',
        finanzas_consumers.HealthCheckConsumer.as_asgi(),
    ),
    re_path(
        r'ws/mensajeria/(?P<conversacion_id>\d+)/$',
        mensajeria_consumers.MensajeriaConsumer.as_asgi(),
    ),
]