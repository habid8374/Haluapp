# en gestion_academica/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from decimal import Decimal
from django.db.models.signals import pre_save
import google.generativeai as genai
from django.conf import settings
from .utils import enviar_correo_documento_listo
from .models import SolicitudDocumento
import json
from django.template.loader import render_to_string
from django.core.mail import EmailMessage, get_connection

from .models import Calificacion, ArchivoPlanAcademico, Notificacion, AnotacionObservador, Usuario, Candidato, TicketSoporte, RegistroAsistencia, Curso, NivelEscolaridad, Familiar, CitaReunion, CasoConvivencia, InvolucradoCaso
from finanzas.models import InstitucionEducativa
from finanzas.institucion_credentials import google_api_key as get_inst_google_api_key

import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Calificacion)
def sugerir_material_de_refuerzo(sender, instance, created, **kwargs):
    """
    Si una calificación es baja, llama a la IA para generar un consejo
    Y busca material de refuerzo, luego crea una notificación completa.
    """
    calificacion = instance
    estudiante = calificacion.estudiante
    institucion = estudiante.institucion
    nota_minima = getattr(institucion, 'nota_minima_aprobacion', Decimal('3.0'))

    # Solo actuar si la nota es baja y numérica
    if calificacion.valor_numerico is None or calificacion.valor_numerico >= nota_minima:
        return

    actividad = calificacion.actividad_calificable
    
    # --- INICIO DE LA MODIFICACIÓN ---

    # 1. Generar el consejo personalizado con la IA
    consejo_ia = "" # Valor por defecto en caso de que la IA falle
    try:
        api_key = get_inst_google_api_key(institucion)
        if not api_key:
            raise ValueError("Institución sin google_api_key")
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        prompt = (
            f"Actúa como un tutor amigable y positivo llamado HALU. Un estudiante de '{estudiante.grado_actual}' "
            f"obtuvo una calificación baja de '{calificacion.valor_numerico}' en la materia de '{actividad.curso.materia.nombre_materia}' "
            f"sobre el tema '{actividad.titulo}'. "
            "Genera un consejo corto en español (máximo 150 palabras) con 2 o 3 pasos de estudio concretos y accionables. "
            "El tono debe ser alentador, nunca regañes."
        )
        response = model.generate_content(prompt)
        consejo_ia = response.text
    except Exception as e:
        print(f"ERROR al generar consejo de IA: {e}")
        consejo_ia = "Te recomendamos fuertemente repasar los temas de la actividad y consultar con tu docente. ¡Tú puedes mejorar!"

    # 2. Buscar material de refuerzo (lógica que ya teníamos)
    recursos_sugeridos = ArchivoPlanAcademico.objects.filter(
        institucion=institucion,
        temas_relacionados__icontains=actividad.titulo
    ).distinct()

    # 3. Preparar el mensaje y el enlace final
    if recursos_sugeridos.exists():
        enlace = reverse('gestion_academica:ver_material_refuerzo', kwargs={'actividad_pk': actividad.pk})
        mensaje = f"HALU tiene un plan de estudio para ti sobre '{actividad.titulo}'."
    else:
        enlace = reverse('gestion_academica:dashboard_estudiante')
        mensaje = f"HALU tiene un consejo para ayudarte a mejorar en '{actividad.titulo}'."

    # 4. Crear la notificación con TODA la información
    Notificacion.objects.create(
        destinatario=estudiante.usuario,
        mensaje=mensaje,
        enlace=enlace,
        consejo_ia=consejo_ia,  # Asumimos que tu modelo Notificacion tiene este campo
        institucion=institucion
    )


@receiver(post_save, sender=AnotacionObservador)
def analizar_observacion_convivencia(sender, instance, created, **kwargs):
    """
    Signal que usa la IA para clasificar la situación de convivencia.
    Utiliza un prompt que fuerza una respuesta JSON para mayor robustez.
    """
    if not created or instance.tipo_situacion_ia is not None:
        return

    anotacion = instance
    texto_a_analizar = anotacion.descripcion

    try:
        api_key = get_inst_google_api_key(anotacion.institucion)
        if not api_key:
            print("ADVERTENCIA: la institución no tiene google_api_key. No se puede analizar la observación.")
            return

        genai.configure(api_key=api_key)
        
        generation_config = genai.types.GenerationConfig(response_mime_type="application/json")
        model = genai.GenerativeModel('gemini-2.5-flash', generation_config=generation_config)
        
        prompt = f"""
        Actúa como un experto en la Ley 1620 de Colombia. Analiza la siguiente anotación y responde ÚNICAMENTE con un objeto JSON válido que siga esta estructura:
        {{
            "tipo_situacion": "TIPO I" | "TIPO II" | "TIPO III" | "NINGUNO",
            "resumen": "Un resumen objetivo y conciso de los hechos.",
            "protocolo_sugerido": "Una lista numerada de acciones a seguir según el protocolo." | "No se requiere protocolo.",
            "requiere_revision": true | false
        }}

        Anotación: "{texto_a_analizar}"
        """

        response = model.generate_content(prompt)
        ai_data = json.loads(response.text)
        
        tipo_situacion = ai_data.get('tipo_situacion', 'NINGUNO').upper()
        
        # Actualizamos los campos de la anotación
        anotacion.tipo_situacion_ia = tipo_situacion
        anotacion.analisis_ia = ai_data.get('resumen', 'No se generó resumen.')
        anotacion.acciones_protocolo_ia = ai_data.get('protocolo_sugerido', 'No se sugirieron acciones.')
        anotacion.requiere_revision = ai_data.get('requiere_revision', False)
        
        if tipo_situacion in ['TIPO II', 'TIPO III']:
            anotacion.requiere_revision = True

        # Usamos update() para evitar un bucle infinito en el signal
        AnotacionObservador.objects.filter(pk=anotacion.pk).update(
            tipo_situacion_ia=anotacion.tipo_situacion_ia,
            analisis_ia=anotacion.analisis_ia,
            acciones_protocolo_ia=anotacion.acciones_protocolo_ia,
            requiere_revision=anotacion.requiere_revision
        )

        # ── Apertura automática de Caso de Convivencia (Tipo II / III) ──
        if tipo_situacion in ['TIPO II', 'TIPO III']:
            from django.db import transaction
            from django.utils import timezone as _tz
            from datetime import timedelta

            def _crear_caso():
                try:
                    # Calcular fecha límite legal
                    if tipo_situacion == 'TIPO III':
                        # 2 horas hábiles (urgente)
                        fecha_limite = _tz.now() + timedelta(hours=2)
                    else:
                        # 5 días hábiles ≈ 7 días calendario
                        fecha_limite = _tz.now() + timedelta(days=7)

                    caso = CasoConvivencia.objects.create(
                        institucion=anotacion.institucion,
                        tipo_situacion=tipo_situacion,
                        anotacion_origen=anotacion,
                        descripcion_detalle=anotacion.descripcion,
                        protocolo_ia=ai_data.get('protocolo_sugerido', ''),
                        fecha_limite=fecha_limite,
                    )
                    # Registrar al estudiante como involucrado (rol por defecto: VICTIMA)
                    InvolucradoCaso.objects.create(
                        caso=caso,
                        estudiante=anotacion.estudiante,
                        rol=CasoConvivencia.RolInvolucrado.VICTIMA,
                    )
                    # Notificar a coordinadores de la institución
                    coordinadores = Usuario.objects.filter(
                        institucion_asociada=anotacion.institucion,
                        is_staff=True,
                        rol__in=['coordinador', 'administrador'],
                    )
                    urgencia = "⚠️ URGENTE — " if tipo_situacion == 'TIPO III' else ""
                    url_caso = reverse('gestion_academica:detalle_caso_convivencia', kwargs={'pk': caso.pk})
                    for coord in coordinadores:
                        Notificacion.objects.create(
                            destinatario=coord,
                            institucion=anotacion.institucion,
                            mensaje=(
                                f"{urgencia}Nuevo caso {tipo_situacion} abierto: "
                                f"{anotacion.estudiante} — Radicado {caso.radicado}"
                            ),
                            enlace=url_caso,
                        )
                    # Push WebSocket en tiempo real a coordinadores
                    try:
                        from channels.layers import get_channel_layer
                        from asgiref.sync import async_to_sync
                        channel_layer = get_channel_layer()
                        if channel_layer:
                            severity = 'danger' if tipo_situacion == 'TIPO III' else 'warning'
                            for coord in coordinadores:
                                async_to_sync(channel_layer.group_send)(
                                    f"user_{coord.pk}",
                                    {
                                        'type': 'send_notification',
                                        'kind': 'sentinel',
                                        'title': f'{urgencia}Halu Sentinel — Caso {tipo_situacion}',
                                        'message': (
                                            f"Caso {caso.radicado} abierto para "
                                            f"{anotacion.estudiante}. "
                                            f"Plazo: {fecha_limite.strftime('%d/%m %H:%M')}"
                                        ),
                                        'url': url_caso,
                                        'severity': severity,
                                    }
                                )
                    except Exception as ws_err:
                        logger.warning("WS Sentinel no disponible: %s", ws_err)

                except Exception as caso_err:
                    logger.exception("Error creando CasoConvivencia para anotación %s: %s", anotacion.pk, caso_err)

            transaction.on_commit(_crear_caso)

    except Exception as e:
        print(f"ERROR CRÍTICO en el signal de Halu Sentinel: {e}")

@receiver(post_save, sender=Candidato)
def analizar_propuesta_candidato(sender, instance, created, **kwargs):
    if not created:
        return

    try:
        api_key = get_inst_google_api_key(instance.eleccion.institucion)
        if not api_key:
            print("ADVERTENCIA: institución sin google_api_key; se omite análisis de propuesta.")
            return
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')

        prompt = (
            f"Eres un asesor electoral. Analiza esta propuesta de candidatura:\n\n"
            f"'{instance.propuesta}'\n\n"
            "Responde con:\n"
            "1. Resumen breve (máx. 2 líneas)\n"
            "2. Principales ejes temáticos (como educación, deporte, inclusión)\n"
            "3. Nivel de claridad: Alto, Medio, Bajo"
        )

        response = model.generate_content(prompt)
        texto_respuesta = response.text.strip()

        instance.analisis_ia = texto_respuesta
        instance.save(update_fields=['analisis_ia'])

    except Exception as e:
        print(f"Error con Gemini analizando propuesta: {e}")

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
            # Verificamos que el correo de soporte global esté configurado
            if not settings.SOFTWARE_CONTACT_EMAIL:
                logger.error("No se puede enviar notificación de ticket: SOFTWARE_CONTACT_EMAIL no está definido en settings.py.")
                return

            # Verificamos que la institución tenga credenciales de correo
            if not (institucion.email_host_user and institucion.email_host_password):
                logger.warning(f"No se pudo enviar notificación para el ticket {ticket.ticket_id} porque la institución '{institucion.nombre}' no tiene credenciales de correo configuradas.")
                return

            # Creamos una conexión SMTP dinámica con las credenciales de la institución
            connection = get_connection(
                host=institucion.email_host,
                port=institucion.email_port,
                username=institucion.email_host_user,
                password=institucion.email_host_password,
                use_tls=institucion.email_use_tls
            )
            
            remitente = f'"{institucion.nombre} (Plataforma HALU)" <{institucion.email_host_user}>'
            
            email = EmailMessage(
                subject=asunto,
                body=mensaje_html,
                from_email=remitente,
                to=[settings.SOFTWARE_CONTACT_EMAIL], # Envía al correo de soporte global
                connection=connection # Usa la conexión dinámica
            )
            email.content_subtype = "html"
            email.send(fail_silently=False)
            logger.info(f"Notificación para el ticket {ticket.ticket_id} enviada exitosamente a {settings.SOFTWARE_CONTACT_EMAIL}.")

        except Exception as e:
            logger.error(f"FALLO CRÍTICO al enviar notificación por correo para el ticket {ticket.ticket_id}: {e}", exc_info=True)
        # --- FIN DE LA LÓGICA DE ENVÍO ---  
        #     
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
            horarios__dia_semana=dia_semana
        ).distinct()

        logger.info(f"Signal activado: Creando registros de asistencia para {estudiante} en {cursos_del_dia.count()} cursos del día.")

        for curso in cursos_del_dia:
            # Usamos get_or_create para no duplicar registros si por alguna razón ya existiera
            registro, fue_creado = RegistroAsistencia.objects.get_or_create(
                estudiante=estudiante,
                curso=curso,
                fecha__date=fecha.date(), # Buscamos por la parte de la fecha para evitar duplicados en el mismo día
                defaults={
                    'estado': 'PRESENTE',
                    'fecha': fecha, # Guardamos el timestamp completo
                    'institucion': estudiante.institucion,
                    'registrado_por': instance.registrado_por, # Quien registró la asistencia general
                    'aula': curso.aula, # Asignamos el aula del curso
                }
            )
            if fue_creado:
                logger.info(f"Creado registro de asistencia para {estudiante} en el curso '{curso}'.")


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
        """Encola correo de confirmación de pago al acudiente cuando se crea un pago nuevo."""
        if not created:
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
