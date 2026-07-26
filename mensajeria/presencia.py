"""
mensajeria/presencia.py
=======================
Lógica de presencia (en línea / ausente / desconectado) para la mensajería.

- `conexiones` cuenta los WebSocket activos de un usuario (varias pestañas o
  dispositivos). Conectado si > 0. Se actualiza con F() para ser atómico.
- Cuando el estado efectivo de un usuario cambia, se avisa a sus "pares"
  (los otros participantes de sus conversaciones) por el canal user_{pk},
  que el NotificationConsumer reenvía al navegador.

Todas las funciones son SÍNCRONAS; el consumer las envuelve con
database_sync_to_async.
"""
from django.db.models import F, Q
from django.utils import timezone


def _get_or_create(usuario_id):
    from .models import PresenciaUsuario
    obj, _ = PresenciaUsuario.objects.get_or_create(usuario_id=usuario_id)
    return obj


def estado_de(usuario_id):
    """Estado efectivo actual del usuario: EN_LINEA / AUSENTE / DESCONECTADO."""
    return _get_or_create(usuario_id).estado_efectivo()


def marcar_conexion(usuario_id, delta):
    """Suma/resta una conexión WebSocket y devuelve el estado efectivo resultante."""
    from .models import PresenciaUsuario
    PresenciaUsuario.objects.get_or_create(usuario_id=usuario_id)
    if delta > 0:
        PresenciaUsuario.objects.filter(usuario_id=usuario_id).update(
            conexiones=F('conexiones') + 1, ausente_auto=False, last_seen=timezone.now()
        )
    else:
        PresenciaUsuario.objects.filter(usuario_id=usuario_id, conexiones__gt=0).update(
            conexiones=F('conexiones') - 1, last_seen=timezone.now()
        )
    return PresenciaUsuario.objects.get(usuario_id=usuario_id).estado_efectivo()


def set_estado_manual(usuario_id, estado_manual):
    """Fija DISPONIBLE / AUSENTE manual y limpia el auto-away."""
    from .models import PresenciaUsuario
    PresenciaUsuario.objects.update_or_create(
        usuario_id=usuario_id,
        defaults={'estado_manual': estado_manual, 'ausente_auto': False, 'last_seen': timezone.now()},
    )
    return estado_de(usuario_id)


def set_auto_away(usuario_id, away):
    """Marca/limpia el ausente automático por inactividad."""
    from .models import PresenciaUsuario
    PresenciaUsuario.objects.update_or_create(
        usuario_id=usuario_id,
        defaults={'ausente_auto': bool(away), 'last_seen': timezone.now()},
    )
    return estado_de(usuario_id)


def peers_de(usuario_id):
    """IDs de los otros participantes de las conversaciones del usuario."""
    from .models import Conversacion
    peers = set()
    for a, b in Conversacion.objects.filter(
        Q(participante_a_id=usuario_id) | Q(participante_b_id=usuario_id)
    ).values_list('participante_a_id', 'participante_b_id'):
        peers.add(b if a == usuario_id else a)
    return peers


def broadcast_presencia(usuario_id, estado):
    """Avisa a los pares del usuario (canal user_{pk}) que su presencia cambió."""
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer
    from django.contrib.auth import get_user_model

    layer = get_channel_layer()
    if layer is None:
        return
    u = get_user_model().objects.filter(pk=usuario_id).first()
    nombre = (u.get_full_name() or u.username) if u else ''
    payload = {
        'type': 'presencia_update',
        'usuario_id': usuario_id,
        'nombre': nombre,
        'estado': estado,
    }
    for peer_id in peers_de(usuario_id):
        try:
            async_to_sync(layer.group_send)(f"user_{peer_id}", payload)
        except Exception:
            pass
