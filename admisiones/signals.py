# admisiones/signals.py

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
import logging

from .models import Aspirante, CitaAgendada
from .utils import (
    crear_cuenta_cobro_matricula,
    enviar_correo_bienvenida,
    enviar_correo_cambio_estado,
    enviar_correo_confirmacion_cita,
)
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)

@receiver(pre_save, sender=Aspirante)
def guardar_estado_original(sender, instance, **kwargs):
    if instance.pk:
        try:
            instance._original_estado = Aspirante.objects.get(pk=instance.pk).estado
        except Aspirante.DoesNotExist:
            instance._original_estado = None

@receiver(post_save, sender=Aspirante)
def gestionar_notificaciones_aspirante(sender, instance, created, **kwargs):
    """
    Gestiona el envío de correos y la creación de cobros de forma directa (síncrona).
    VERSIÓN RESTAURADA Y CON ORDEN CORREGIDO.
    """
    if created:
        enviar_correo_bienvenida(request=None, aspirante=instance)
        return

    estado_anterior = getattr(instance, '_original_estado', None)
    if estado_anterior != instance.estado:
        
        if instance.estado == Aspirante.EstadoAdmision.APROBADO_MATRICULA:
            logger.info(f"SEÑAL: Aspirante '{instance}' aprobado. Creando cobro y enviando correo...")
            
            from .utils import crear_cuenta_cobro_matricula
            
            # ▼▼▼ CORRECCIÓN CLAVE AQUÍ ▼▼▼
            # Desempaquetamos la tupla que devuelve la función.
            exito, cuenta_objeto = crear_cuenta_cobro_matricula(instance)

            if exito:
                # Ahora le pasamos el objeto de la cuenta, no la tupla.
                enviar_correo_cambio_estado(instance, cuenta_matricula=cuenta_objeto)
            else:
                # La variable 'cuenta_objeto' aquí contiene el mensaje de error.
                logger.error(f"SEÑAL: Fallo al crear cobro de matrícula para {instance.pk}: {cuenta_objeto}")
            # ▲▲▲ FIN DE LA CORRECCIÓN ▲▲▲
        
        else:
            logger.info(f"SEÑAL: Enviando correo de cambio de estado para {instance.pk}.")
            enviar_correo_cambio_estado(instance)
            

@receiver(post_save, sender=CitaAgendada)
def notificar_creacion_de_cita(sender, instance, created, **kwargs):
    if created:
        # 1. La lógica de envío de correo se mantiene
        logger.info(f"SEÑAL (CitaAgendada): Enviando correo de confirmación para '{instance.aspirante}'.")
        enviar_correo_confirmacion_cita(instance)
        
        # 2. Lógica de notificación en tiempo real CORREGIDA
        try:
            channel_layer = get_channel_layer()
            if channel_layer is not None:
                # ▼▼▼ CORRECCIÓN CLAVE AQUÍ ▼▼▼
                # Obtenemos los nombres y apellidos desde el aspirante asociado (instance.aspirante)
                mensaje = (
                    f"Nueva cita agendada: {instance.aspirante.nombres} {instance.aspirante.apellidos} "
                    f"para el {instance.horario.fecha_hora_inicio.strftime('%d/%m a las %H:%M')}."
                )
                # ▲▲▲ FIN DE LA CORRECCIÓN ▲▲▲
                
                async_to_sync(channel_layer.group_send)(
                    'admin_notifications',
                    {
                        'type': 'send_notification',
                        'message': mensaje
                    }
                )
        except Exception as e:
            logger.error(f"Error al enviar notificación de cita en tiempo real: {e}")