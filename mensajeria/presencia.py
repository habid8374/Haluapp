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
    """Obtiene/crea la presencia del usuario, fijando su institución (regla
    multi-institución) desde institucion_asociada al crearla."""
    from .models import PresenciaUsuario
    from django.contrib.auth import get_user_model
    obj = PresenciaUsuario.objects.filter(usuario_id=usuario_id).first()
    if obj is not None:
        return obj
    inst_id = get_user_model().objects.filter(pk=usuario_id).values_list(
        'institucion_asociada_id', flat=True
    ).first()
    obj, _ = PresenciaUsuario.objects.get_or_create(
        usuario_id=usuario_id, defaults={'institucion_id': inst_id}
    )
    return obj


def estado_de(usuario_id):
    """Estado efectivo actual del usuario: EN_LINEA / AUSENTE / DESCONECTADO."""
    return _get_or_create(usuario_id).estado_efectivo()


def marcar_conexion(usuario_id, delta):
    """Suma/resta una conexión WebSocket y devuelve el estado efectivo resultante."""
    from .models import PresenciaUsuario
    _get_or_create(usuario_id)  # asegura la fila con su institución
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
    _get_or_create(usuario_id)
    PresenciaUsuario.objects.filter(usuario_id=usuario_id).update(
        estado_manual=estado_manual, ausente_auto=False, last_seen=timezone.now()
    )
    return estado_de(usuario_id)


def set_auto_away(usuario_id, away):
    """Marca/limpia el ausente automático por inactividad."""
    from .models import PresenciaUsuario
    _get_or_create(usuario_id)
    PresenciaUsuario.objects.filter(usuario_id=usuario_id).update(
        ausente_auto=bool(away), last_seen=timezone.now()
    )
    return estado_de(usuario_id)


# Roles considerados "personal" (staff). Se mantiene igual que
# mensajeria.views.ROLES_PERSONAL; se duplica aquí para evitar un import
# circular (views importa presencia).
ROLES_PERSONAL = {
    'rector', 'coordinador', 'administrador', 'administrativo',
    'admin_institucion', 'tesoreria', 'secretaria', 'docente',
}


def peers_de(usuario_id):
    """IDs de los usuarios que deben VER la presencia de este usuario —aunque
    todavía no tengan un chat abierto entre ellos— así reciben el aviso
    «X está en línea» al conectarse.

    Reglas (las mismas de la mensajería), SIEMPRE acotadas a la MISMA
    institución (defensa multi-institución):
      - Personal ↔ personal: todo el personal del colegio se ve entre sí.
      - Además, los otros participantes de las conversaciones YA existentes
        (cubre el caso docente ↔ alumno que ya venían conversando).
    """
    from .models import Conversacion
    from django.contrib.auth import get_user_model
    User = get_user_model()

    urow = User.objects.filter(pk=usuario_id).values(
        'institucion_asociada_id', 'rol'
    ).first()
    if not urow:
        return set()
    inst_id = urow['institucion_asociada_id']
    rol = urow['rol'] or ''

    peers = set()

    # Personal ↔ personal: todo el personal activo del mismo colegio, sin
    # necesidad de que ya exista un chat.
    if inst_id is not None and rol in ROLES_PERSONAL:
        peers.update(
            User.objects.filter(
                institucion_asociada_id=inst_id, is_active=True, rol__in=ROLES_PERSONAL
            ).exclude(pk=usuario_id).values_list('pk', flat=True)
        )

    # Docente ↔ alumnos (estudiantes/familias) de sus cursos del periodo activo,
    # sin necesitar chat previo. Acotado por institución dentro del helper.
    if inst_id is not None and rol in ('docente', 'estudiante', 'familiar'):
        peers.update(_peers_curso(usuario_id, rol, inst_id))

    # Conversaciones ya existentes (por si hubiera chats fuera de las reglas
    # anteriores), acotadas a la institución del usuario.
    convs = Conversacion.objects.filter(
        Q(participante_a_id=usuario_id) | Q(participante_b_id=usuario_id)
    )
    if inst_id is not None:
        convs = convs.filter(institucion_id=inst_id)
    for a, b in convs.values_list('participante_a_id', 'participante_b_id'):
        peers.add(b if a == usuario_id else a)

    peers.discard(usuario_id)
    return peers


def _peers_curso(usuario_id, rol, inst_id):
    """Presencia docente ↔ alumnos de sus cursos (solo periodo activo).

    - Docente → estudiantes (y sus familias) de los grados que dicta.
    - Estudiante → docentes de los cursos de su grado.
    - Familiar → docentes de los cursos de sus estudiantes asociados.
    Todo dentro de la misma institución.
    """
    from gestion_academica.models import (
        Estudiante, Docente, Familiar, Curso, PeriodoAcademico,
    )
    peers = set()
    periodo_ids = list(
        PeriodoAcademico.objects.filter(institucion_id=inst_id, activo=True)
        .values_list('pk', flat=True)
    )
    if not periodo_ids:
        return peers

    if rol == 'docente':
        docente = Docente.objects.filter(usuario_id=usuario_id).first()
        if not docente:
            return peers
        grado_ids = list(
            Curso.objects.filter(
                docentes_asignados=docente,
                periodo_academico_id__in=periodo_ids,
                institucion_id=inst_id,
            ).values_list('grado_id', flat=True).distinct()
        )
        if not grado_ids:
            return peers
        estudiantes = Estudiante.objects.filter(
            grado_actual_id__in=grado_ids, institucion_id=inst_id
        )
        peers.update(
            estudiantes.exclude(usuario__isnull=True).values_list('usuario_id', flat=True)
        )
        peers.update(
            Familiar.objects.filter(estudiantes_asociados__in=estudiantes)
            .exclude(usuario__isnull=True).values_list('usuario_id', flat=True)
        )
    elif rol == 'estudiante':
        est = Estudiante.objects.filter(usuario_id=usuario_id).first()
        if not est or not est.grado_actual_id:
            return peers
        peers.update(
            Docente.objects.filter(
                cursos_impartidos__grado_id=est.grado_actual_id,
                cursos_impartidos__periodo_academico_id__in=periodo_ids,
                cursos_impartidos__institucion_id=inst_id,
            ).exclude(usuario__isnull=True).values_list('usuario_id', flat=True).distinct()
        )
    elif rol == 'familiar':
        fam = Familiar.objects.filter(usuario_id=usuario_id).first()
        if not fam:
            return peers
        grado_ids = list(
            fam.estudiantes_asociados.exclude(grado_actual__isnull=True)
            .values_list('grado_actual_id', flat=True).distinct()
        )
        if not grado_ids:
            return peers
        peers.update(
            Docente.objects.filter(
                cursos_impartidos__grado_id__in=grado_ids,
                cursos_impartidos__periodo_academico_id__in=periodo_ids,
                cursos_impartidos__institucion_id=inst_id,
            ).exclude(usuario__isnull=True).values_list('usuario_id', flat=True).distinct()
        )
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
