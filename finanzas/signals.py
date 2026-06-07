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
    DESACTIVADO: el envío del recibo lo gestiona directamente la vista registrar_pago,
    que adjunta el PDF y usa las credenciales SMTP de la institución.
    Mantener este signal activo causaría que el destinatario recibiera dos correos.
    """
    pass