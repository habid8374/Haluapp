# admisiones/utils.py

import logging
from django.conf import settings
from django.core.mail import get_connection, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.contrib.sites.models import Site
from django.utils import timezone
from datetime import timedelta, date
from django.db import transaction

from .models import Aspirante, CitaAgendada
from gestion_academica.models import Estudiante, Usuario
from finanzas.models import CuentaPorCobrarEstudiante, ConceptoPago

logger = logging.getLogger(__name__)

# --- FUNCIÓN CENTRAL DE ENVÍO ---
def enviar_correo_dinamico(institucion, asunto, destinatarios, html_content, texto_plano='', connection=None):
    if not isinstance(destinatarios, list):
        destinatarios = [destinatarios]

    if connection is None and institucion and institucion.email_host_user and institucion.email_host_password:
        try:
            connection = get_connection(
                host=institucion.email_host, port=institucion.email_port,
                username=institucion.email_host_user, password=institucion.email_host_password,
                use_tls=institucion.email_use_tls
            )
        except Exception as e:
            logger.error(f"Fallo al crear conexión SMTP para {institucion.nombre}. Error: {e}")
            return False

    remitente = f"{institucion.nombre} <{institucion.email_host_user}>" if institucion.email_host_user else settings.DEFAULT_FROM_EMAIL

    try:
        msg = EmailMultiAlternatives(
            subject=asunto,
            body=texto_plano or "Este es un correo HTML.",
            from_email=remitente,
            to=destinatarios,
            connection=connection
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)
        return True
    except Exception as e:
        logger.error(f"ERROR FATAL al enviar correo a {', '.join(destinatarios)}: {e}", exc_info=True)
        return False

# --- FUNCIONES DE NOTIFICACIÓN ---

def enviar_correo_bienvenida(request, aspirante):
    try:
        domain = Site.objects.get_current().domain
        protocol = 'https' if not settings.DEBUG else 'http'
        url_path = aspirante.get_portal_url()
        portal_url_completa = f"{protocol}://{domain}{url_path}"
    except Exception as e:
        logger.error(f"Fallo al generar URL para correo de bienvenida del aspirante {aspirante.id}: {e}")
        return False

    context = {'aspirante': aspirante, 'portal_url': portal_url_completa}
    html_content = render_to_string('emails/bienvenida_aspirante.html', context)
    asunto = f"Bienvenido al Proceso de Admisión - {aspirante.institucion.nombre}"
    
    return enviar_correo_dinamico(
        institucion=aspirante.institucion,
        asunto=asunto,
        destinatarios=[aspirante.email_contacto],
        html_content=html_content
    )


def enviar_correo_cambio_estado(aspirante, cuenta_matricula=None):
    """
    Envía un correo de notificación de cambio de estado.
    Si se proporciona una cuenta de matrícula, incluye un enlace de pago directo.
    VERSIÓN DEFINITIVA Y CORREGIDA.
    """
    institucion = aspirante.institucion
    domain = Site.objects.get_current().domain
    protocol = 'https' if not settings.DEBUG else 'http'
    
    context = {'aspirante': aspirante, 'institucion': institucion}
    
    # CASO 1: Aprobado para pagar matrícula
    if aspirante.estado == 'APROBADO_MATRICULA' and cuenta_matricula:
        asunto = f"¡Felicitaciones! Estás listo para matricularte - {institucion.nombre}"
        template_name = 'emails/cambio_estado_aspirante.html'
        
        # ▼▼▼ CORRECCIÓN CLAVE AQUÍ ▼▼▼
        # Apuntamos a la URL correcta en la app 'admisiones' y con el nombre correcto.
        url_pago = reverse('admisiones:crear_preferencia_mercadopago', kwargs={
            'cuenta_por_cobrar_id': cuenta_matricula.pk
        })
        context['enlace_pago_matricula'] = f"{protocol}://{domain}{url_pago}"
        # ▲▲▲ FIN DE LA CORRECCIÓN ▲▲▲

    # CASO 2: Admitido
    elif aspirante.estado == 'ADMITIDO':
        asunto = f"¡Has sido Admitido/a! - {institucion.nombre}"
        template_name = 'emails/aspirante_admitido.html'
        portal_url = reverse('admisiones:portal_postulante_pagado', kwargs={'token': aspirante.access_token})
        context['portal_pagado_url'] = f"{protocol}://{domain}{portal_url}"
    
    # CASO 3: Otro cambio de estado
    else:
        asunto = f"Actualización de tu Proceso: {aspirante.get_estado_display()}"
        template_name = 'emails/cambio_estado_aspirante.html'
        portal_url = reverse('admisiones:portal_postulante', kwargs={'token': aspirante.access_token})
        context['portal_url'] = f"{protocol}://{domain}{portal_url}"

    html_content = render_to_string(template_name, context)
    
    return enviar_correo_dinamico(
        institucion=institucion,
        asunto=asunto,
        destinatarios=[aspirante.email_contacto],
        html_content=html_content
    )


def enviar_correo_confirmacion_cita(cita):
    context = {'aspirante': cita.aspirante, 'cita': cita}
    institucion_cita = cita.aspirante.institucion
    
    html_content_padre = render_to_string('emails/confirmacion_cita.html', context)
    asunto_padre = f"Confirmación de Cita de Admisión - {institucion_cita.nombre}"
    enviar_correo_dinamico(institucion=institucion_cita, asunto=asunto_padre, destinatarios=[cita.aspirante.email_contacto], html_content=html_content_padre)

    if cita.horario.entrevistador and cita.horario.entrevistador.email:
        html_content_entrevistador = render_to_string('emails/confirmacion_cita.html', context)
        asunto_entrevistador = f"Nueva Cita Agendada: {cita.aspirante}"
        enviar_correo_dinamico(institucion=institucion_cita, asunto=asunto_entrevistador, destinatarios=[cita.horario.entrevistador.email], html_content=html_content_entrevistador)

# --- FUNCIONES DE LÓGICA FINANCIERA ---

def crear_cuenta_cobro_inscripcion(aspirante):
    """
    Crea la cuenta de cobro para la INSCRIPCIÓN, buscando el concepto
    específico para el Nivel de Escolaridad del aspirante.
    VERSIÓN CORREGIDA Y DEFINITIVA.
    """
    if not aspirante.requiere_pago_inscripcion:
        logger.info(f"Aspirante {aspirante.pk} no requiere pago de inscripción.")
        return None

    if not aspirante.estudiante_creado:
        logger.error(f"Error crítico: Aspirante {aspirante.pk} sin perfil de estudiante para asignarle el cobro.")
        return None

    try:
        grado_aspirado = aspirante.grado_aspira
        nivel_escolar = getattr(grado_aspirado, 'nivel_escolaridad', None)

        if not nivel_escolar:
            logger.warning(f"El grado '{grado_aspirado}' no tiene un Nivel de Escolaridad asignado. No se generó cobro para {aspirante}.")
            return None

        # ▼▼▼ INICIO DE LA CORRECCIÓN CLAVE ▼▼▼
        # Buscamos el Concepto de Pago que sea de Inscripción Y que coincida
        # con el Nivel de Escolaridad del aspirante.
        concepto_inscripcion = ConceptoPago.objects.get(
            institucion=aspirante.institucion,
            es_pago_inscripcion=True,
            nivel_escolaridad=nivel_escolar # <-- Filtro por Nivel de Escolaridad añadido
        )
        # ▲▲▲ FIN DE LA CORRECCIÓN CLAVE ▲▲▲

        cuenta, created = CuentaPorCobrarEstudiante.objects.get_or_create(
            estudiante=aspirante.estudiante_creado,
            concepto_pago=concepto_inscripcion,
            defaults={
                # Usamos el valor del ConceptoPago específico, que es más preciso.
                'monto_asignado': concepto_inscripcion.valor,
                'institucion': aspirante.institucion,
                'fecha_vencimiento_especifica': timezone.now().date() + timedelta(days=15)
            }
        )
        
        logger.info(f"Cuenta de inscripción {'creada' if created else 'ya existente'} para el estudiante preliminar {aspirante.estudiante_creado.pk}.")
        return cuenta

    except (ConceptoPago.DoesNotExist, ConceptoPago.MultipleObjectsReturned):
        logger.error(f"Error de Configuración: No se encontró (o hay duplicados) un Concepto de Pago marcado como 'Es pago de Inscripción' PARA EL NIVEL '{nivel_escolar}'.")
        return None
    except Exception as e:
        logger.error(f"Error creando CxC de inscripción para aspirante {aspirante.pk}: {e}", exc_info=True)
        return None

def crear_cuenta_cobro_matricula(aspirante):
    """
    Crea la cuenta de cobro para la MATRÍCULA y devuelve el objeto de la cuenta.
    VERSIÓN DEFINITIVA: Devuelve el objeto 'cuenta' en caso de éxito.
    """
    try:
        institucion = aspirante.institucion
        grado_aspirado = aspirante.grado_aspira

        if not (grado_aspirado and grado_aspirado.nivel_escolaridad):
            mensaje = f"El grado '{grado_aspirado}' no tiene un Nivel de Escolaridad asignado."
            logger.warning(f"{mensaje} No se generó el cobro para {aspirante}.")
            return False, mensaje

        nivel_escolar = grado_aspirado.nivel_escolaridad

        try:
            concepto_matricula = ConceptoPago.objects.get(
                institucion=institucion,
                es_pago_matricula=True, # Búsqueda precisa por el campo booleano
                nivel_escolaridad=nivel_escolar
            )
        except (ConceptoPago.DoesNotExist, ConceptoPago.MultipleObjectsReturned):
            mensaje = f"Error de Configuración: No se encontró (o hay duplicados) un Concepto de Pago marcado como 'Es pago de matrícula' Y asignado al Nivel de Escolaridad '{nivel_escolar}'."
            logger.error(mensaje)
            return False, mensaje

        fecha_vencimiento = timezone.now().date() + timedelta(days=30)

        cuenta, created = CuentaPorCobrarEstudiante.objects.get_or_create(
            aspirante=aspirante,
            concepto_pago=concepto_matricula,
            defaults={
                'monto_asignado': nivel_escolar.valor_matricula_estandar,
                'institucion': institucion,
                'fecha_vencimiento_especifica': fecha_vencimiento,
                'estudiante': aspirante.estudiante_creado # Vinculamos también al estudiante preliminar
            }
        )
        
        if created:
            logger.info(f"Cuenta de matrícula creada para {aspirante}.")
        else:
            logger.info(f"La cuenta de matrícula para {aspirante} ya existía.")
        
        # --- CORRECCIÓN CLAVE AQUÍ ---
        # En lugar de un mensaje, devolvemos el objeto de la cuenta que se creó o encontró.
        return True, cuenta
        # --- FIN DE LA CORRECCIÓN ---

    except Exception as e:
        logger.error(f"Error creando CxC de matrícula para aspirante {aspirante.pk}: {e}", exc_info=True)
        return False, f"Error inesperado: {e}"