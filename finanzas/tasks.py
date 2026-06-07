"""Tareas Celery del módulo finanzas.

Contiene:
- run_health_check_task: health-check del super-admin.
- enviar_avisos_cobro_masivo_task: envío en segundo plano de avisos de cobro
  a acudientes/estudiantes tras una facturación masiva.
"""
from __future__ import annotations

import logging
import os
import traceback
from io import BytesIO

from celery import shared_task
from django.conf import settings
from django.core.mail import get_connection, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="finanzas.run_health_check",
    soft_time_limit=120,
    time_limit=150,
    max_retries=0,  # no queremos reintentos automáticos en un diagnóstico manual
)
def run_health_check_task(self, ejecucion_id: int, institucion_id: int | None = None):
    """Ejecuta el health-check completo y guarda el resultado.

    Notifica progreso en vivo al grupo WS ``healthcheck_<ejecucion_id>``,
    para que el dashboard de mantenimiento renderice cada paso en tiempo real.
    """
    from finanzas.models import EjecucionHealthCheck
    from admisiones.services.health_check import (
        ejecutar_health_check,
        NIVEL_ERR,
        NIVEL_WARN,
    )

    try:
        ejecucion = EjecucionHealthCheck.objects.get(pk=ejecucion_id)
    except EjecucionHealthCheck.DoesNotExist:
        logger.error("run_health_check_task: ejecucion id=%s no existe.", ejecucion_id)
        return

    ejecucion.estado = EjecucionHealthCheck.Estado.EJECUTANDO
    ejecucion.task_id = self.request.id or ""
    ejecucion.save(update_fields=["estado", "task_id"])

    eventos_serializados: list = []
    pasos_completados = 0

    def _ws_notify(payload: dict):
        """Envía un evento al grupo WS de esta ejecución (no levanta si falla)."""
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            layer = get_channel_layer()
            if layer is None:
                return
            async_to_sync(layer.group_send)(
                f"healthcheck_{ejecucion_id}",
                {"type": "healthcheck.event", "payload": payload},
            )
        except Exception:
            logger.debug("WS notify falló (se ignora).", exc_info=True)

    def progreso_callback(evento):
        """Callback invocado por el service en cada evento generado."""
        nonlocal pasos_completados
        eventos_serializados.append(evento.to_dict())
        if evento.paso and evento.nivel == "INFO" and "/" in evento.paso:
            # "X/8" → pasos_completados = X (el evento INFO marca el inicio del paso X)
            try:
                pasos_completados = int(evento.paso.split("/")[0])
            except (ValueError, AttributeError):
                pass
        _ws_notify({
            "tipo": "evento",
            "evento": evento.to_dict(),
            "pasos_completados": pasos_completados,
            "pasos_totales": 8,
        })

    try:
        resultado = ejecutar_health_check(
            institucion_id=institucion_id,
            progreso_callback=progreso_callback,
        )

        # Estado final según conteo
        if resultado.errores > 0:
            estado_final = EjecucionHealthCheck.Estado.ERROR
        elif resultado.warnings > 0:
            estado_final = EjecucionHealthCheck.Estado.WARN
        else:
            estado_final = EjecucionHealthCheck.Estado.OK

        ejecucion.estado = estado_final
        ejecucion.errores_count = resultado.errores
        ejecucion.warnings_count = resultado.warnings
        ejecucion.pasos_completados = pasos_completados
        ejecucion.eventos = eventos_serializados
        ejecucion.terminado_at = timezone.now()
        ejecucion.save()

        _ws_notify({
            "tipo": "finalizado",
            "estado": estado_final,
            "errores": resultado.errores,
            "warnings": resultado.warnings,
            "pasos_completados": pasos_completados,
            "pasos_totales": 8,
        })
        return f"Health-check #{ejecucion_id}: {estado_final}"
    except Exception as exc:
        logger.exception("run_health_check_task: excepción interna.")
        ejecucion.estado = EjecucionHealthCheck.Estado.FALLIDO
        ejecucion.error_excepcion = "".join(traceback.format_exception_only(type(exc), exc))[:5000]
        ejecucion.eventos = eventos_serializados
        ejecucion.terminado_at = timezone.now()
        ejecucion.save()
        _ws_notify({
            "tipo": "fallido",
            "estado": EjecucionHealthCheck.Estado.FALLIDO,
            "error": str(exc)[:500],
        })
        raise


def _link_callback_pdf(uri, rel):
    """Resuelve URLs de media/static a rutas del filesystem para xhtml2pdf."""
    if uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, "", 1).lstrip("/"))
    elif uri.startswith(settings.STATIC_URL):
        path = os.path.join(settings.STATIC_ROOT, uri.replace(settings.STATIC_URL, "", 1).lstrip("/"))
    else:
        return uri
    return path if os.path.isfile(path) else None


@shared_task(
    bind=True,
    name="finanzas.enviar_avisos_cobro_masivo",
    soft_time_limit=300,
    time_limit=360,
    max_retries=2,
    default_retry_delay=30,
)
def enviar_avisos_cobro_masivo_task(self, cuenta_ids: list, institucion_id: int, portal_url: str, domain: str):
    """Envía avisos de cobro con PDF adjunto a acudientes/estudiantes tras una facturación masiva.

    Reutiliza una única conexión SMTP para todo el lote.
    """
    from xhtml2pdf import pisa
    from finanzas.models import CuentaPorCobrarEstudiante, InstitucionEducativa

    institucion = InstitucionEducativa.objects.get(pk=institucion_id)

    if not (institucion.email_host_user and institucion.email_host_password):
        logger.warning(
            "enviar_avisos_cobro_masivo_task: SMTP no configurado para institución %s — no se envían correos.",
            institucion_id,
        )
        return {"enviados": 0, "sin_email": len(cuenta_ids), "errores": 0}

    cuentas = list(
        CuentaPorCobrarEstudiante.objects.filter(pk__in=cuenta_ids)
        .select_related(
            "estudiante__usuario",
            "estudiante__grado_actual",
            "concepto_pago",
            "institucion",
        )
        .prefetch_related("estudiante__familiares__usuario")
    )

    enviados = 0
    sin_email = 0
    errores = 0
    remitente = f"{institucion.nombre} <{institucion.email_host_user}>"

    try:
        connection = get_connection(
            backend="django.core.mail.backends.smtp.EmailBackend",
            host=institucion.email_host,
            port=institucion.email_port,
            username=institucion.email_host_user,
            password=institucion.email_host_password,
            use_tls=institucion.email_use_tls,
        )
        connection.open()
    except Exception as exc:
        logger.error("enviar_avisos_cobro_masivo_task: no se pudo abrir SMTP para institución %s: %s", institucion_id, exc)
        raise self.retry(exc=exc)

    for cuenta in cuentas:
        # Determinar destinatario: preferir acudiente, luego estudiante
        email_dest = None
        nombre_dest = None
        acudiente = cuenta.estudiante.familiares.first()
        if acudiente and getattr(acudiente, "usuario", None) and acudiente.usuario.email:
            email_dest = acudiente.usuario.email
            nombre_dest = acudiente.usuario.get_full_name() or cuenta.estudiante.usuario.get_full_name()
        elif cuenta.estudiante.usuario.email:
            email_dest = cuenta.estudiante.usuario.email
            nombre_dest = cuenta.estudiante.usuario.get_full_name()

        if not email_dest:
            sin_email += 1
            continue

        try:
            ctx = {
                "cuenta": cuenta,
                "estudiante": cuenta.estudiante,
                "institucion": institucion,
                "nombre_destinatario": nombre_dest or cuenta.estudiante.usuario.get_full_name(),
                "portal_url": portal_url,
                "domain": domain.rstrip("/"),
            }

            html_email = render_to_string("finanzas/emails/aviso_cobro_masivo.html", ctx)
            asunto = f"Aviso de Cobro: {cuenta.concepto_pago.nombre_concepto} — {institucion.nombre}"

            msg = EmailMultiAlternatives(
                subject=asunto,
                body="Por favor visualice este mensaje en un cliente que soporte HTML.",
                from_email=remitente,
                to=[email_dest],
                connection=connection,
            )
            msg.attach_alternative(html_email, "text/html")

            # Adjuntar PDF DIAN si existe factura electrónica validada para esta cuenta
            fe_pdf_adjunto = False
            try:
                from facturacion_electronica.models import FacturaElectronica
                fe = (
                    FacturaElectronica.objects
                    .filter(cuenta=cuenta, estado="VALIDADA", tipo="FACTURA")
                    .order_by("-fecha_creacion")
                    .first()
                )
                if fe and fe.url_pdf:
                    import urllib.request as _ur
                    pdf_dian = _ur.urlopen(fe.url_pdf, timeout=12).read()
                    nombre_fe = f"Factura_DIAN_{fe.numero or cuenta.pk}.pdf"
                    msg.attach(nombre_fe, pdf_dian, "application/pdf")
                    fe_pdf_adjunto = True
                    ctx["factura_electronica_url"] = fe.url_pdf
                    ctx["factura_numero"] = fe.numero
            except Exception as _exc_fe:
                logger.warning(
                    "No se pudo obtener PDF DIAN para cuenta %s: %s", cuenta.pk, _exc_fe
                )

            if not fe_pdf_adjunto:
                # Fallback: adjuntar la Orden de Pago interna
                from finanzas.pdf_helpers import generar_qr_base64, valor_en_letras
                pdf_ctx = {
                    **ctx,
                    "tipo_volante": f"Aviso de Cobro — {cuenta.concepto_pago.nombre_concepto}",
                    "cuentas": [cuenta],
                    "total_a_pagar": cuenta.saldo_pendiente,
                    "qr_pago": generar_qr_base64(portal_url),
                    "total_en_letras": valor_en_letras(cuenta.saldo_pendiente),
                }
                pdf_html = render_to_string("finanzas/pdfs/volante_pago.html", pdf_ctx)
                pdf_buffer = BytesIO()
                pisa_status = pisa.CreatePDF(pdf_html, dest=pdf_buffer, link_callback=_link_callback_pdf)
                if not pisa_status.err:
                    msg.attach(
                        f"Aviso_Cobro_{cuenta.pk}.pdf",
                        pdf_buffer.getvalue(),
                        "application/pdf",
                    )

            msg.send()
            enviados += 1

        except Exception as exc:
            logger.error(
                "enviar_avisos_cobro_masivo_task: error enviando a %s (cuenta %s): %s",
                email_dest, cuenta.pk, exc,
            )
            errores += 1

    try:
        connection.close()
    except Exception:
        pass

    logger.info(
        "enviar_avisos_cobro_masivo_task [inst=%s]: enviados=%s sin_email=%s errores=%s",
        institucion_id, enviados, sin_email, errores,
    )
    return {"enviados": enviados, "sin_email": sin_email, "errores": errores}
