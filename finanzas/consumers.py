"""Consumers WebSocket del módulo finanzas.

Por ahora solo contiene el consumer del **dashboard de mantenimiento del
super-admin**, que recibe los eventos del health-check en tiempo real.
"""
from __future__ import annotations

import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


class HealthCheckConsumer(AsyncWebsocketConsumer):
    """WebSocket que transmite el progreso de un health-check específico.

    Solo super-admins (``is_superuser``) pueden conectar. Recibe cada evento
    (1 por línea de reporte) y los reenvía al cliente como JSON.
    """

    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated or not user.is_superuser:
            await self.close(code=4403)
            return

        self.ejecucion_id = self.scope["url_route"]["kwargs"]["ejecucion_id"]
        self.group_name = f"healthcheck_{self.ejecucion_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.debug("HealthCheckConsumer conectado a %s (user=%s)", self.group_name, user)

    async def disconnect(self, close_code):
        group = getattr(self, "group_name", None)
        if group:
            await self.channel_layer.group_discard(group, self.channel_name)

    async def healthcheck_event(self, event):
        """Recibe ``{type: healthcheck.event, payload: dict}`` y lo reenvía como JSON."""
        payload = event.get("payload") or {}
        try:
            await self.send(text_data=json.dumps(payload))
        except Exception:
            logger.exception("HealthCheckConsumer: fallo al enviar payload.")
