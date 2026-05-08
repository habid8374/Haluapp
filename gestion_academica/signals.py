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

from .models import Calificacion, ArchivoPlanAcademico, Notificacion, AnotacionObservador, Usuario, Candidato, TicketSoporte, RegistroAsistencia, Curso
from finanzas.models import InstitucionEducativa

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
        genai.configure(api_key=settings.GOOGLE_API_KEY)
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
        api_key = getattr(settings, 'GOOGLE_API_KEY', None)
        if not api_key:
            print("ADVERTENCIA: GOOGLE_API_KEY no está configurada. No se puede analizar la observación.")
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
            # Lógica de notificación para coordinadores...
        
        # Usamos update() para evitar un bucle infinito en el signal
        AnotacionObservador.objects.filter(pk=anotacion.pk).update(
            tipo_situacion_ia=anotacion.tipo_situacion_ia,
            analisis_ia=anotacion.analisis_ia,
            acciones_protocolo_ia=anotacion.acciones_protocolo_ia,
            requiere_revision=anotacion.requiere_revision
        )
    
    except Exception as e:
        print(f"ERROR CRÍTICO en el signal de Halu Sentinel: {e}")

@receiver(post_save, sender=Candidato)
def analizar_propuesta_candidato(sender, instance, created, **kwargs):
    if not created:
        return

    try:
        genai.configure(api_key=settings.GOOGLE_API_KEY)
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