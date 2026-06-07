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
        archivada = conv.esta_archivada_para(request.user)
        if archivada and not mostrar_archivadas:
            continue
        if not archivada and mostrar_archivadas:
            continue
        otro = conv.get_otro_participante(request.user)
        conversaciones.append({
            'conv': conv,
            'otro': otro,
            'no_leidos': conv.no_leidos_para(request.user),
            'archivada': archivada,
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

    return render(request, 'mensajeria/conversacion.html', {
        'conv': conv,
        'otro': otro,
        'mensajes': mensajes,
        'conversacion_id': conv.pk,
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

    destinatario = get_object_or_404(User, pk=destinatario_pk)
    estudiante_id = request.POST.get('estudiante_id') or None
    institucion = _get_institucion(request.user)

    if not institucion:
        flash.error(request, "Tu cuenta no está asociada a ninguna institución.")
        return redirect('mensajeria:inbox')

    if destinatario == request.user:
        flash.error(request, "No puedes enviarte mensajes a ti mismo.")
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

    else:
        # ── Staff / coordinador / rector: todos los docentes ────────────────
        from gestion_academica.models import Docente as DocenteModel
        for d in DocenteModel.objects.filter(institucion=institucion).select_related('usuario'):
            nombre = d.usuario.get_full_name() or d.usuario.username
            destinatarios.append({
                'usuario':       d.usuario,
                'etiqueta':      nombre,
                'sub':           'Docente',
                'estudiante_id': None,
                'busqueda':      nombre.lower(),
            })

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

        # Toast de notificación al destinatario
        async_to_sync(channel_layer.group_send)(
            f'user_{destinatario.pk}',
            {
                'type': 'send_notification',
                'kind': 'mensaje',
                'title': f'Nuevo mensaje de {remitente_nombre}',
                'message': texto[:80] + ('…' if len(texto) > 80 else ''),
                'url': f'/mensajeria/{conv.pk}/',
                'severity': 'info',
            }
        )
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
