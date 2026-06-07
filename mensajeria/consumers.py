"""
mensajeria/consumers.py
========================
Consumer WebSocket para mensajería en tiempo real.

URL: ws/mensajeria/<conversacion_id>/

Grupo de canal: "conv_{conversacion_id}"
  → Cada conversación tiene su propio canal privado.
  → Solo los dos participantes verificados pueden conectarse.

Al recibir un mensaje también emite al grupo "user_{destinatario_pk}"
para que llegue el toast de notificación en cualquier otra pestaña abierta.
"""
import json
import logging
from datetime import datetime

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)


class MensajeriaConsumer(AsyncWebsocketConsumer):

    # ------------------------------------------------------------------ #
    #  Ciclo de vida                                                       #
    # ------------------------------------------------------------------ #

    async def connect(self):
        user = self.scope['user']

        if not user.is_authenticated:
            await self.close(code=4001)
            return

        self.conversacion_id = self.scope['url_route']['kwargs']['conversacion_id']
        self.group_name = f'conv_{self.conversacion_id}'

        # Verificar que el usuario es participante de esta conversación
        es_participante = await self._es_participante(user, self.conversacion_id)
        if not es_participante:
            logger.warning(
                f'Usuario {user.pk} intentó conectarse a conversación '
                f'{self.conversacion_id} sin ser participante.'
            )
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Marcar como leídos los mensajes pendientes del otro participante
        await self._marcar_mensajes_leidos(user, self.conversacion_id)

        # Notificar al otro cliente (si está conectado) que ya leímos
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'mensajes_leidos',
                'lector_id': user.pk,
            }
        )

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        user = self.scope['user']

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        texto = (data.get('texto') or '').strip()
        if not texto or len(texto) > 2000:
            return

        # Guardar en BD
        mensaje_data = await self._guardar_mensaje(user, self.conversacion_id, texto)
        if not mensaje_data:
            return

        # Emitir a todos los conectados en este canal
        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'mensaje_nuevo',
                **mensaje_data,
            }
        )

        # Notificación toast al destinatario (funciona aunque no esté en el chat)
        await self.channel_layer.group_send(
            f"user_{mensaje_data['destinatario_id']}",
            {
                'type': 'send_notification',
                'kind': 'mensaje',
                'title': f"Nuevo mensaje de {mensaje_data['remitente_nombre']}",
                'message': texto[:80] + ('…' if len(texto) > 80 else ''),
                'url': f"/mensajeria/{self.conversacion_id}/",
                'severity': 'info',
            }
        )

    # ------------------------------------------------------------------ #
    #  Handlers de eventos del grupo                                       #
    # ------------------------------------------------------------------ #

    async def mensaje_nuevo(self, event):
        """Envía el mensaje al WebSocket del cliente."""
        await self.send(text_data=json.dumps({
            'tipo': 'mensaje_nuevo',
            'id': event['id'],
            'texto': event['texto'],
            'remitente_id': event['remitente_id'],
            'remitente_nombre': event['remitente_nombre'],
            'enviado_en': event['enviado_en'],
            'adjunto_url': event.get('adjunto_url', ''),
        }))

    async def mensajes_leidos(self, event):
        """Notifica al cliente que el otro participante leyó los mensajes."""
        await self.send(text_data=json.dumps({
            'tipo': 'mensajes_leidos',
            'lector_id': event['lector_id'],
        }))

    # ------------------------------------------------------------------ #
    #  Helpers de base de datos (sync → async)                            #
    # ------------------------------------------------------------------ #

    @database_sync_to_async
    def _es_participante(self, user, conversacion_id):
        from mensajeria.models import Conversacion
        return Conversacion.objects.filter(
            pk=conversacion_id,
        ).filter(
            models_q_participante(user.pk)
        ).exists()

    @database_sync_to_async
    def _marcar_mensajes_leidos(self, user, conversacion_id):
        from mensajeria.models import Mensaje
        from django.utils import timezone
        ahora = timezone.now()
        Mensaje.objects.filter(
            conversacion_id=conversacion_id,
            leido=False,
        ).exclude(remitente=user).update(leido=True, leido_en=ahora)

    @database_sync_to_async
    def _guardar_mensaje(self, user, conversacion_id, texto):
        from mensajeria.models import Conversacion, Mensaje
        from django.db.models import Q
        try:
            conv = Conversacion.objects.select_related(
                'participante_a', 'participante_b'
            ).get(
                pk=conversacion_id,
            )
        except Conversacion.DoesNotExist:
            return None

        # Seguridad: verificar de nuevo que el usuario es participante
        if user.pk not in (conv.participante_a_id, conv.participante_b_id):
            return None

        msg = Mensaje.objects.create(
            conversacion=conv,
            remitente=user,
            texto=texto,
        )

        # Actualizar timestamp del último mensaje en la conversación
        conv.ultimo_mensaje_en = msg.enviado_en
        conv.save(update_fields=['ultimo_mensaje_en'])

        destinatario = conv.get_otro_participante(user)

        return {
            'id': msg.pk,
            'texto': texto,
            'remitente_id': user.pk,
            'remitente_nombre': user.get_full_name() or user.username,
            'enviado_en': msg.enviado_en.isoformat(),
            'adjunto_url': '',
            'destinatario_id': destinatario.pk,
        }


def models_q_participante(user_pk):
    """Q object para filtrar conversaciones donde user_pk es participante."""
    from django.db.models import Q
    return Q(participante_a_id=user_pk) | Q(participante_b_id=user_pk)
