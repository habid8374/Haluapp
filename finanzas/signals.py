# finanzas/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail, get_connection
from django.template.loader import render_to_string
import logging

from .models import PagoRegistrado, InstitucionEducativa, ModuloPlataforma

logger = logging.getLogger(__name__)


@receiver(post_save, sender=InstitucionEducativa)
def asignar_modulos_por_defecto(sender, instance, created, **kwargs):
    """Al CREAR una institución nueva se le asignan todos los módulos activos por
    defecto (modelo opt-out: el propietario luego DESMARCA los que el colegio no
    compró). Así ninguna institución queda sin módulos por descuido. Idempotente:
    solo actúa al crear y solo si aún no tiene módulos."""
    if not created:
        return
    try:
        if instance.modulos_contratados.exists():
            return
        activos = list(ModuloPlataforma.objects.filter(activo=True))
        if activos:
            instance.modulos_contratados.add(*activos)
    except Exception:
        logger.exception("No se pudieron asignar módulos por defecto a la institución %s", instance.pk)


@receiver(post_save, sender=PagoRegistrado)
def enviar_recibo_de_pago(sender, instance, created, **kwargs):
    """
    DESACTIVADO: el envío del recibo lo gestiona directamente la vista registrar_pago,
    que adjunta el PDF y usa las credenciales SMTP de la institución.
    Mantener este signal activo causaría que el destinatario recibiera dos correos.
    """
    pass