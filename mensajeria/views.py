"""
mensajeria/views.py
===================
Vistas HTTP para el módulo de mensajería directa.

Endpoints HTML:
  GET  /mensajeria/                              → inbox (lista de conversaciones)
  GET  /mensajeria/<id>/                         → detalle de conversación (chat)
  POST /mensajeria/iniciar/<destinatario_pk>/    → crear o recuperar conversación
  POST /mensajeria/<id>/archivar/                → archivar/desarchivar conversación

Endpoints API (JSON):
  GET  /mensajeria/api/conversaciones/           → lista para el móvil
  GET  /mensajeria/api/mensajes/<id>/            → mensajes de una conversación
  POST /mensajeria/api/enviar/                   → enviar mensaje vía HTTP (fallback)
  GET  /mensajeria/api/no-leidos/                → contador de mensajes no leídos
"""
import json
import logging

from django.contrib.auth.decorators import login_required
from django.db.models import Q, Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.contrib import messages as flash
from django.utils import timezone

from .models import Conversacion, Mensaje

logger = logging.getLogger(__name__)


# ======================================================================= #
#  Helpers                                                                  #
# ======================================================================= #

def _qs_conversaciones(user):
    """Queryset base: conversaciones del usuario ordenadas por último mensaje."""
    return (
        Conversacion.objects
        .filter(Q(participante_a=user) | Q(participante_b=user))
        .select_related('participante_a', 'participante_b', 'estudiante_contexto')
        .order_by('-ultimo_mensaje_en')
    )


def _get_institucion(user):
    """Devuelve la InstitucionEducativa asociada al usuario."""
    return getattr(user, 'institucion_asociada', None)


# ── Categorías de rol para la mensajería ──────────────────────────────────
# Personal (staff): se pueden escribir entre sí. El docente es personal PERO
# además puede escribir a familias/estudiantes de sus cursos. Los alumnos
# (estudiante/familiar) solo se comunican con docentes.
ROLES_PERSONAL = {
    'rector', 'coordinador', 'administrador', 'administrativo',
    'admin_institucion', 'tesoreria', 'secretaria', 'psicologo', 'docente',
}
ROLES_ALUMNO = {'estudiante', 'familiar'}
_ROL_ETIQUETA = {
    'rector': 'Rector(a) / Directivo', 'coordinador': 'Coordinador(a)',
    'administrador': 'Administrador(a)', 'administrativo': 'Administrativo(a)',
    'admin_institucion': 'Administrador(a)', 'tesoreria': 'Tesorería',
    'secretaria': 'Secretaría', 'psicologo': 'Psicoorientador(a)', 'docente': 'Docente',
}


def _directorio_personal(institucion, exclude_user):
    """Lista de dicts del personal (staff) de la institución para el selector
    de nuevo mensaje. Excluye al propio usuario y a alumnos/familias."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    if not institucion:
        return []
    qs = (
        User.objects
        .filter(institucion_asociada=institucion, is_active=True, rol__in=list(ROLES_PERSONAL))
        .exclude(pk=exclude_user.pk)
        .order_by('last_name', 'first_name')
    )
    out = []
    for u in qs:
        nombre = u.get_full_name() or u.username
        etiqueta_rol = _ROL_ETIQUETA.get(u.rol or '', 'Personal')
        out.append({
            'usuario': u,
            'etiqueta': nombre,
            'sub': etiqueta_rol,
            'estudiante_id': None,
            'busqueda': f"{nombre} {etiqueta_rol}".lower(),
        })
    return out


def _categoria_rol(rol):
    if rol in ROLES_PERSONAL:
        return 'personal'
    if rol in ROLES_ALUMNO:
        return 'alumno'
    return 'otro'


def _puede_conversar(remitente, destinatario):
    """Reglas de quién puede iniciar/mantener un chat con quién.

    - Personal ↔ personal: sí.
    - Docente ↔ alumno (estudiante/familiar), en cualquier dirección: sí.
    - Administrativo (no docente) ↔ alumno: no.
    - Alumno ↔ alumno: no.
    El superusuario puede con cualquiera.
    """
    if getattr(remitente, 'is_superuser', False):
        return True
    ra = getattr(remitente, 'rol', '') or ''
    rb = getattr(destinatario, 'rol', '') or ''
    ca, cb = _categoria_rol(ra), _categoria_rol(rb)
    if ca == 'personal' and cb == 'personal':
        return True
    if ('docente' in (ra, rb)) and ('alumno' in (ca, cb)):
        return True
    return False


# ======================================================================= #
#  Vistas HTML                                                              #
# ======================================================================= #

@login_required
def inbox(request):
    """Lista todas las conversaciones del usuario (no archivadas por defecto)."""
    mostrar_archivadas = request.GET.get('archivadas') == '1'
    qs = _qs_conversaciones(request.user)

    conversaciones = []
    for conv in qs:
        # Ocultar las que el usuario eliminó de su bandeja (soft-delete propio).
        if conv.esta_eliminada_para(request.user):
            continue
        archivada = conv.esta_archivada_para(request.user)
        if archivada and not mostrar_archivadas:
            continue
        if not archivada and mostrar_archivadas:
            continue
        otro = conv.get_otro_participante(request.user)
        from .presencia import estado_de
        conversaciones.append({
            'conv': conv,
            'otro': otro,
            'no_leidos': conv.no_leidos_para(request.user),
            'archivada': archivada,
            'estado': estado_de(otro.pk),
        })

    return render(request, 'mensajeria/inbox.html', {
        'conversaciones': conversaciones,
        'mostrar_archivadas': mostrar_archivadas,
    })


@login_required
def detalle_conversacion(request, conversacion_id):
    """Vista de chat: muestra historial y el input de mensajes."""
    conv = get_object_or_404(
        Conversacion.objects.select_related(
            'participante_a', 'participante_b',
            'estudiante_contexto', 'institucion',
        ),
        pk=conversacion_id,
    )

    # Verificar que el usuario es participante
    if request.user.pk not in (conv.participante_a_id, conv.participante_b_id):
        flash.error(request, "No tienes acceso a esta conversación.")
        return redirect('mensajeria:inbox')

    # Marcar mensajes como leídos
    ahora = timezone.now()
    Mensaje.objects.filter(
        conversacion=conv,
        leido=False,
    ).exclude(remitente=request.user).update(leido=True, leido_en=ahora)

    mensajes = (
        conv.mensajes
        .select_related('remitente')
        .order_by('enviado_en')
    )

    otro = conv.get_otro_participante(request.user)
    from .presencia import estado_de

    return render(request, 'mensajeria/conversacion.html', {
        'conv': conv,
        'otro': otro,
        'mensajes': mensajes,
        'conversacion_id': conv.pk,
        'otro_estado': estado_de(otro.pk),
    })


@login_required
@require_POST
def iniciar_conversacion(request, destinatario_pk):
    """
    Crea o recupera una conversación con el usuario destinatario.
    El parámetro opcional `estudiante_id` en el body POST fija el contexto.
    Redirecciona al detalle de la conversación.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    estudiante_id = request.POST.get('estudiante_id') or None
    institucion = _get_institucion(request.user)

    if not institucion:
        flash.error(request, "Tu cuenta no está asociada a ninguna institución.")
        return redirect('mensajeria:inbox')

    # Aislamiento multi-institución: solo se puede iniciar conversación con
    # usuarios de la misma institución (el superusuario puede con cualquiera).
    destinatario_qs = User.objects.all()
    if not request.user.is_superuser:
        destinatario_qs = destinatario_qs.filter(institucion_asociada=institucion)
    destinatario = get_object_or_404(destinatario_qs, pk=destinatario_pk)

    if destinatario == request.user:
        flash.error(request, "No puedes enviarte mensajes a ti mismo.")
        return redirect('mensajeria:inbox')

    # Reglas de categoría: personal↔personal, y docente↔alumno. Un administrativo
    # no puede iniciar chat con estudiantes/familias, ni un alumno con otro alumno.
    if not _puede_conversar(request.user, destinatario):
        flash.error(request, "No puedes iniciar una conversación con este usuario.")
        return redirect('mensajeria:inbox')

    # Normalizar: participante_a siempre el de menor pk para evitar duplicados
    # cuando unique_together no incluye estudianteContexto=None
    pk_a, pk_b = sorted([request.user.pk, destinatario.pk])
    user_a = request.user if request.user.pk == pk_a else destinatario
    user_b = destinatario if request.user.pk == pk_a else request.user

    # Estudiante contexto (opcional)
    estudiante = None
    if estudiante_id:
        try:
            from gestion_academica.models import Estudiante
            estudiante = Estudiante.objects.get(pk=estudiante_id, institucion=institucion)
        except Exception:
            pass

    conv, _ = Conversacion.objects.get_or_create(
        participante_a=user_a,
        participante_b=user_b,
        estudiante_contexto=estudiante,
        defaults={'institucion': institucion},
    )

    return redirect('mensajeria:detalle', conversacion_id=conv.pk)


@login_required
def nuevo_mensaje(request):
    """
    GET  /mensajeria/nuevo/
    Muestra la lista de personas con quienes el usuario puede iniciar un chat.

    - Familiar  → ve los docentes de sus estudiantes, agrupados por estudiante.
    - Docente   → ve los familiares de sus alumnos.
    - Staff     → ve todos los docentes de la institución.
    """
    from gestion_academica.models import Estudiante, Docente, Familiar

    user = request.user
    institucion = _get_institucion(user)
    destinatarios = []   # lista de dicts: {usuario, etiqueta, estudiante}

    # Filtro opcional por estudiante (viene del portal familiar via ?estudiante=<pk>)
    filtro_estudiante_pk = request.GET.get('estudiante')

    # ── Helper: construye destinatarios docentes para un estudiante concreto ──
    def _docentes_de_estudiante(estudiante_obj, mostrar_nombre_est=True):
        """Devuelve lista de dicts {usuario, etiqueta, sub, estudiante_id} para el estudiante."""
        from gestion_academica.models import Curso as _Curso
        nivel = (
            getattr(estudiante_obj.grado_actual, 'nivel_escolaridad', None)
            if estudiante_obj.grado_actual else None
        )
        if not nivel:
            return []

        cursos = (
            _Curso.objects
            .filter(grado__nivel_escolaridad=nivel, institucion=institucion)
            .prefetch_related('docentes_asignados__usuario')
            .select_related('materia')
        )

        docente_materias: dict = {}
        for curso in cursos:
            for doc in curso.docentes_asignados.all():
                mats = docente_materias.setdefault(doc, [])
                nombre_mat = curso.materia.nombre_materia
                if nombre_mat not in mats:
                    mats.append(nombre_mat)

        resultado = []
        for doc, mats in docente_materias.items():
            mats_str = ', '.join(mats[:3])
            if len(mats) > 3:
                mats_str += f' +{len(mats)-3}'
            sub = mats_str
            if mostrar_nombre_est:
                sub += f' · {nivel.nombre} · {estudiante_obj.usuario.get_full_name()}'
            else:
                sub += f' · {nivel.nombre}'
            nombre_doc = doc.usuario.get_full_name() or doc.usuario.username
            resultado.append({
                'usuario':       doc.usuario,
                'etiqueta':      nombre_doc,
                'sub':           sub,
                'estudiante_id': estudiante_obj.pk,
                'busqueda':      f"{nombre_doc} {' '.join(mats)}".lower(),
            })
        return resultado

    if user.rol == 'familiar':
        # ── Familiar: docentes filtrados por nivel de escolaridad del estudiante ──
        try:
            familiar = user.familiar
        except Exception:
            familiar = None

        if familiar:
            qs_estudiantes = (
                familiar.estudiantes_asociados
                .filter(activo=True)
                .select_related('usuario', 'grado_actual__nivel_escolaridad')
            )
            if filtro_estudiante_pk:
                qs_estudiantes = qs_estudiantes.filter(pk=filtro_estudiante_pk)

            vistos = set()
            for estudiante in qs_estudiantes:
                for item in _docentes_de_estudiante(estudiante, mostrar_nombre_est=True):
                    key = (item['usuario'].pk, estudiante.pk)
                    if key not in vistos:
                        vistos.add(key)
                        destinatarios.append(item)

    elif user.rol == 'estudiante':
        # ── Estudiante: sus propios docentes según su nivel de escolaridad ──
        try:
            estudiante_obj = user.estudiante
        except Exception:
            estudiante_obj = None

        if estudiante_obj:
            destinatarios = _docentes_de_estudiante(estudiante_obj, mostrar_nombre_est=False)

    elif user.rol == 'docente':
        # ── Docente: agrupado por grado → alumnos → familiares ──────────────
        try:
            docente = user.docente
        except Exception:
            docente = None

        if docente:
            from gestion_academica.models import BloqueHorario, Grado
            grados_qs = (
                Grado.objects
                .filter(
                    cursos__docentes_asignados=docente,
                    cursos__institucion=institucion,
                )
                .distinct()
                .order_by('nombre')
            )

            grupos_grado = []
            for grado in grados_qs:
                alumnos_grado = (
                    Estudiante.objects
                    .filter(grado_actual=grado, activo=True)
                    .select_related('usuario')
                    .prefetch_related('familiares__usuario')
                    .order_by('usuario__last_name', 'usuario__first_name')
                )
                filas = []
                for est in alumnos_grado:
                    familiares = [
                        {
                            'usuario':       f.usuario,
                            'etiqueta':      f.usuario.get_full_name() or f.usuario.username,
                            'estudiante_id': est.pk,
                        }
                        for f in est.familiares.all()
                    ]
                    filas.append({
                        'estudiante':  est,
                        'nombre_est':  est.usuario.get_full_name(),
                        'familiares':  familiares,
                    })
                if filas:
                    grupos_grado.append({'grado': grado, 'alumnos': filas})

        # El docente también es personal: puede escribir al resto del personal.
        destinatarios = _directorio_personal(institucion, user)

    else:
        # ── Personal administrativo (rector, coordinador, administrador,
        #    tesorería, secretaría): ven al resto del PERSONAL, no a alumnos. ──
        destinatarios = _directorio_personal(institucion, user)

    # Título contextual
    titulo = 'Nuevo mensaje'
    subtitulo = None
    if user.rol == 'estudiante' and destinatarios:
        subtitulo = f"Tus docentes en {destinatarios[0]['sub'].split(' · ')[-1]}"
    elif filtro_estudiante_pk and destinatarios:
        partes = destinatarios[0]['sub'].split(' · ')
        if len(partes) >= 3:
            subtitulo = f"Docentes de {partes[-1]} — {partes[-2]}"

    return render(request, 'mensajeria/nuevo_mensaje.html', {
        'destinatarios':  destinatarios,
        'grupos_grado':   locals().get('grupos_grado', []),
        'titulo':         titulo,
        'subtitulo':      subtitulo,
    })


@login_required
@require_POST
def archivar_conversacion(request, conversacion_id):
    """Alterna el estado de archivado de una conversación para el usuario actual."""
    conv = get_object_or_404(Conversacion, pk=conversacion_id)

    if request.user.pk not in (conv.participante_a_id, conv.participante_b_id):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    if request.user.pk == conv.participante_a_id:
        conv.archivada_por_a = not conv.archivada_por_a
        conv.save(update_fields=['archivada_por_a'])
        archivada = conv.archivada_por_a
    else:
        conv.archivada_por_b = not conv.archivada_por_b
        conv.save(update_fields=['archivada_por_b'])
        archivada = conv.archivada_por_b

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'archivada': archivada})

    estado = "archivada" if archivada else "restaurada"
    flash.success(request, f"Conversación {estado}.")
    return redirect('mensajeria:inbox')


@login_required
def marcar_leida_conversacion(request, conversacion_id):
    """Marca la conversación como leída o no leída para el usuario actual.

    accion='leida'    → marca como leídos todos los mensajes entrantes.
    accion='no_leida' → marca el último mensaje entrante como no leído (para
                        que reaparezca el indicador de no leído).
    """
    conv = get_object_or_404(Conversacion, pk=conversacion_id)
    if request.user.pk not in (conv.participante_a_id, conv.participante_b_id):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    accion = request.POST.get('accion', 'leida')
    if accion == 'no_leida':
        ultimo = (
            conv.mensajes.exclude(remitente=request.user)
            .order_by('-enviado_en').first()
        )
        if ultimo and ultimo.leido:
            ultimo.leido = False
            ultimo.leido_en = None
            ultimo.save(update_fields=['leido', 'leido_en'])
        leido = False
    else:
        conv.mensajes.filter(leido=False).exclude(remitente=request.user).update(
            leido=True, leido_en=timezone.now()
        )
        leido = True

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'leido': leido})
    return redirect('mensajeria:inbox')


@login_required
def eliminar_conversacion(request, conversacion_id):
    """Soft-delete: saca la conversación de la bandeja del usuario actual.

    No borra el hilo ni los mensajes; el otro participante la sigue viendo y la
    supervisión del coordinador queda intacta. Reaparece si llega un mensaje
    nuevo (la señal de Mensaje limpia las banderas)."""
    conv = get_object_or_404(Conversacion, pk=conversacion_id)
    if request.user.pk not in (conv.participante_a_id, conv.participante_b_id):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    if request.user.pk == conv.participante_a_id:
        conv.eliminada_por_a = True
        conv.save(update_fields=['eliminada_por_a'])
    else:
        conv.eliminada_por_b = True
        conv.save(update_fields=['eliminada_por_b'])

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})
    flash.success(request, "Conversación eliminada.")
    return redirect('mensajeria:inbox')


@login_required
def eliminar_historial(request):
    """Soft-delete de TODO el historial de conversaciones del usuario actual."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    Conversacion.objects.filter(participante_a=request.user).update(eliminada_por_a=True)
    Conversacion.objects.filter(participante_b=request.user).update(eliminada_por_b=True)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})
    flash.success(request, "Historial de conversaciones eliminado.")
    return redirect('mensajeria:inbox')


# ======================================================================= #
#  API JSON (móvil / AJAX)                                                  #
# ======================================================================= #

@login_required
def api_conversaciones(request):
    """
    GET /mensajeria/api/conversaciones/
    Devuelve lista de conversaciones activas del usuario.
    """
    qs = _qs_conversaciones(request.user)
    resultado = []
    for conv in qs:
        if conv.esta_archivada_para(request.user):
            continue
        otro = conv.get_otro_participante(request.user)
        resultado.append({
            'id': conv.pk,
            'otro_usuario_id': otro.pk,
            'otro_usuario_nombre': otro.get_full_name() or otro.username,
            'ultimo_mensaje_en': conv.ultimo_mensaje_en.isoformat() if conv.ultimo_mensaje_en else None,
            'no_leidos': conv.no_leidos_para(request.user),
        })
    return JsonResponse({'conversaciones': resultado})


@login_required
def api_mensajes(request, conversacion_id):
    """
    GET /mensajeria/api/mensajes/<id>/
    Devuelve los mensajes de una conversación.
    Parámetros opcionales: ?desde=<ISO datetime> para paginación incremental.
    """
    conv = get_object_or_404(Conversacion, pk=conversacion_id)
    if request.user.pk not in (conv.participante_a_id, conv.participante_b_id):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    qs = conv.mensajes.select_related('remitente').order_by('enviado_en')

    # Filtro por ID (polling incremental, más preciso que timestamp)
    desde_id = request.GET.get('desde_id')
    if desde_id:
        try:
            qs = qs.filter(pk__gt=int(desde_id))
        except (ValueError, TypeError):
            pass
    else:
        # Compatibilidad: filtro legacy por datetime
        desde = request.GET.get('desde')
        if desde:
            try:
                from django.utils.dateparse import parse_datetime
                dt = parse_datetime(desde)
                if dt:
                    qs = qs.filter(enviado_en__gt=dt)
            except Exception:
                pass

    mensajes = [
        {
            'id': m.pk,
            'texto': m.texto,
            'remitente_id': m.remitente_id,
            'remitente_nombre': m.remitente.get_full_name() or m.remitente.username,
            'enviado_en': m.enviado_en.isoformat(),
            'leido': m.leido,
            'adjunto_url': m.adjunto.url if m.adjunto else '',
        }
        for m in qs
    ]
    return JsonResponse({'mensajes': mensajes})


@login_required
@require_POST
def api_enviar_mensaje(request):
    """
    POST /mensajeria/api/enviar/
    Fallback HTTP para enviar un mensaje cuando el WebSocket no está disponible.
    Body JSON: { "conversacion_id": int, "texto": str }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    conversacion_id = data.get('conversacion_id')
    texto = (data.get('texto') or '').strip()

    if not conversacion_id or not texto:
        return JsonResponse({'error': 'Faltan campos requeridos'}, status=400)

    if len(texto) > 2000:
        return JsonResponse({'error': 'Texto demasiado largo (máx. 2000)'}, status=400)

    conv = get_object_or_404(Conversacion, pk=conversacion_id)
    if request.user.pk not in (conv.participante_a_id, conv.participante_b_id):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    msg = Mensaje.objects.create(
        conversacion=conv,
        remitente=request.user,
        texto=texto,
    )
    conv.ultimo_mensaje_en = msg.enviado_en
    conv.save(update_fields=['ultimo_mensaje_en'])

    destinatario = conv.get_otro_participante(request.user)
    remitente_nombre = request.user.get_full_name() or request.user.username

    # Broadcast via channel layer (misma lógica que el consumer WS)
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        group_name = f'conv_{conv.pk}'
        payload = {
            'type': 'mensaje_nuevo',
            'id': msg.pk,
            'texto': texto,
            'remitente_id': request.user.pk,
            'remitente_nombre': remitente_nombre,
            'enviado_en': msg.enviado_en.isoformat(),
            'adjunto_url': '',
            'destinatario_id': destinatario.pk,
        }
        async_to_sync(channel_layer.group_send)(group_name, payload)
        # El toast al destinatario lo envía la señal post_save de Mensaje
        # (mensajeria/signals.py), única fuente para no duplicar el aviso.
    except Exception as exc:
        logger.warning('api_enviar_mensaje: channel broadcast falló: %s', exc)

    return JsonResponse({
        'id': msg.pk,
        'texto': msg.texto,
        'remitente_id': request.user.pk,
        'remitente_nombre': remitente_nombre,
        'enviado_en': msg.enviado_en.isoformat(),
    }, status=201)


@login_required
def api_no_leidos(request):
    """
    GET /mensajeria/api/no-leidos/
    Devuelve el número total de mensajes no leídos del usuario.
    Útil para el badge del menú.
    """
    total = Mensaje.objects.filter(
        conversacion__in=_qs_conversaciones(request.user),
        leido=False,
    ).exclude(remitente=request.user).count()

    return JsonResponse({'no_leidos': total})


# ---------------------------------------------------------------------------
#  Presencia (en línea / ausente)
# ---------------------------------------------------------------------------
@login_required
@require_POST
def set_presencia(request):
    """El usuario fija su estado manual: DISPONIBLE (en línea) o AUSENTE."""
    from .presencia import set_estado_manual, broadcast_presencia
    from .models import PresenciaUsuario
    estado = request.POST.get('estado')
    validos = (PresenciaUsuario.EstadoManual.DISPONIBLE, PresenciaUsuario.EstadoManual.AUSENTE)
    if estado not in validos:
        return JsonResponse({'ok': False, 'error': 'estado inválido'}, status=400)
    efectivo = set_estado_manual(request.user.pk, estado)
    broadcast_presencia(request.user.pk, efectivo)
    return JsonResponse({'ok': True, 'estado': efectivo})


@login_required
@require_POST
def set_auto_away(request):
    """Ausente automático por inactividad (lo dispara el cliente)."""
    from .presencia import set_auto_away as _set_auto_away, broadcast_presencia
    away = request.POST.get('away') == '1'
    efectivo = _set_auto_away(request.user.pk, away)
    broadcast_presencia(request.user.pk, efectivo)
    return JsonResponse({'ok': True, 'estado': efectivo})


@login_required
def mi_estado_presencia(request):
    """Estado manual guardado del propio usuario (para pintar el selector)."""
    from .presencia import _get_or_create
    p = _get_or_create(request.user.pk)
    return JsonResponse({'estado_manual': p.estado_manual})
