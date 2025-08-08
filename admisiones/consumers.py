# admisiones/consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        print(f"--- CONSUMER DEBUG: Intento de conexión de: {user} ---")
        
        if user.is_authenticated and user.is_staff:
            self.room_group_name = 'admin_notifications'
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            await self.accept()
            print(f"--- CONSUMER DEBUG: Conexión ACEPTADA para {user} ---")
        else:
            print(f"--- CONSUMER DEBUG: Conexión RECHAZADA para {user} ---")
            await self.close()

    async def disconnect(self, close_code):
        print("--- CONSUMER DEBUG: WebSocket desconectado ---")
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def send_notification(self, event):
        message = event['message']
        print(f"--- CONSUMER DEBUG: Recibido mensaje para enviar: '{message}' ---")
        await self.send(text_data=json.dumps({
            'message': message
        }))