# admisiones/consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

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

        # Presencia: este WebSocket vive mientras el usuario tiene la app abierta,
        # así que sirve como señal de "en línea". Avisa a sus pares del cambio.
        await self._actualizar_presencia(user.pk, +1)

    async def disconnect(self, close_code):
        for group_name in getattr(self, "_channel_groups", []):
            await self.channel_layer.group_discard(group_name, self.channel_name)
        user = self.scope.get("user")
        if user and getattr(user, "is_authenticated", False):
            await self._actualizar_presencia(user.pk, -1)

    async def _actualizar_presencia(self, usuario_id, delta):
        try:
            from mensajeria.presencia import marcar_conexion, broadcast_presencia
            estado = await database_sync_to_async(marcar_conexion)(usuario_id, delta)
            await database_sync_to_async(broadcast_presencia)(usuario_id, estado)
        except Exception:
            pass

    async def presencia_update(self, event):
        """Reenvía al navegador un cambio de presencia de un par."""
        await self.send(text_data=json.dumps({
            "kind": "presencia",
            "usuario_id": event.get("usuario_id"),
            "nombre": event.get("nombre", ""),
            "estado": event.get("estado", "DESCONECTADO"),
        }))

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