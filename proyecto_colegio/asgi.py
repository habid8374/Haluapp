# proyecto_colegio/asgi.py

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from . import routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proyecto_colegio.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    # AllowedHostsOriginValidator valida el header Origin contra ALLOWED_HOSTS
    # para impedir Cross-Site WebSocket Hijacking (la cookie de sesión viaja
    # cross-site en conexiones WS).
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(
                routing.websocket_urlpatterns
            )
        )
    ),
})
