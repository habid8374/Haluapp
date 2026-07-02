# en gestion_academica/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from decimal import Decimal
from django.db.models.signals import pre_save
from google import genai
from google.genai import types
from django.conf import settings
from .utils import enviar_correo_documento_listo
from .models import SolicitudDocumento
import json
from django.template.loader import render_to_string
from django.core.mail import EmailMessage, get_connection

from .models import Calificacion, ArchivoPlanAcademico, Notificacion, AnotacionObservador, Usuario, Candidato, TicketSoporte, RegistroAsistencia, Curso, NivelEscolaridad, Familiar, CitaReunion, CasoConvivencia, InvolucradoCaso, Estudiante, Deber, ActividadCalificable
from finanzas.models import InstitucionEducativa
from finanzas.institucion_credentials import google_api_key as get_inst_google_api_key

import bleach
import logging

logger = logging.getLogger(__name__)

def _sanitize_ai(text: str) -> str:
    """Elimina etiquetas HTML/JS del texto generado por IA antes de persistirlo."""
    return bleach.clean(str(text or ''), tags=[], strip=True).strip()


def _delay_seguro(task, *args):
    """Encola una tarea Celery sin propagar errores: si el broker no está
    disponible, la operación principal (guardar la nota, la anotación, etc.)
    NO debe fallar por eso — solo se pierde el análisis de IA y queda en log."""
    try:
        task.delay(*args)
    except Exception as e:
        logger.error("No se pudo encolar la tarea %s%r: %s",
                     getattr(task, 'name', task), args, e)


@receiver(post_save, sender=Calificacion)
def sugerir_material_de_refuerzo(sender, instance, created, **kwargs):
    """
    Si la calificación es numérica, encola en segundo plano la generación del
    consejo de refuerzo con IA. Antes esto se hacía síncrono aquí (llamada a
    Gemini de varios segundos dentro del post_save) y bloqueaba el guardado de
    notas; ahora solo se encola. La tarea revisa el umbral de aprobación y solo
    genera consejo/notificación si la nota está por debajo del mínimo.
    """
    if instance.valor_numerico is None:
        return
    from django.db import transaction
    from .tasks import sugerir_material_de_refuerzo_task
    pk = instance.pk
    transaction.on_commit(lambda: _delay_seguro(sugerir_material_de_refuerzo_task, pk))


@receiver(post_save, sender=AnotacionObservador)
def analizar_observacion_convivencia(sender, instance, created, **kwargs):
    """
    Encola en segundo plano el análisis de convivencia con IA (Ley 1620) y la
    apertura automática del Caso de Convivencia (TIPO II/III). Antes la llamada
    a Gemini se hacía síncrona dentro del post_save y bloqueaba el guardado.
    """
    if not created or instance.tipo_situacion_ia is not None:
        return
    from django.db import transaction
    from .tasks import analizar_observacion_convivencia_task
    pk = instance.pk
    transaction.on_commit(lambda: _delay_seguro(analizar_observacion_convivencia_task, pk))

@receiver(post_save, sender=Candidato)
def analizar_propuesta_candidato(sender, instance, created, **kwargs):
    """Encola el análisis de la propuesta del candidato con IA en segundo plano
    (antes se llamaba a Gemini síncrono aquí). Reutiliza la tarea Celery ya
    existente en tasks.py."""
    if not created:
        return
    from django.db import transaction
    from .tasks import analizar_propuesta_candidato_task
    pk = instance.pk
    transaction.on_commit(lambda: _delay_seguro(analizar_propuesta_candidato_task, pk))

@receiver(pre_save, sender=SolicitudDocumento)
def gestionar_notificacion_documento_listo(sender, instance, **kwargs):
    """
    Detecta si el estado de una solicitud cambia a 'LISTO_DESCARGA'
    para enviar una notificación por correo al egresado.
    """
    if not instance.pk:
        return # No hacer nada si es un objeto nuevo

    try:
        # Obtiene el estado del objeto como está guardado en la BD
        estado_anterior = SolicitudDocumento.objects.get(pk=instance.pk).estado
    except SolicitudDocumento.DoesNotExist:
        return

    # Comprueba si el estado ha cambiado a 'LISTO_DESCARGA'
    if estado_anterior != instance.estado and instance.estado == SolicitudDocumento.EstadoSolicitud.LISTO_DESCARGA:
        # Llama a la función que enviará el correo
        enviar_correo_documento_listo(instance)   

@receiver(post_save, sender=TicketSoporte)
def notificar_nuevo_ticket_a_superadmin(sender, instance, created, **kwargs):
    """
    Cuando un usuario crea un nuevo ticket, envía una notificación por correo
    al email de soporte de la plataforma, usando la configuración SMTP de la
    institución que generó el ticket.
    """
    if created:
        ticket = instance
        institucion = ticket.institucion
        asunto = f"[HALU Soporte] Nuevo Ticket Creado: [{ticket.ticket_id}]"
        
        # Construimos la URL absoluta al detalle del ticket en el panel de superadmin
        from django.contrib.sites.models import Site
        domain = Site.objects.get_current().domain
        protocol = 'https' if not settings.DEBUG else 'http'
        # CORRECCIÓN: Apuntamos a la URL que ahora está en la app 'finanzas'
        url_ticket = reverse('finanzas:superadmin_ticket_detail', kwargs={'ticket_id': ticket.ticket_id})
        url_absoluta = f"{protocol}://{domain}{url_ticket}"

        context = {
            'ticket': ticket,
            'url_absoluta': url_absoluta,
        }
        
        mensaje_html = render_to_string('gestion_academica/email/notificacion_nuevo_ticket.html', context)
        
        # --- INICIO DE LA LÓGICA DE ENVÍO MULTI-INSTITUCIÓN ---
        try:
            if not settings.SOFTWARE_CONTACT_EMAIL:
                logger.error("No se puede enviar notificación de ticket: SOFTWARE_CONTACT_EMAIL no está definido en settings.py.")
                return

            from admisiones.utils import enviar_correo_dinamico as _enviar_correo
            ok = _enviar_correo(
                institucion=institucion,
                asunto=asunto,
                destinatarios=[settings.SOFTWARE_CONTACT_EMAIL],
                html_content=mensaje_html,
            )
            if ok:
                logger.info("Notificación para el ticket %s enviada a %s.", ticket.ticket_id, settings.SOFTWARE_CONTACT_EMAIL)
            else:
                logger.warning("No se pudo enviar notificación para ticket %s (sin canal de correo configurado en %s).", ticket.ticket_id, institucion.nombre)

        except Exception as e:
            logger.error("FALLO CRÍTICO al enviar notificación por correo para el ticket %s: %s", ticket.ticket_id, e, exc_info=True)
        # --- FIN DE LA LÓGICA DE ENVÍO ---
        # 
@receiver(post_save, sender=RegistroAsistencia)
def crear_registros_asistencia_por_clase(sender, instance, created, **kwargs):
    """
    Cuando se crea un registro de asistencia general para el día, este signal
    crea automáticamente los registros de asistencia por clase para ese estudiante,
    marcando todos como 'PRESENTE' por defecto.
    """
    # Solo se activa al crear un nuevo registro y si el estado es 'Presente'
    if created and instance.estado == 'PRESENTE':
        estudiante = instance.estudiante
        fecha = instance.fecha # Usamos el DateTimeField de la asistencia general
        
        # Buscamos el horario del estudiante para ese día de la semana
        dia_semana = fecha.weekday() # Lunes=0, Martes=1, etc.
        cursos_del_dia = Curso.objects.filter(
            grado=estudiante.grado_actual,
            institucion=estudiante.institucion,  # aislamiento explícito por institución
            horarios__dia_semana=dia_semana
        ).distinct()

        fecha_dia = fecha.date()
        # Cursos del día que YA tienen registro para este estudiante hoy: los
        # excluimos para no duplicar (y para que la re-emisión de este mismo
        # signal por cada registro creado termine sin trabajo).
        ya_registrados = set(
            RegistroAsistencia.objects.filter(
                estudiante=estudiante,
                curso__in=cursos_del_dia,
                fecha__date=fecha_dia,
            ).values_list('curso_id', flat=True)
        )
        faltantes = [c for c in cursos_del_dia if c.pk not in ya_registrados]

        if faltantes:
            logger.info(f"Signal activado: creando asistencia para {estudiante} en {len(faltantes)} cursos del día.")
        for curso in faltantes:
            RegistroAsistencia.objects.create(
                estudiante=estudiante,
                curso=curso,
                estado='PRESENTE',
                fecha=fecha,
                institucion=estudiante.institucion,
                registrado_por=instance.registrado_por,
                aula=curso.aula,
            )


# ---------------------------------------------------------------------------
# Generación automática de Conceptos de Pago al crear/editar un Nivel
# ---------------------------------------------------------------------------

@receiver(post_save, sender=NivelEscolaridad)
def crear_conceptos_pago_para_nivel(sender, instance, created, **kwargs):
    """Mantiene sincronizados los ConceptoPago estándar para cada nivel.

    Al crear (o editar) un ``NivelEscolaridad``, asegura que existan en su
    institución:
      - 1 ConceptoPago de Inscripción (es_pago_inscripcion=True)
      - 1 ConceptoPago de Matrícula <año> (es_pago_matricula=True)
      - 10 ConceptoPago de Pensión Feb–Nov <año> (es_pago_pension=True)

    Es idempotente y no pisa los valores que el admin haya editado a mano.
    """
    # Evita ciclos: si la actualización viene del propio servicio (por ejemplo,
    # ajustando 'valor' en cascada), no debemos disparar de nuevo.
    if getattr(instance, "_omitir_sync_conceptos", False):
        return

    # Necesitamos institución para generar conceptos. Si por alguna razón no
    # está (no debería: el modelo tiene FK obligatoria), abortamos limpio.
    if instance.institucion_id is None:
        logger.warning(
            "NivelEscolaridad %s sin institución; no se sincronizan conceptos.",
            instance.pk,
        )
        return

    # Diferimos al commit para que la sincronización de conceptos no entre
    # en una transacción que aún puede revertirse (importación masiva,
    # vista que falla después del save, etc.).
    from django.db import transaction
    from finanzas.services import sincronizar_conceptos_de_nivel

    def _sync():
        try:
            resultado = sincronizar_conceptos_de_nivel(instance)
            logger.info(
                "ConceptoPago auto-sync por NivelEscolaridad %s (%s): %s",
                instance.pk, "creado" if created else "editado", resultado.resumen(),
            )
        except Exception as exc:  # noqa: BLE001
            # Falla NO debe romper la creación del Nivel; solo logueamos.
            logger.error(
                "Fallo al sincronizar ConceptoPago para NivelEscolaridad %s: %s",
                instance.pk, exc, exc_info=True,
            )

    transaction.on_commit(_sync)


# ---------------------------------------------------------------------------
# Permisos del portal familiar (Meta.permissions del modelo Familiar)
# ---------------------------------------------------------------------------

FAMILIAR_PORTAL_PERM_CODENAMES = (
    "acceso_portal_familiar",
    "ver_calificaciones_estudiante_familiar",
    "ver_boletin_estudiante_familiar",
    "ver_deberes_estudiante_familiar",
)


def asegurar_permisos_portal_familiar_usuario(usuario):
    """
    Asigna al usuario los permisos ligados al modelo ``Familiar`` para el portal.
    Idempotente: puede llamarse en cada guardado del perfil familiar.
    """
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType

    if not usuario or not getattr(usuario, "pk", None):
        return
    ct = ContentType.objects.get_for_model(Familiar)
    perms = list(
        Permission.objects.filter(
            content_type=ct, codename__in=FAMILIAR_PORTAL_PERM_CODENAMES
        )
    )
    if len(perms) < len(FAMILIAR_PORTAL_PERM_CODENAMES):
        logger.warning(
            "Faltan permisos Meta de Familiar en la BD (esperados %s, hallados %s). "
            "Ejecute migrate y revise contenttypes.",
            len(FAMILIAR_PORTAL_PERM_CODENAMES),
            len(perms),
        )
    if perms:
        usuario.user_permissions.add(*perms)


@receiver(post_save, sender=Familiar)
def asignar_permisos_portal_al_guardar_familiar(sender, instance, **kwargs):
    try:
        asegurar_permisos_portal_familiar_usuario(instance.usuario)
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "No se pudieron asignar permisos de portal al usuario del familiar: %s",
            exc,
        )


def _notificar_docente_cita_reunion_academica(cita_pk):
    """
    Tras crear una CitaReunion (familiar–docente): notificación en BD + WebSocket
    al usuario del docente (mismo canal `user_{pk}` que admisiones/consumers).
    """
    from django.urls import reverse
    from django.utils import timezone
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer
    from admisiones.utils import build_absolute_site_uri

    try:
        cita = CitaReunion.objects.select_related(
            "docente__usuario",
            "familiar__usuario",
            "estudiante__usuario",
            "institucion",
        ).get(pk=cita_pk)
    except CitaReunion.DoesNotExist:
        return

    docente_user = cita.docente.usuario
    est = cita.estudiante.usuario.get_full_name() or cita.estudiante.usuario.username
    fam = cita.familiar.usuario.get_full_name() or cita.familiar.usuario.username
    fh = timezone.localtime(cita.fecha_hora_inicio).strftime("%d/%m/%Y %H:%M")
    asunto_corto = (cita.asunto or "")[:100]
    mensaje = (
        f"Nueva cita con acudiente {fam} (estudiante: {est}). "
        f"Asunto: {asunto_corto}. Fecha: {fh}."
    )[:255]

    rel_url = reverse("gestion_academica:docente_mis_citas")
    enlace_abs = build_absolute_site_uri(rel_url)

    Notificacion.objects.create(
        destinatario=docente_user,
        mensaje=mensaje,
        enlace=enlace_abs,
        institucion=cita.institucion,
    )

    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        event_payload = {
            "type": "send_notification",
            "kind": "cita_reunion_academica",
            "title": "Nueva cita con familia",
            "message": mensaje,
            "url": rel_url,
            "severity": "info",
            "institucion_id": cita.institucion_id,
        }
        async_to_sync(channel_layer.group_send)(
            f"user_{docente_user.pk}",
            event_payload,
        )
    except Exception as e:  # noqa: BLE001
        logger.error("WS notificación cita reunión académica: %s", e, exc_info=True)


@receiver(post_save, sender=CitaReunion)
def notificar_docente_nueva_cita_reunion(sender, instance, created, **kwargs):
    if not created:
        return
    from django.db import transaction

    cita_pk = instance.pk
    transaction.on_commit(lambda pk=cita_pk: _notificar_docente_cita_reunion_academica(pk))


# ---------------------------------------------------------------------------
# Señales de notificación por correo (tareas Celery)
# ---------------------------------------------------------------------------

def _connect_pago_signal():
    """Conecta el signal post_save de PagoRegistrado.

    Se llama desde apps.py → ready() una vez que todas las apps están cargadas,
    evitando cualquier problema de importación circular.
    """
    from finanzas.models import PagoRegistrado
    from django.db.models.signals import post_save as _post_save

    def _enviar_correo_pago_recibido(sender, instance, created, **kwargs):
        """Encola correo de confirmación al acudiente para pagos online (Mercado Pago).

        Los pagos manuales NO se notifican aquí: la vista registrar_pago ya
        envía el recibo con PDF adjunto usando el SMTP de la institución;
        notificarlos también por esta vía duplicaría el correo.
        """
        if not created or instance.metodo_pago != 'MERCADO_PAGO':
            return
        from django.db import transaction
        from gestion_academica.tasks_notificaciones import notificar_pago_recibido

        pago_pk = instance.pk
        transaction.on_commit(
            lambda pk=pago_pk: notificar_pago_recibido.delay(pk)
        )

    # weak=False: el receptor es una función local; sin esto el recolector
    # de basura lo eliminaría al salir de esta función.
    _post_save.connect(_enviar_correo_pago_recibido, sender=PagoRegistrado,
                       weak=False,
                       dispatch_uid="gestion_academica_correo_pago_recibido")


ROL_GRUPO_MAP = {
    'docente': 'docentes',
    'estudiante': 'estudiantes',
    'coordinador': 'coordinadores',
    'familiar': 'familiares',
}


@receiver(post_save, sender=Usuario)
def sincronizar_usuario_a_grupo_por_rol(sender, instance, **kwargs):
    """Auto-assigns users to their role-based Django Group on every save."""
    from django.contrib.auth.models import Group

    rol = getattr(instance, 'rol', None) or ''
    group_name = ROL_GRUPO_MAP.get(rol)
    if not group_name:
        return
    try:
        group = Group.objects.get(name=group_name)
    except Group.DoesNotExist:
        return
    if not instance.groups.filter(pk=group.pk).exists():
        instance.groups.add(group)


@receiver(post_save, sender=RegistroAsistencia)
def enviar_correo_inasistencia(sender, instance, created, **kwargs):
    """Encola correo a acudientes cuando el estudiante falta o llega tarde."""
    if instance.estado not in ("AUSENTE", "TARDANZA"):
        return
    from django.db import transaction
    from gestion_academica.tasks_notificaciones import notificar_inasistencia

    registro_pk = instance.pk
    transaction.on_commit(
        lambda pk=registro_pk: notificar_inasistencia.delay(pk)
    )


# ---------------------------------------------------------------------------
# Notificación a familiares cuando un docente crea un deber o actividad
# ---------------------------------------------------------------------------

def _notificar_familiares_nueva_tarea(curso_pk, institucion_pk, titulo, tipo, fecha_entrega_str):
    """
    Ejecutado en on_commit: busca los familiares del grado del curso
    y les crea una Notificacion + push WebSocket en tiempo real.
    """
    try:
        from .models import Curso as _Curso, Estudiante as _Est, Familiar as _Fam, Notificacion as _Notif
        from finanzas.models import InstitucionEducativa as _Inst

        curso = _Curso.objects.select_related('materia', 'grado').get(pk=curso_pk)
        institucion = _Inst.objects.get(pk=institucion_pk)

        estudiantes = _Est.objects.filter(
            grado_actual=curso.grado,
            institucion=institucion,
            activo=True
        )
        if not estudiantes.exists():
            return

        familiares = _Fam.objects.filter(
            estudiantes_asociados__in=estudiantes,
            institucion=institucion,
        ).select_related('usuario').distinct()

        if not familiares.exists():
            return

        tipo_label = "Tarea/Deber" if tipo == "deber" else "Actividad calificable"
        materia = curso.materia.nombre_materia
        grado = curso.grado.nombre
        fecha_str = f" · Entrega: {fecha_entrega_str}" if fecha_entrega_str else ""
        mensaje = f"Nueva {tipo_label} en {materia} ({grado}): \"{titulo}\"{fecha_str}"

        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()

        bulk = []
        for familiar in familiares:
            usuario = familiar.usuario
            bulk.append(_Notif(
                destinatario=usuario,
                mensaje=mensaje,
                enlace="",
                institucion=institucion,
            ))
            try:
                async_to_sync(channel_layer.group_send)(
                    f"user_{usuario.pk}",
                    {
                        "type": "send_notification",
                        "kind": "nueva_actividad_docente",
                        "title": f"Nueva {tipo_label} — {materia}",
                        "message": mensaje,
                        "url": "",
                        "severity": "info",
                    }
                )
            except Exception:
                pass

        _Notif.objects.bulk_create(bulk)
        logger.info(
            "Notificadas %d familias por nueva %s '%s' en curso %s",
            len(bulk), tipo_label, titulo, curso_pk
        )
    except Exception:
        logger.exception("Error al notificar familiares por nueva tarea (curso=%s)", curso_pk)


@receiver(post_save, sender=Deber)
def notificar_familiares_nuevo_deber(sender, instance, created, **kwargs):
    """Avisa a los acudientes cuando el docente publica un deber."""
    if not created:
        return
    from django.db import transaction
    from gestion_academica.tasks_notificaciones import notificar_nueva_tarea_familiares
    fecha_str = instance.fecha_entrega.strftime('%d/%m/%Y') if instance.fecha_entrega else ""
    curso_pk = instance.curso_id
    inst_pk = instance.institucion_id
    titulo = instance.titulo

    def _on_commit():
        # Notificación in-app + WebSocket
        _notificar_familiares_nueva_tarea(curso_pk, inst_pk, titulo, "deber", fecha_str)
        # Correo por Celery
        notificar_nueva_tarea_familiares.delay(curso_pk, inst_pk, titulo, "deber", fecha_str)

    transaction.on_commit(_on_commit)


@receiver(post_save, sender=ActividadCalificable)
def notificar_familiares_nueva_actividad(sender, instance, created, **kwargs):
    """Avisa a los acudientes cuando el docente crea una actividad calificable."""
    if not created:
        return
    from django.db import transaction
    from gestion_academica.tasks_notificaciones import notificar_nueva_tarea_familiares
    fecha_str = (
        instance.fecha_entrega_limite.strftime('%d/%m/%Y')
        if instance.fecha_entrega_limite else ""
    )
    curso_pk = instance.curso_id
    inst_pk = instance.institucion_id
    titulo = instance.titulo

    def _on_commit():
        # Notificación in-app + WebSocket
        _notificar_familiares_nueva_tarea(curso_pk, inst_pk, titulo, "actividad", fecha_str)
        # Correo por Celery
        notificar_nueva_tarea_familiares.delay(curso_pk, inst_pk, titulo, "actividad", fecha_str)

    transaction.on_commit(_on_commit)
