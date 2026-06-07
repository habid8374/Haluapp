"""
mensajeria/signals.py
=====================
Señales para el módulo de mensajería directa.

Al crearse un nuevo Mensaje:
  1. Se crea un registro Notificacion para el destinatario
     (persiste en BD y aparece en el campano del sistema).
  2. Se empuja un evento WebSocket al grupo "user_{destinatario_pk}"
     para el toast en tiempo real (funciona aunque el destinatario
     no esté en la ventana de chat).

El consumer ya envía el toast cuando el remitente es quien está conectado
al WebSocket; esta señal cubre el camino alternativo (Celery task, admin, API).
"""
import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Mensaje

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Mensaje)
def notificar_destinatario(sender, instance, created, **kwargs):
    """Crea Notificacion en BD y empuja toast WebSocket al destinatario."""
    if not created:
        return

    msg = instance
    conv = msg.conversacion
    remitente = msg.remitente
    destinatario = conv.get_otro_participante(remitente)

    # ------------------------------------------------------------------ #
    #  1. Registro persistente en la tabla Notificacion                   #
    # ------------------------------------------------------------------ #
    def _crear_notificacion():
        try:
            from gestion_academica.models import Notificacion
            Notificacion.objects.create(
                destinatario=destinatario,
                institucion=conv.institucion,
                mensaje=f"Nuevo mensaje de {remitente.get_full_name() or remitente.username}",
                enlace=f"/mensajeria/{conv.pk}/",
            )
        except Exception:
            logger.exception(
                "Error creando Notificacion para mensaje %s → usuario %s",
                msg.pk, destinatario.pk,
            )

    transaction.on_commit(_crear_notificacion)

    # ------------------------------------------------------------------ #
    #  2. Toast WebSocket inmediato (best-effort, no rompe el flujo)      #
    # ------------------------------------------------------------------ #
    def _push_ws_toast():
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync

            channel_layer = get_channel_layer()
            if channel_layer is None:
                return

            texto_preview = msg.texto[:80] + ("…" if len(msg.texto) > 80 else "")
            async_to_sync(channel_layer.group_send)(
                f"user_{destinatario.pk}",
                {
                    "type": "send_notification",
                    "kind": "mensaje",
                    "title": f"Nuevo mensaje de {remitente.get_full_name() or remitente.username}",
                    "message": texto_preview,
                    "url": f"/mensajeria/{conv.pk}/",
                    "severity": "info",
                },
            )
        except Exception:
            logger.exception(
                "Error enviando toast WS para mensaje %s → usuario %s",
                msg.pk, destinatario.pk,
            )

    transaction.on_commit(_push_ws_toast)
