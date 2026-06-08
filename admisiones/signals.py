# admisiones/signals.py

from django.db import transaction
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
import logging

from django.contrib.auth import get_user_model
from django.db.models import Q

from gestion_academica.models import Notificacion

from .models import Aspirante, CitaAgendada
from .utils import (
    build_absolute_site_uri,
    crear_cuenta_cobro_matricula,
    enviar_correo_bienvenida,
    enviar_correo_cambio_estado,
    enviar_correo_confirmacion_cita,
)
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.urls import reverse

logger = logging.getLogger(__name__)


def _safe_on_commit(fn):
    """Programa ``fn`` para ejecutarse al hacer commit; si no hay transacción
    activa, lo ejecuta inmediatamente. Garantiza que los correos nunca salen
    si la transacción que los produjo termina haciendo rollback.
    """
    transaction.on_commit(fn)


@receiver(pre_save, sender=Aspirante)
def guardar_estado_original(sender, instance, **kwargs):
    if not instance.pk:
        instance._original_estado = None
        return
    try:
        instance._original_estado = Aspirante.objects.get(pk=instance.pk).estado
    except Aspirante.DoesNotExist:
        instance._original_estado = None


@receiver(post_save, sender=Aspirante)
def gestionar_notificaciones_aspirante(sender, instance, created, **kwargs):
    """
    Crea cobros y envía correos solo DESPUÉS de que la transacción haya hecho
    commit. Si la transacción se revierte, los efectos colaterales (correos)
    no se ejecutan, evitando estados inconsistentes para el postulante.

    Para procesos masivos (importación de aspirantes) la señal acepta dos
    "flags" en la instancia que permiten saltar el envío inmediato y dejarlo
    en manos del worker que está haciendo el batch:
      - ``_omitir_correo_bienvenida``: si True, no se envía el correo "creado".
      - ``_omitir_correo_estado``: si True, no se envía el correo de cambio
        de estado (útil al cambiar estados en masa).
    """
    def _safe_send(fn, aspirante_pk):
        try:
            fn()
        except Exception as exc:
            logger.error("SEÑAL: error enviando correo para aspirante %s: %s", aspirante_pk, exc, exc_info=True)

    if created:
        if getattr(instance, "_omitir_correo_bienvenida", False):
            return
        pk = instance.pk
        _safe_on_commit(lambda: _safe_send(
            lambda: enviar_correo_bienvenida(request=None, aspirante=instance), pk
        ))
        return

    if getattr(instance, "_omitir_correo_estado", False):
        return

    estado_anterior = getattr(instance, '_original_estado', None)
    if estado_anterior == instance.estado:
        return

    pk = instance.pk
    if instance.estado == Aspirante.EstadoAdmision.APROBADO_MATRICULA:
        logger.info("SEÑAL: Aspirante '%s' aprobado. Creando cobro y enviando correo...", instance)
        exito, cuenta_objeto = crear_cuenta_cobro_matricula(instance)
        if exito:
            _safe_on_commit(lambda: _safe_send(
                lambda: enviar_correo_cambio_estado(instance, cuenta_matricula=cuenta_objeto), pk
            ))
        else:
            logger.error(
                "SEÑAL: Fallo al crear cobro de matrícula para %s: %s",
                instance.pk, cuenta_objeto,
            )
        return

    logger.info("SEÑAL: Enviando correo de cambio de estado para %s.", instance.pk)
    _safe_on_commit(lambda: _safe_send(lambda: enviar_correo_cambio_estado(instance), pk))

def _notificar_cita_post_commit(cita_pk):
    """Envía correo y notificaciones (DB + WebSocket) para una cita ya persistida.

    Se invoca SIEMPRE después del commit. Re-busca la cita por PK para evitar
    trabajar con un objeto cuya transacción haya sido revertida.
    """
    try:
        cita = CitaAgendada.objects.select_related(
            "aspirante", "horario", "horario__entrevistador", "institucion",
        ).get(pk=cita_pk)
    except CitaAgendada.DoesNotExist:
        logger.info("Cita %s ya no existe al ejecutar on_commit; se omite.", cita_pk)
        return

    logger.info("SEÑAL (CitaAgendada): Enviando correo de confirmación para '%s'.", cita.aspirante)
    try:
        enviar_correo_confirmacion_cita(cita)
    except Exception as e:
        logger.error("Error enviando correo de confirmación de cita %s: %s", cita_pk, e, exc_info=True)

    try:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        horario = cita.horario
        tipo_txt = horario.get_tipo_cita_display()
        fecha_txt = horario.fecha_hora_inicio.strftime("%d/%m/%Y %H:%M")
        aspirante = cita.aspirante
        nombre_asp = f"{aspirante.nombres} {aspirante.apellidos}".strip()
        partes = [f"{tipo_txt}: {nombre_asp}.", f"Fecha y hora: {fecha_txt}."]
        if horario.entrevistador_id:
            ev = horario.entrevistador
            nombre_ev = (ev.get_full_name() or ev.get_username() or "").strip()
            if nombre_ev:
                partes.append(f"Responsable: {nombre_ev}.")
        mensaje = " ".join(partes)
        url = reverse("admisiones:detalle_aspirante", kwargs={"pk": aspirante.pk})
        enlace_abs = build_absolute_site_uri(url)

        User = get_user_model()
        institucion = cita.institucion
        staff_users_qs = (
            User.objects.filter(
                Q(is_superuser=True)
                | Q(is_staff=True, institucion_asociada_id=institucion.pk)
            ).distinct()
        )

        to_create = []
        user_ids_ws = []
        for u in staff_users_qs.iterator(chunk_size=200):
            to_create.append(
                Notificacion(
                    destinatario=u,
                    mensaje=mensaje[:255],
                    enlace=enlace_abs,
                    institucion=institucion,
                )
            )
            user_ids_ws.append(u.pk)
        if to_create:
            Notificacion.objects.bulk_create(to_create)

        event_payload = {
            "type": "send_notification",
            "kind": "cita_nueva",
            "title": "Nueva cita de admisión",
            "message": mensaje,
            "url": url,
            "severity": "info",
            "institucion_id": cita.institucion_id,
        }
        for uid in user_ids_ws:
            async_to_sync(channel_layer.group_send)(f"user_{uid}", event_payload)
    except Exception as e:
        logger.error("Error al enviar notificación de cita en tiempo real: %s", e, exc_info=True)


@receiver(post_save, sender=CitaAgendada)
def notificar_creacion_de_cita(sender, instance, created, **kwargs):
    if not created:
        return
    cita_pk = instance.pk
    _safe_on_commit(lambda: _notificar_cita_post_commit(cita_pk))