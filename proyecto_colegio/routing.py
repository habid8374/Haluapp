# proyecto_colegio/routing.py

from django.urls import re_path
# Importamos el consumidor directamente desde la app donde vive (admisiones)
from admisiones import consumers 

websocket_urlpatterns = [
    # Esta es la única ruta que nuestro servidor de WebSockets conocerá
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
]