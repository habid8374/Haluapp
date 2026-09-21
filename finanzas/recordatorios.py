"""Recordatorios de pago (correo) para cuentas por cobrar próximas a vencer
o ya vencidas. Lógica compartida entre el comando de gestión (todas las
instituciones, vía Celery Beat) y el botón manual "Enviar recordatorios
ahora" (solo la institución del usuario) — para no duplicar la lógica de
envío entre los dos como pasó históricamente con la mora.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from admisiones.utils import enviar_correo_dinamico

logger = logging.getLogger(__name__)


def enviar_recordatorios_pago(cuentas_qs):
    """Envía el correo de recordatorio correspondiente (próximo vencimiento
    a 3 días, o ya vencida) para cada cuenta del queryset que lo necesite hoy.

    Usa SIEMPRE el canal propio de la institución de esa cuenta (Brevo si lo
    tiene configurado, si no SMTP) — nunca un canal compartido entre
    instituciones (ver regla crítica de credenciales en CLAUDE.md).

    Devuelve {'enviados': int, 'sin_email': int, 'sin_canal': set(nombres)}.
    """
    today = timezone.now().date()
    domain = Site.objects.get_current().domain
    protocol = 'http' if settings.DEBUG else 'https'
    portal_url = f"{protocol}://{domain}{reverse('finanzas:mi_estado_de_cuenta')}"

    enviados = 0
    sin_email = 0
    sin_canal = set()

    for cuenta in cuentas_qs.select_related('institucion', 'estudiante__usuario'):
        # Ya se le envió un recordatorio de esta cuenta hoy (el envío
        # automático de la madrugada y el botón manual podrían coincidir
        # el mismo día): no mandar el correo dos veces.
        if cuenta.ultimo_recordatorio_pago_enviado == today:
            continue

        institucion = cuenta.institucion
        tiene_brevo = bool(getattr(institucion, 'brevo_api_key', '') or '')
        tiene_smtp = bool(institucion.email_host_user and institucion.email_host_password)
        if not tiene_brevo and not tiene_smtp:
            sin_canal.add(institucion.nombre)
            continue

        tipo_notificacion = None
        if cuenta.estado == 'PENDIENTE' and cuenta.fecha_vencimiento_especifica == (today + timedelta(days=3)):
            tipo_notificacion = 'proximo_vencimiento'
        elif cuenta.estado == 'VENCIDO':
            tipo_notificacion = 'vencido'
        if not tipo_notificacion:
            continue

        estudiante = cuenta.estudiante
        email_destinatario = getattr(estudiante, 'email_acudiente', None) or (
            estudiante.usuario.email if estudiante and estudiante.usuario else None
        )
        if not email_destinatario:
            sin_email += 1
            continue

        asunto = (
            f"Recordatorio de Pago Próximo - {institucion.nombre}"
            if tipo_notificacion == 'proximo_vencimiento'
            else f"Aviso de Saldo Vencido - {institucion.nombre}"
        )
        html_content = render_to_string('finanzas/emails/recordatorio_pago.html', {
            'cuenta': cuenta,
            'institucion': institucion,
            'tipo_recordatorio': tipo_notificacion,
            'portal_url': portal_url,
        })

        try:
            exito = enviar_correo_dinamico(
                institucion=institucion,
                asunto=asunto,
                destinatarios=[email_destinatario],
                html_content=html_content,
            )
        except Exception as exc:  # nunca romper el lote por un correo
            logger.error(
                "enviar_recordatorios_pago: falló cuenta=%s destinatario=%s: %s",
                cuenta.pk, email_destinatario, exc,
            )
            exito = False

        if exito:
            enviados += 1
            cuenta.ultimo_recordatorio_pago_enviado = today
            cuenta.save(update_fields=['ultimo_recordatorio_pago_enviado'])
        logger.info(
            "enviar_recordatorios_pago: cuenta=%s institucion=%s tipo=%s exito=%s",
            cuenta.pk, institucion.pk, tipo_notificacion, exito,
        )

    return {'enviados': enviados, 'sin_email': sin_email, 'sin_canal': sin_canal}
