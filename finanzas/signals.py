# finanzas/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail, get_connection
from django.template.loader import render_to_string
import logging

from .models import PagoRegistrado

logger = logging.getLogger(__name__)


@receiver(post_save, sender=PagoRegistrado)
def enviar_recibo_de_pago(sender, instance, created, **kwargs):
    """
    Se dispara al crear un nuevo PagoRegistrado. Envía un correo de confirmación
    usando las credenciales SMTP específicas de la institución.
    """
    if not created:
        return

    pago = instance
    institucion = pago.institucion
    
    # 1. Verificar si la institución tiene credenciales para enviar correos
    if not (institucion.email_host_user and institucion.email_host_password):
        logger.warning(f"No se envió recibo para el pago {pago.id}. La institución '{institucion.nombre}' no tiene credenciales SMTP configuradas.")
        return

    # 2. Encontrar el correo del destinatario
    email_destinatario = None
    estudiante = pago.estudiante
    familiar = estudiante.familiares.first()
    
    if familiar and familiar.usuario.email:
        email_destinatario = familiar.usuario.email
    elif estudiante.usuario.email:
        email_destinatario = estudiante.usuario.email
            
    if not email_destinatario:
        logger.info(f"No se envió recibo para el pago {pago.id} porque no se encontró un email de destinatario.")
        return
    
    # 3. Preparar el contenido del correo
    asunto = f"Confirmación de Pago - Recibo #{pago.id} - {institucion.nombre}"
    contexto_correo = {'pago': pago, 'institucion': institucion}
    html_mensaje = render_to_string('finanzas/emails/email_recibo.html', contexto_correo)
    
    try:
        # 4. Crear una conexión SMTP dinámica
        connection = get_connection(
            host=institucion.email_host,
            port=institucion.email_port,
            username=institucion.email_host_user,
            password=institucion.email_host_password,
            use_tls=institucion.email_use_tls
        )

        # 5. Enviar el correo
        send_mail(
            subject=asunto,
            message='', # El HTML tiene prioridad
            from_email=f"{institucion.nombre} <{institucion.email_host_user}>",
            recipient_list=[email_destinatario],
            html_message=html_mensaje,
            connection=connection,
        )
        logger.info(f"Recibo de pago {pago.id} enviado exitosamente a {email_destinatario}.")

    except Exception as e:
        logger.error(f"FALLO al enviar recibo de pago {pago.id} para la institución '{institucion.nombre}': {e}", exc_info=True)