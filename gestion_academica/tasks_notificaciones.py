# gestion_academica/tasks_notificaciones.py
"""
Tareas Celery para notificaciones por correo a acudientes y estudiantes.

Tareas:
  - notificar_pago_recibido(pago_id)
  - notificar_inasistencia(registro_asistencia_id)
  - notificar_boletin_disponible(estudiante_id, periodo_id)
  - notificar_factura_electronica(factura_id)
  - notificar_recibo_pago_manual(pago_id)
"""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers de plantillas HTML inline
# ---------------------------------------------------------------------------

def _html_pago(institucion_nombre: str, estudiante_nombre: str,
               concepto: str, valor: str, fecha: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:32px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:16px;overflow:hidden;
                    box-shadow:0 4px 24px rgba(0,0,0,.10);max-width:560px;width:100%;">
        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#16a34a 0%,#15803d 100%);
                     padding:32px 36px;text-align:center;">
            <div style="display:inline-block;background:rgba(255,255,255,.18);
                        border-radius:50%;width:56px;height:56px;line-height:56px;
                        font-size:28px;margin-bottom:12px;">&#10003;</div>
            <h1 style="color:#ffffff;margin:0;font-size:22px;font-weight:700;">
              Pago Recibido Exitosamente
            </h1>
            <p style="color:#bbf7d0;margin:6px 0 0;font-size:14px;">
              {institucion_nombre}
            </p>
          </td>
        </tr>
        <!-- Body -->
        <tr>
          <td style="padding:32px 36px;">
            <p style="color:#374151;font-size:15px;margin:0 0 16px;">
              Estimado/a acudiente,
            </p>
            <p style="color:#374151;font-size:15px;margin:0 0 24px;">
              Le informamos que se ha registrado un pago correctamente para el estudiante
              <strong>{estudiante_nombre}</strong>.
            </p>
            <!-- Tarjeta de detalle -->
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;
                          margin-bottom:24px;">
              <tr>
                <td style="padding:20px 24px;">
                  <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <td style="color:#6b7280;font-size:12px;text-transform:uppercase;
                                 letter-spacing:.6px;padding-bottom:4px;">Concepto</td>
                    </tr>
                    <tr>
                      <td style="color:#111827;font-size:17px;font-weight:700;
                                 padding-bottom:16px;">{concepto}</td>
                    </tr>
                    <tr>
                      <td style="color:#6b7280;font-size:12px;text-transform:uppercase;
                                 letter-spacing:.6px;padding-bottom:4px;">Valor pagado</td>
                    </tr>
                    <tr>
                      <td style="color:#16a34a;font-size:26px;font-weight:800;
                                 padding-bottom:16px;">{valor}</td>
                    </tr>
                    <tr>
                      <td style="color:#6b7280;font-size:12px;text-transform:uppercase;
                                 letter-spacing:.6px;padding-bottom:4px;">Fecha</td>
                    </tr>
                    <tr>
                      <td style="color:#374151;font-size:15px;font-weight:600;">{fecha}</td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
            <p style="color:#6b7280;font-size:13px;margin:0;">
              Conserve este mensaje como comprobante. Si tiene alguna duda, comuníquese
              con la administración de <strong>{institucion_nombre}</strong>.
            </p>
          </td>
        </tr>
        <!-- Footer -->
        <tr>
          <td style="background:#f8fafc;padding:18px 36px;text-align:center;
                     border-top:1px solid #e2e8f0;">
            <p style="color:#94a3b8;font-size:12px;margin:0;">
              Este es un mensaje automático de <strong>Halu Plataforma Escolar</strong>.
              No responda a este correo.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _html_inasistencia(institucion_nombre: str, estudiante_nombre: str,
                       tipo_evento: str, fecha_str: str,
                       materia: str | None) -> str:
    color_header = "#dc2626" if tipo_evento == "ausencia" else "#d97706"
    icono = "&#9888;" if tipo_evento == "ausencia" else "&#9200;"
    titulo = "Ausencia Registrada" if tipo_evento == "ausencia" else "Tardanza Registrada"
    descripcion = "estuvo <strong>ausente</strong>" if tipo_evento == "ausencia" else "llegó con <strong>tardanza</strong>"
    materia_fila = (
        f"""<tr>
              <td style="color:#6b7280;font-size:12px;text-transform:uppercase;
                         letter-spacing:.6px;padding-bottom:4px;">Materia / Clase</td>
            </tr>
            <tr>
              <td style="color:#374151;font-size:15px;font-weight:600;
                         padding-bottom:16px;">{materia}</td>
            </tr>"""
        if materia else ""
    )
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:32px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:16px;overflow:hidden;
                    box-shadow:0 4px 24px rgba(0,0,0,.10);max-width:560px;width:100%;">
        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,{color_header} 0%,{color_header}cc 100%);
                     padding:32px 36px;text-align:center;">
            <div style="display:inline-block;background:rgba(255,255,255,.18);
                        border-radius:50%;width:56px;height:56px;line-height:56px;
                        font-size:28px;margin-bottom:12px;">{icono}</div>
            <h1 style="color:#ffffff;margin:0;font-size:22px;font-weight:700;">
              {titulo}
            </h1>
            <p style="color:rgba(255,255,255,.8);margin:6px 0 0;font-size:14px;">
              {institucion_nombre}
            </p>
          </td>
        </tr>
        <!-- Body -->
        <tr>
          <td style="padding:32px 36px;">
            <p style="color:#374151;font-size:15px;margin:0 0 16px;">
              Estimado/a acudiente,
            </p>
            <p style="color:#374151;font-size:15px;margin:0 0 24px;">
              Le informamos que el/la estudiante <strong>{estudiante_nombre}</strong>
              {descripcion} el día de hoy en <strong>{institucion_nombre}</strong>.
            </p>
            <!-- Tarjeta de detalle -->
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="background:#fef9f9;border:1px solid #fecaca;border-radius:10px;
                          margin-bottom:24px;">
              <tr>
                <td style="padding:20px 24px;">
                  <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <td style="color:#6b7280;font-size:12px;text-transform:uppercase;
                                 letter-spacing:.6px;padding-bottom:4px;">Estudiante</td>
                    </tr>
                    <tr>
                      <td style="color:#111827;font-size:17px;font-weight:700;
                                 padding-bottom:16px;">{estudiante_nombre}</td>
                    </tr>
                    <tr>
                      <td style="color:#6b7280;font-size:12px;text-transform:uppercase;
                                 letter-spacing:.6px;padding-bottom:4px;">Fecha</td>
                    </tr>
                    <tr>
                      <td style="color:#374151;font-size:15px;font-weight:600;
                                 padding-bottom:16px;">{fecha_str}</td>
                    </tr>
                    {materia_fila}
                    <tr>
                      <td style="color:#6b7280;font-size:12px;text-transform:uppercase;
                                 letter-spacing:.6px;padding-bottom:4px;">Novedad</td>
                    </tr>
                    <tr>
                      <td style="color:{color_header};font-size:15px;font-weight:700;">
                        {titulo}
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
            <p style="color:#6b7280;font-size:13px;margin:0;">
              Si esta información no es correcta o el/la estudiante tiene justificación,
              comuníquese con la dirección de <strong>{institucion_nombre}</strong>.
            </p>
          </td>
        </tr>
        <!-- Footer -->
        <tr>
          <td style="background:#f8fafc;padding:18px 36px;text-align:center;
                     border-top:1px solid #e2e8f0;">
            <p style="color:#94a3b8;font-size:12px;margin:0;">
              Mensaje automático de <strong>Halu Plataforma Escolar</strong>.
              No responda a este correo.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _html_boletin(institucion_nombre: str, estudiante_nombre: str,
                  periodo_nombre: str, enlace_plataforma: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:32px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:16px;overflow:hidden;
                    box-shadow:0 4px 24px rgba(0,0,0,.10);max-width:560px;width:100%;">
        <!-- Header -->
        <tr>
          <td style="background:linear-gradient(135deg,#4f46e5 0%,#7c3aed 100%);
                     padding:32px 36px;text-align:center;">
            <div style="display:inline-block;background:rgba(255,255,255,.18);
                        border-radius:50%;width:56px;height:56px;line-height:56px;
                        font-size:28px;margin-bottom:12px;">&#128196;</div>
            <h1 style="color:#ffffff;margin:0;font-size:22px;font-weight:700;">
              Boletín de Calificaciones Disponible
            </h1>
            <p style="color:#c7d2fe;margin:6px 0 0;font-size:14px;">
              {institucion_nombre}
            </p>
          </td>
        </tr>
        <!-- Body -->
        <tr>
          <td style="padding:32px 36px;">
            <p style="color:#374151;font-size:15px;margin:0 0 16px;">
              Estimado/a acudiente,
            </p>
            <p style="color:#374151;font-size:15px;margin:0 0 24px;">
              El boletín de calificaciones del período <strong>{periodo_nombre}</strong>
              para el/la estudiante <strong>{estudiante_nombre}</strong> ya está disponible
              en la plataforma.
            </p>
            <!-- CTA -->
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="background:linear-gradient(135deg,#eef2ff,#ede9fe);
                          border:1px solid #c7d2fe;border-radius:12px;margin-bottom:28px;">
              <tr>
                <td style="padding:24px 28px;text-align:center;">
                  <p style="color:#4338ca;font-size:14px;margin:0 0 16px;">
                    Ingrese a la plataforma para consultar el boletín detallado
                    con todas las calificaciones por materia.
                  </p>
                  <a href="{enlace_plataforma}"
                     style="display:inline-block;background:linear-gradient(135deg,#4f46e5,#7c3aed);
                            color:#ffffff;text-decoration:none;font-size:15px;font-weight:700;
                            padding:12px 32px;border-radius:8px;letter-spacing:.3px;">
                    Ver Boletín Ahora
                  </a>
                </td>
              </tr>
            </table>
            <p style="color:#6b7280;font-size:13px;margin:0;">
              Si necesita ayuda para acceder a la plataforma, comuníquese con la
              administración de <strong>{institucion_nombre}</strong>.
            </p>
          </td>
        </tr>
        <!-- Footer -->
        <tr>
          <td style="background:#f8fafc;padding:18px 36px;text-align:center;
                     border-top:1px solid #e2e8f0;">
            <p style="color:#94a3b8;font-size:12px;margin:0;">
              Mensaje automático de <strong>Halu Plataforma Escolar</strong>.
              No responda a este correo.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Tarea 1: Pago recibido
# ---------------------------------------------------------------------------

@shared_task(
    name="gestion_academica.notificar_pago_recibido",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def notificar_pago_recibido(self, pago_id: int) -> None:
    """Notifica por correo a los familiares cuando se registra un nuevo pago."""
    from finanzas.models import PagoRegistrado
    from admisiones.utils import enviar_correo_dinamico

    try:
        pago = (
            PagoRegistrado.objects
            .select_related(
                "estudiante__usuario",
                "cuenta__concepto_pago",
                "institucion",
            )
            .get(pk=pago_id)
        )
    except PagoRegistrado.DoesNotExist:
        logger.warning("notificar_pago_recibido: pago %s no encontrado.", pago_id)
        return

    estudiante = pago.estudiante
    if not estudiante:
        logger.warning("notificar_pago_recibido: pago %s sin estudiante.", pago_id)
        return

    institucion = pago.institucion

    # Nombre del estudiante
    estudiante_nombre = (
        estudiante.usuario.get_full_name() or estudiante.usuario.username
        if hasattr(estudiante, "usuario") and estudiante.usuario
        else f"Estudiante #{estudiante.pk}"
    )

    # Concepto del pago
    concepto = getattr(pago.cuenta.concepto_pago, "nombre_concepto", "Pago")
    valor = f"${pago.valor_pagado:,.2f}"
    fecha_str = pago.fecha_pago.strftime("%d/%m/%Y") if pago.fecha_pago else "—"

    # Familiares con email
    destinatarios = list(
        estudiante.familiares
        .select_related("usuario")
        .exclude(usuario__email="")
        .exclude(usuario__email__isnull=True)
        .values_list("usuario__email", flat=True)
    )

    if not destinatarios:
        logger.info(
            "notificar_pago_recibido: estudiante %s no tiene familiares con email.",
            estudiante.pk,
        )
        return

    html = _html_pago(
        institucion_nombre=institucion.nombre,
        estudiante_nombre=estudiante_nombre,
        concepto=concepto,
        valor=valor,
        fecha=fecha_str,
    )
    asunto = (
        f"Pago registrado para {estudiante_nombre} — {institucion.nombre}"
    )

    try:
        enviar_correo_dinamico(
            institucion=institucion,
            asunto=asunto,
            destinatarios=destinatarios,
            html_content=html,
        )
        logger.info(
            "notificar_pago_recibido: correo enviado para pago %s a %s destinatario(s).",
            pago_id, len(destinatarios),
        )
    except Exception as exc:
        logger.error(
            "notificar_pago_recibido: error enviando correo para pago %s: %s",
            pago_id, exc, exc_info=True,
        )
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Tarea 2: Inasistencia / Tardanza
# ---------------------------------------------------------------------------

@shared_task(
    name="gestion_academica.notificar_inasistencia",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def notificar_inasistencia(self, registro_asistencia_id: int) -> None:
    """Notifica por correo a familiares cuando el estudiante falta o llega tarde."""
    from gestion_academica.models import RegistroAsistencia
    from admisiones.utils import enviar_correo_dinamico

    try:
        registro = (
            RegistroAsistencia.objects
            .select_related(
                "estudiante__usuario",
                "curso__materia",
                "institucion",
            )
            .get(pk=registro_asistencia_id)
        )
    except RegistroAsistencia.DoesNotExist:
        logger.warning(
            "notificar_inasistencia: registro %s no encontrado.", registro_asistencia_id
        )
        return

    if registro.estado not in ("AUSENTE", "TARDANZA"):
        return

    estudiante = registro.estudiante
    institucion = registro.institucion

    estudiante_nombre = (
        estudiante.usuario.get_full_name() or estudiante.usuario.username
        if hasattr(estudiante, "usuario") and estudiante.usuario
        else f"Estudiante #{estudiante.pk}"
    )

    tipo_evento = "ausencia" if registro.estado == "AUSENTE" else "tardanza"

    from django.utils import timezone as tz
    fecha_str = tz.localtime(registro.fecha).strftime("%d/%m/%Y")

    materia = None
    if registro.curso and hasattr(registro.curso, "materia") and registro.curso.materia:
        materia = registro.curso.materia.nombre_materia

    # Familiares con email
    destinatarios = list(
        estudiante.familiares
        .select_related("usuario")
        .exclude(usuario__email="")
        .exclude(usuario__email__isnull=True)
        .values_list("usuario__email", flat=True)
    )

    if not destinatarios:
        logger.info(
            "notificar_inasistencia: estudiante %s no tiene familiares con email.",
            estudiante.pk,
        )
        return

    html = _html_inasistencia(
        institucion_nombre=institucion.nombre,
        estudiante_nombre=estudiante_nombre,
        tipo_evento=tipo_evento,
        fecha_str=fecha_str,
        materia=materia,
    )
    tipo_label = "Ausencia" if tipo_evento == "ausencia" else "Tardanza"
    asunto = (
        f"{tipo_label} de {estudiante_nombre} — {institucion.nombre}"
    )

    try:
        enviar_correo_dinamico(
            institucion=institucion,
            asunto=asunto,
            destinatarios=destinatarios,
            html_content=html,
        )
        logger.info(
            "notificar_inasistencia: correo enviado para registro %s a %s destinatario(s).",
            registro_asistencia_id, len(destinatarios),
        )
    except Exception as exc:
        logger.error(
            "notificar_inasistencia: error enviando correo para registro %s: %s",
            registro_asistencia_id, exc, exc_info=True,
        )
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Tarea 3: Boletín disponible
# ---------------------------------------------------------------------------

@shared_task(
    name="gestion_academica.notificar_boletin_disponible",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def notificar_boletin_disponible(self, estudiante_id: int, periodo_id: int) -> None:
    """Notifica por correo a familiares que el boletín del período está disponible."""
    from gestion_academica.models import Estudiante, PeriodoAcademico
    from admisiones.utils import enviar_correo_dinamico, build_absolute_site_uri
    from django.urls import reverse

    try:
        estudiante = (
            Estudiante.objects
            .select_related("usuario", "institucion")
            .get(pk=estudiante_id)
        )
    except Estudiante.DoesNotExist:
        logger.warning(
            "notificar_boletin_disponible: estudiante %s no encontrado.", estudiante_id
        )
        return

    try:
        periodo = PeriodoAcademico.objects.get(pk=periodo_id)
    except PeriodoAcademico.DoesNotExist:
        logger.warning(
            "notificar_boletin_disponible: periodo %s no encontrado.", periodo_id
        )
        return

    institucion = estudiante.institucion

    estudiante_nombre = (
        estudiante.usuario.get_full_name() or estudiante.usuario.username
        if hasattr(estudiante, "usuario") and estudiante.usuario
        else f"Estudiante #{estudiante.pk}"
    )

    # Intentamos construir el enlace al dashboard del estudiante/familiar
    try:
        rel_url = reverse("gestion_academica:dashboard_estudiante")
        enlace = build_absolute_site_uri(rel_url)
    except Exception:
        enlace = "https://app.haluescolar.com"

    # Familiares con email
    destinatarios = list(
        estudiante.familiares
        .select_related("usuario")
        .exclude(usuario__email="")
        .exclude(usuario__email__isnull=True)
        .values_list("usuario__email", flat=True)
    )

    # También notificamos al propio estudiante si tiene email
    if (
        hasattr(estudiante, "usuario")
        and estudiante.usuario
        and estudiante.usuario.email
    ):
        destinatarios.append(estudiante.usuario.email)

    # Deduplicar
    destinatarios = list(dict.fromkeys(destinatarios))

    if not destinatarios:
        logger.info(
            "notificar_boletin_disponible: estudiante %s sin destinatarios con email.",
            estudiante_id,
        )
        return

    html = _html_boletin(
        institucion_nombre=institucion.nombre,
        estudiante_nombre=estudiante_nombre,
        periodo_nombre=str(periodo),
        enlace_plataforma=enlace,
    )
    asunto = (
        f"Boletín {periodo.nombre} disponible — {estudiante_nombre} — {institucion.nombre}"
    )

    try:
        enviar_correo_dinamico(
            institucion=institucion,
            asunto=asunto,
            destinatarios=destinatarios,
            html_content=html,
        )
        logger.info(
            "notificar_boletin_disponible: correo enviado para estudiante %s, periodo %s, "
            "%s destinatario(s).",
            estudiante_id, periodo_id, len(destinatarios),
        )
    except Exception as exc:
        logger.error(
            "notificar_boletin_disponible: error enviando correo: %s",
            exc, exc_info=True,
        )
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Helpers de plantillas — factura electrónica y recibo manual
# ---------------------------------------------------------------------------

def _html_factura(institucion_nombre: str, estudiante_nombre: str,
                  numero: str, concepto: str, valor: str,
                  fecha: str, url_pdf: str, cufe: str) -> str:
    boton_pdf = (
        f"""<a href="{url_pdf}"
               style="display:inline-block;background:linear-gradient(135deg,#4f46e5,#7c3aed);
                      color:#ffffff;text-decoration:none;font-size:14px;font-weight:700;
                      padding:11px 28px;border-radius:8px;letter-spacing:.3px;margin-top:8px;">
              Ver / Descargar Factura
            </a>"""
        if url_pdf else
        "<p style='color:#6b7280;font-size:13px;margin:0;'>El PDF estará disponible próximamente en la plataforma.</p>"
    )
    cufe_fila = (
        f"""<tr>
              <td style="color:#6b7280;font-size:11px;text-transform:uppercase;
                         letter-spacing:.6px;padding-bottom:2px;padding-top:12px;">CUFE / CUDE</td>
            </tr>
            <tr>
              <td style="color:#374151;font-size:11px;font-family:monospace;
                         word-break:break-all;">{cufe}</td>
            </tr>"""
        if cufe else ""
    )
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:32px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:16px;overflow:hidden;
                    box-shadow:0 4px 24px rgba(0,0,0,.10);max-width:560px;width:100%;">
        <tr>
          <td style="background:linear-gradient(135deg,#1e40af 0%,#1d4ed8 100%);
                     padding:32px 36px;text-align:center;">
            <div style="display:inline-block;background:rgba(255,255,255,.18);
                        border-radius:50%;width:56px;height:56px;line-height:56px;
                        font-size:26px;margin-bottom:12px;">&#128196;</div>
            <h1 style="color:#ffffff;margin:0;font-size:22px;font-weight:700;">
              Factura Electrónica Disponible
            </h1>
            <p style="color:#bfdbfe;margin:6px 0 0;font-size:14px;">
              {institucion_nombre}
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding:32px 36px;">
            <p style="color:#374151;font-size:15px;margin:0 0 20px;">
              Estimado/a acudiente o representante de <strong>{estudiante_nombre}</strong>,
            </p>
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:10px;
                          margin-bottom:24px;">
              <tr>
                <td style="padding:20px 24px;">
                  <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <td style="color:#6b7280;font-size:12px;text-transform:uppercase;
                                 letter-spacing:.6px;padding-bottom:4px;">Número de Factura</td>
                    </tr>
                    <tr>
                      <td style="color:#1e40af;font-size:20px;font-weight:800;
                                 padding-bottom:14px;">{numero}</td>
                    </tr>
                    <tr>
                      <td style="color:#6b7280;font-size:12px;text-transform:uppercase;
                                 letter-spacing:.6px;padding-bottom:4px;">Concepto</td>
                    </tr>
                    <tr>
                      <td style="color:#111827;font-size:16px;font-weight:700;
                                 padding-bottom:14px;">{concepto}</td>
                    </tr>
                    <tr>
                      <td style="color:#6b7280;font-size:12px;text-transform:uppercase;
                                 letter-spacing:.6px;padding-bottom:4px;">Valor</td>
                    </tr>
                    <tr>
                      <td style="color:#1e40af;font-size:24px;font-weight:800;
                                 padding-bottom:14px;">{valor}</td>
                    </tr>
                    <tr>
                      <td style="color:#6b7280;font-size:12px;text-transform:uppercase;
                                 letter-spacing:.6px;padding-bottom:4px;">Fecha</td>
                    </tr>
                    <tr>
                      <td style="color:#374151;font-size:15px;font-weight:600;">{fecha}</td>
                    </tr>
                    {cufe_fila}
                  </table>
                </td>
              </tr>
            </table>
            <div style="text-align:center;margin-bottom:24px;">
              {boton_pdf}
            </div>
            <p style="color:#6b7280;font-size:13px;margin:0;">
              Esta factura fue generada y validada ante la DIAN por
              <strong>{institucion_nombre}</strong>.
              Consérvela como soporte de pago. Si tiene alguna duda, comuníquese
              con la administración del colegio.
            </p>
          </td>
        </tr>
        <tr>
          <td style="background:#f8fafc;padding:18px 36px;text-align:center;
                     border-top:1px solid #e2e8f0;">
            <p style="color:#94a3b8;font-size:12px;margin:0;">
              Mensaje automático de <strong>Halu Plataforma Escolar</strong>.
              No responda a este correo.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Tarea 4: Factura electrónica validada
# ---------------------------------------------------------------------------

@shared_task(
    name="gestion_academica.notificar_factura_electronica",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
)
def notificar_factura_electronica(self, factura_id: int) -> None:
    """Envía la factura electrónica por correo al estudiante y sus familiares."""
    from facturacion_electronica.models import FacturaElectronica
    from admisiones.utils import enviar_correo_dinamico

    try:
        factura = (
            FacturaElectronica.objects
            .select_related(
                "estudiante__usuario",
                "estudiante__institucion",
                "pago__cuenta__concepto_pago",
                "cuenta__concepto_pago",
                "institucion",
            )
            .get(pk=factura_id)
        )
    except FacturaElectronica.DoesNotExist:
        logger.warning("notificar_factura_electronica: factura %s no encontrada.", factura_id)
        return

    if factura.estado != FacturaElectronica.Estado.VALIDADA:
        logger.info(
            "notificar_factura_electronica: factura %s no está VALIDADA (estado=%s), se omite.",
            factura_id, factura.estado,
        )
        return

    estudiante = factura.estudiante
    institucion = factura.institucion

    estudiante_nombre = (
        estudiante.usuario.get_full_name() or estudiante.usuario.username
        if hasattr(estudiante, "usuario") and estudiante.usuario
        else f"Estudiante #{estudiante.pk}"
    )

    # Concepto: viene del pago o de la cuenta directamente
    concepto = "Servicio educativo"
    if factura.pago and hasattr(factura.pago, "cuenta") and factura.pago.cuenta:
        concepto = getattr(factura.pago.cuenta.concepto_pago, "nombre_concepto", concepto)
    elif factura.cuenta:
        concepto = getattr(factura.cuenta.concepto_pago, "nombre_concepto", concepto)

    # Valor: del pago si existe, sino del monto de la cuenta
    valor = "—"
    if factura.pago and factura.pago.valor_pagado:
        valor = f"${factura.pago.valor_pagado:,.2f}"
    elif factura.cuenta and factura.cuenta.monto_asignado:
        valor = f"${factura.cuenta.monto_asignado:,.2f}"

    fecha_str = factura.fecha_emision.strftime("%d/%m/%Y") if factura.fecha_emision else "—"

    # Destinatarios: estudiante + todos los familiares con email
    destinatarios = []
    if estudiante.usuario and estudiante.usuario.email:
        destinatarios.append(estudiante.usuario.email)

    familiares_emails = list(
        estudiante.familiares
        .select_related("usuario")
        .exclude(usuario__email="")
        .exclude(usuario__email__isnull=True)
        .values_list("usuario__email", flat=True)
    )
    destinatarios.extend(familiares_emails)
    destinatarios = list(dict.fromkeys(destinatarios))  # deduplicar

    if not destinatarios:
        logger.info(
            "notificar_factura_electronica: factura %s sin destinatarios con email.", factura_id
        )
        return

    html = _html_factura(
        institucion_nombre=institucion.nombre,
        estudiante_nombre=estudiante_nombre,
        numero=factura.numero or "—",
        concepto=concepto,
        valor=valor,
        fecha=fecha_str,
        url_pdf=factura.url_pdf or "",
        cufe=factura.cufe or "",
    )

    try:
        enviar_correo_dinamico(
            institucion=institucion,
            asunto=f"Factura Electrónica {factura.numero} — {institucion.nombre}",
            destinatarios=destinatarios,
            html_content=html,
        )
        logger.info(
            "notificar_factura_electronica: correo enviado factura %s a %s destinatario(s).",
            factura_id, len(destinatarios),
        )
    except Exception as exc:
        logger.error(
            "notificar_factura_electronica: error enviando correo factura %s: %s",
            factura_id, exc, exc_info=True,
        )
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Tarea 5: Recibo de pago manual (reemplaza el envío síncrono de la vista)
# ---------------------------------------------------------------------------

@shared_task(
    name="gestion_academica.notificar_recibo_pago_manual",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def notificar_recibo_pago_manual(self, pago_id: int) -> None:
    """Genera el PDF del recibo y lo envía por correo en segundo plano.

    Reemplaza el envío síncrono en la vista registrar_pago que causaba
    timeout cuando el servidor SMTP tardaba en responder.
    """
    from finanzas.models import PagoRegistrado
    from django.template.loader import get_template
    from io import BytesIO
    from xhtml2pdf import pisa
    from django.core.mail import EmailMessage

    try:
        pago = (
            PagoRegistrado.objects
            .select_related(
                "estudiante__usuario",
                "cuenta__concepto_pago",
                "institucion",
            )
            .get(pk=pago_id)
        )
    except PagoRegistrado.DoesNotExist:
        logger.warning("notificar_recibo_pago_manual: pago %s no encontrado.", pago_id)
        return

    institucion = pago.institucion
    if not institucion.email_host_user or not institucion.email_host_password:
        logger.info(
            "notificar_recibo_pago_manual: institución %s sin SMTP configurado.",
            institucion.pk,
        )
        return

    # Destinatarios: acudiente + email del estudiante (igual que antes)
    email_acudiente = None
    if pago.estudiante:
        # Primer familiar con email
        familiar = (
            pago.estudiante.familiares
            .select_related("usuario")
            .exclude(usuario__email="")
            .exclude(usuario__email__isnull=True)
            .first()
        )
        if familiar:
            email_acudiente = familiar.usuario.email

    email_estudiante = (
        pago.estudiante.usuario.email
        if pago.estudiante and pago.estudiante.usuario
        else None
    )
    email_destinatario = email_acudiente or email_estudiante
    if not email_destinatario:
        logger.info("notificar_recibo_pago_manual: pago %s sin email destinatario.", pago_id)
        return

    try:
        template = get_template("finanzas/emails/recibo_pago.html")
        html = template.render({"pago": pago, "institucion": institucion, "domain": "https://app.haluplataform.com"})

        pdf_buffer = BytesIO()
        pisa.CreatePDF(html, dest=pdf_buffer)
        pdf_buffer.seek(0)

        from django.core.mail import get_connection
        connection = get_connection(
            backend="django.core.mail.backends.smtp.EmailBackend",
            host=institucion.email_host,
            port=institucion.email_port,
            username=institucion.email_host_user,
            password=institucion.email_host_password.decrypt() if hasattr(institucion.email_host_password, 'decrypt') else institucion.email_host_password,
            use_tls=institucion.email_use_tls,
        )
        remitente = f'"{institucion.nombre}" <{institucion.email_host_user}>'
        email = EmailMessage(
            f"Recibo de Pago — {institucion.nombre}",
            html,
            remitente,
            [email_destinatario],
            connection=connection,
        )
        email.content_subtype = "html"
        email.attach(f"Recibo_Pago_{pago.pk}.pdf", pdf_buffer.getvalue(), "application/pdf")
        email.send()
        logger.info("notificar_recibo_pago_manual: recibo enviado pago %s a %s.", pago_id, email_destinatario)
    except Exception as exc:
        logger.error(
            "notificar_recibo_pago_manual: error pago %s: %s", pago_id, exc, exc_info=True
        )
        raise self.retry(exc=exc)
