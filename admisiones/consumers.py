# admisiones/consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer

class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Cada usuario autenticado entra al grupo user_{pk} (toasts y eventos personales).
    El personal (is_staff) además entra a admin_notifications (broadcasts legacy).
    """

    async def connect(self):
        user = self.scope["user"]

        if not user.is_authenticated:
            await self.close()
            return

        self._channel_groups = []
        personal_group = f"user_{user.pk}"
        await self.channel_layer.group_add(personal_group, self.channel_name)
        self._channel_groups.append(personal_group)

        if user.is_staff:
            await self.channel_layer.group_add("admin_notifications", self.channel_name)
            self._channel_groups.append("admin_notifications")

        await self.accept()

    async def disconnect(self, close_code):
        for group_name in getattr(self, "_channel_groups", []):
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def send_notification(self, event):
        """
        Envía al navegador un JSON con campos estables para el cliente (Fase A).
        Compatibilidad: si solo viene 'message' (código antiguo), el resto toma valores por defecto.
        """
        message = event.get("message", "")
        payload = {
            "kind": event.get("kind") or "generic",
            "title": event.get("title") or "Notificación",
            "message": message,
            "url": event.get("url") or "",
            "severity": event.get("severity") or "info",
        }
        if event.get("institucion_id") is not None:
            payload["institucion_id"] = event["institucion_id"]
        await self.send(text_data=json.dumps(payload))