"""Señales de la app SIMAT."""
import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='finanzas.InstitucionEducativa')
def crear_sede_principal_al_crear_institucion(sender, instance, created, **kwargs):
    """Al crear una institución, garantiza que tenga su Sede Principal.

    Idempotente (asegurar_principal no duplica). Se ejecuta tras el commit para
    no interferir con la transacción de creación de la institución.
    """
    if not created:
        return

    def _crear():
        try:
            from .models import Sede
            Sede.asegurar_principal(instance)
        except Exception:
            logger.exception("No se pudo crear la Sede Principal de la institución %s", instance.pk)

    transaction.on_commit(_crear)
