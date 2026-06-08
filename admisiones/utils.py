# admisiones/utils.py

import logging
from typing import NamedTuple, Optional

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


# ---------------------------------------------------------------------------
# Tipos de resultado para flujos de inscripción / cobro
# ---------------------------------------------------------------------------

# Motivos por los cuales NO se pudo crear la cuenta de cobro de inscripción.
# Los que están en MOTIVOS_WARNING corresponden a problemas de configuración
# que el operador puede resolver (no son errores técnicos del sistema).
MOTIVOS_WARNING = frozenset({
    "sin_nivel_escolaridad",
    "sin_concepto_configurado",
    "concepto_duplicado",
    "sin_estudiante",
})


class ResultadoCobroInscripcion(NamedTuple):
    """Resultado estructurado de intentar crear la cuenta de cobro de inscripción.

    Atributos:
        cuenta:        ``CuentaPorCobrarEstudiante`` creada/encontrada, o ``None``.
        motivo_falla:  Etiqueta corta del motivo (None si fue éxito).
        mensaje:       Texto legible para mostrar al operador.
    """

    cuenta: Optional["CuentaPorCobrarEstudiante"]
    motivo_falla: Optional[str]
    mensaje: str

    @property
    def es_exito(self) -> bool:
        return self.cuenta is not None

    @property
    def es_warning(self) -> bool:
        """True si la falla es un problema de configuración accionable
        por el operador (no un error técnico inesperado).
        """
        return self.motivo_falla in MOTIVOS_WARNING


class ResultadoInscripcion(NamedTuple):
    """Resultado de ``Aspirante.procesar_inscripcion_completa()``."""

    aspirante: "Aspirante"
    cobro_inscripcion: ResultadoCobroInscripcion


def build_absolute_site_uri(path: str) -> str:
    """
    URL absoluta para enlaces persistidos (p. ej. Notificacion.enlace) sin HttpRequest.
    """
    site = Site.objects.get_current()
    domain = (site.domain or "").strip()
    path = path if path.startswith("/") else f"/{path}"
    if domain.startswith("http://") or domain.startswith("https://"):
        base = domain.rstrip("/")
    else:
        scheme = "http" if getattr(settings, "DEBUG", False) else "https"
        base = f"{scheme}://{domain}".rstrip("/")
    return f"{base}{path}"


# --- FUNCIÓN CENTRAL DE ENVÍO ---
def _email_valido(direccion: str) -> bool:
    """Valida que una dirección de correo tenga formato básico correcto."""
    import re
    if not direccion or not isinstance(direccion, str):
        return False
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', direccion.strip()))


def enviar_correo_dinamico(institucion, asunto, destinatarios, html_content, texto_plano='', connection=None):
    if not isinstance(destinatarios, list):
        destinatarios = [destinatarios]

    # Filtrar destinatarios con email inválido
    validos = [d for d in destinatarios if _email_valido(d)]
    invalidos = [d for d in destinatarios if not _email_valido(d)]
    if invalidos:
        logger.warning(
            "enviar_correo_dinamico: se omiten %d dirección(es) inválida(s): %s",
            len(invalidos), invalidos,
        )
    if not validos:
        logger.warning("enviar_correo_dinamico: ningún destinatario válido, no se envía.")
        return False
    destinatarios = validos

    if not institucion:
        logger.error("enviar_correo_dinamico: se requiere institución.")
        return False

    if not (institucion.email_host_user and institucion.email_host_password):
        logger.warning(
            "enviar_correo_dinamico: SMTP no configurado para la institución %s; no se envía el correo.",
            getattr(institucion, "nombre", institucion),
        )
        return False

    if connection is None:
        try:
            connection = get_connection(
                backend='django.core.mail.backends.smtp.EmailBackend',
                host=institucion.email_host, port=institucion.email_port,
                username=institucion.email_host_user, password=institucion.email_host_password,
                use_tls=institucion.email_use_tls,
                timeout=15,
            )
        except Exception as e:
            logger.error(f"Fallo al crear conexión SMTP para {institucion.nombre}. Error: {e}")
            return False

    remitente = f"{institucion.nombre} <{institucion.email_host_user}>"

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

def enviar_correo_bienvenida(request, aspirante, connection=None):
    """Envía el correo de bienvenida del aspirante.

    Acepta ``connection`` opcional para reutilizar una conexión SMTP en
    procesos batch (importación masiva). Si no se pasa, ``enviar_correo_dinamico``
    abrirá y cerrará una conexión nueva.

    Si el aspirante tiene una cuenta de inscripción ya generada, agregamos al
    contexto del template:
      * ``cuenta_inscripcion``      : objeto ``CuentaPorCobrarEstudiante``
      * ``monto_inscripcion``       : monto pendiente (``saldo_pendiente``)
      * ``enlace_pago_inscripcion`` : URL absoluta + token para pagar directo
    De esta forma el postulante recibe en el primer correo el botón
    "Pagar inscripción" y no tiene que entrar al portal a buscarlo.
    """
    try:
        portal_url_completa = build_absolute_site_uri(aspirante.get_portal_url())
    except Exception as e:
        logger.error(
            "Fallo al generar URL para correo de bienvenida del aspirante %s: %s",
            aspirante.id, e,
        )
        return False

    context = {
        'aspirante': aspirante,
        'portal_url': portal_url_completa,
        'cuenta_inscripcion': None,
        'monto_inscripcion': None,
        'enlace_pago_inscripcion': None,
    }

    cuenta_inscripcion = getattr(aspirante, 'cuenta_pago_inscripcion', None)
    if cuenta_inscripcion and cuenta_inscripcion.estado not in ('PAGADO', 'ANULADO'):
        try:
            url_pago = reverse(
                'admisiones:crear_preferencia_mercadopago',
                kwargs={'cuenta_por_cobrar_id': cuenta_inscripcion.pk},
            )
            context.update({
                'cuenta_inscripcion': cuenta_inscripcion,
                'monto_inscripcion': cuenta_inscripcion.saldo_pendiente,
                'enlace_pago_inscripcion': build_absolute_site_uri(
                    f"{url_pago}?token={aspirante.access_token}"
                ),
            })
        except Exception as e:
            logger.warning(
                "No se pudo generar enlace de pago de inscripción para aspirante %s: %s",
                aspirante.id, e,
            )

    html_content = render_to_string('emails/bienvenida_aspirante.html', context)
    asunto = f"Bienvenido al Proceso de Admisión - {aspirante.institucion.nombre}"

    return enviar_correo_dinamico(
        institucion=aspirante.institucion,
        asunto=asunto,
        destinatarios=[aspirante.email_contacto],
        html_content=html_content,
        connection=connection,
    )


def enviar_correo_cambio_estado(aspirante, cuenta_matricula=None):
    """
    Envía un correo de notificación de cambio de estado.
    Si se proporciona una cuenta de matrícula, incluye un enlace de pago directo.

    NOTA: Usa build_absolute_site_uri() para construir URLs —
    esa función ya maneja el caso en que Site.domain contenga el protocolo
    completo (ej. "https://mi-tunel.trycloudflare.com"), evitando URLs
    malformadas como "http://https://...".
    """
    institucion = aspirante.institucion
    context = {'aspirante': aspirante, 'institucion': institucion}

    # CASO 1: Aprobado para pagar matrícula
    if aspirante.estado == 'APROBADO_MATRICULA' and cuenta_matricula:
        asunto = f"¡Felicitaciones! Estás listo para matricularte - {institucion.nombre}"
        template_name = 'emails/cambio_estado_aspirante.html'

        # El enlace debe llevar el token del aspirante: la vista de creación de
        # preferencia de Mercado Pago lo exige para autorizar la operación.
        url_pago = reverse(
            'admisiones:crear_preferencia_mercadopago',
            kwargs={'cuenta_por_cobrar_id': cuenta_matricula.pk},
        )
        context['enlace_pago_matricula'] = build_absolute_site_uri(
            f"{url_pago}?token={aspirante.access_token}"
        )

    # CASO 2: Admitido
    elif aspirante.estado == 'ADMITIDO':
        asunto = f"¡Has sido Admitido/a! - {institucion.nombre}"
        template_name = 'emails/aspirante_admitido.html'
        portal_url = reverse(
            'admisiones:portal_postulante_pagado',
            kwargs={'token': aspirante.access_token},
        )
        context['portal_pagado_url'] = build_absolute_site_uri(portal_url)

    # CASO 3: Otro cambio de estado
    else:
        asunto = f"Actualización de tu Proceso: {aspirante.get_estado_display()}"
        template_name = 'emails/cambio_estado_aspirante.html'
        portal_url = reverse(
            'admisiones:portal_postulante',
            kwargs={'token': aspirante.access_token},
        )
        context['portal_url'] = build_absolute_site_uri(portal_url)

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

def crear_cuenta_cobro_inscripcion(aspirante) -> ResultadoCobroInscripcion:
    """Crea la cuenta de cobro de inscripción para el aspirante.

    Devuelve un ``ResultadoCobroInscripcion`` con detalle del éxito o motivo
    de falla. Esto permite que las vistas e importaciones masivas reporten
    al operador problemas de configuración (p. ej. falta el ``ConceptoPago``)
    en lugar de fallar silenciosamente.
    """
    if not aspirante.requiere_pago_inscripcion:
        logger.info("Aspirante %s no requiere pago de inscripción.", aspirante.pk)
        return ResultadoCobroInscripcion(
            cuenta=None,
            motivo_falla="no_requiere",
            mensaje="El aspirante no requiere pago de inscripción.",
        )

    if not aspirante.estudiante_creado:
        msg = (
            f"El aspirante {aspirante.pk} no tiene perfil de estudiante asociado, "
            "no se puede crear la cuenta de inscripción."
        )
        logger.error(msg)
        return ResultadoCobroInscripcion(
            cuenta=None, motivo_falla="sin_estudiante", mensaje=msg,
        )

    grado_aspirado = aspirante.grado_aspira
    nivel_escolar = getattr(grado_aspirado, "nivel_escolaridad", None)
    if not nivel_escolar:
        msg = (
            f"El grado '{grado_aspirado}' no tiene un Nivel de Escolaridad asignado. "
            "Asigna el nivel desde Gestión Académica → Grados antes de inscribir aspirantes."
        )
        logger.warning("Aspirante %s: %s", aspirante.pk, msg)
        return ResultadoCobroInscripcion(
            cuenta=None, motivo_falla="sin_nivel_escolaridad", mensaje=msg,
        )

    try:
        concepto_inscripcion = ConceptoPago.objects.get(
            institucion=aspirante.institucion,
            es_pago_inscripcion=True,
            nivel_escolaridad=nivel_escolar,
        )
    except ConceptoPago.DoesNotExist:
        msg = (
            f"No existe un Concepto de Pago marcado como 'Es pago de Inscripción' "
            f"para el Nivel '{nivel_escolar}' en esta institución. "
            "Configúralo en Finanzas → Conceptos de Pago."
        )
        logger.error("Aspirante %s: %s", aspirante.pk, msg)
        return ResultadoCobroInscripcion(
            cuenta=None, motivo_falla="sin_concepto_configurado", mensaje=msg,
        )
    except ConceptoPago.MultipleObjectsReturned:
        msg = (
            f"Hay MÁS DE UN Concepto de Pago marcado como 'Es pago de Inscripción' "
            f"para el Nivel '{nivel_escolar}' en esta institución. "
            "Deja activo solo uno desde Finanzas → Conceptos de Pago."
        )
        logger.error("Aspirante %s: %s", aspirante.pk, msg)
        return ResultadoCobroInscripcion(
            cuenta=None, motivo_falla="concepto_duplicado", mensaje=msg,
        )

    try:
        cuenta, created = CuentaPorCobrarEstudiante.objects.get_or_create(
            estudiante=aspirante.estudiante_creado,
            concepto_pago=concepto_inscripcion,
            defaults={
                "monto_asignado": concepto_inscripcion.valor,
                "institucion": aspirante.institucion,
                "fecha_vencimiento_especifica": timezone.now().date() + timedelta(days=15),
            },
        )
        logger.info(
            "Cuenta de inscripción %s para el estudiante preliminar %s.",
            "creada" if created else "ya existente",
            aspirante.estudiante_creado.pk,
        )
        return ResultadoCobroInscripcion(
            cuenta=cuenta,
            motivo_falla=None,
            mensaje=("Cuenta de inscripción creada." if created else "Cuenta de inscripción ya existía."),
        )
    except Exception as e:
        msg = f"Error inesperado al crear la cuenta de inscripción: {e}"
        logger.error("Aspirante %s: %s", aspirante.pk, msg, exc_info=True)
        return ResultadoCobroInscripcion(
            cuenta=None, motivo_falla="error_inesperado", mensaje=msg,
        )

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
                'monto_asignado': concepto_matricula.valor,
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