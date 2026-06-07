# admisiones/tasks.py
"""Tareas Celery para procesos pesados de admisiones.

Por ahora, su única responsabilidad es ejecutar la importación masiva de
aspirantes desde un archivo Excel en background, reportando progreso por
WebSocket al usuario que la disparó.

Diseño:
- Una instancia de ``LoteImportacionAspirantes`` actúa como "job ticket": guarda
  archivo, estado, progreso, errores por fila y enlace al usuario creador.
- La tarea reutiliza UNA sola conexión SMTP por institución para todo el lote
  (evita el "anti-pattern" de abrir N conexiones SMTP en N filas).
- La señal ``post_save`` de ``Aspirante`` respeta el flag
  ``_omitir_correo_bienvenida`` para que el envío de correo lo controle la
  tarea, no la señal por defecto.
- El progreso se publica vía Channels al grupo ``user_<pk>`` del creador.
"""
from __future__ import annotations

import logging
import os
from datetime import date

import pandas as pd
from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.core.mail import get_connection
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from gestion_academica.models import Grado

from .models import Aspirante, LoteImportacionAspirantes
from .utils import enviar_correo_bienvenida

logger = logging.getLogger(__name__)


# Columnas esperadas en la plantilla Excel (en minúsculas, ya normalizadas).
COLUMNAS_OBLIGATORIAS = ("nombres", "apellidos", "numero_documento", "grado_aspira", "fecha_nacimiento", "email_contacto")


class _FilaInvalida(Exception):
    """Error 'controlado' al validar una fila: se reporta al usuario."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _se_pidio_cancelar(lote_id):
    """Lee el flag ``cancelacion_solicitada`` del lote desde BD.

    Esta función vive aparte para que la consulta sea ligera (un solo campo)
    y se pueda llamar dentro del bucle de filas sin penalizar el rendimiento.
    """
    return (
        LoteImportacionAspirantes.objects
        .filter(pk=lote_id)
        .values_list("cancelacion_solicitada", flat=True)
        .first()
        or False
    )


def _crear_conexion_smtp(institucion):
    """Devuelve una conexión SMTP reutilizable para los correos de bienvenida.

    Si la institución no tiene credenciales, devuelve None y la tarea simplemente
    omite el envío de correos (manteniendo el registro en BD).
    """
    if not (institucion.email_host_user and institucion.email_host_password):
        return None
    try:
        return get_connection(
            backend='django.core.mail.backends.smtp.EmailBackend',
            host=institucion.email_host,
            port=institucion.email_port,
            username=institucion.email_host_user,
            password=institucion.email_host_password,
            use_tls=institucion.email_use_tls,
        )
    except Exception as exc:
        logger.warning(
            "No fue posible crear conexión SMTP reutilizable para %s: %s",
            getattr(institucion, "nombre", institucion), exc,
        )
        return None


def _publicar_progreso(lote, *, final=False):
    """Publica el estado del lote por WebSocket al creador del lote."""
    if not lote.creado_por_id:
        return
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    try:
        url_resumen = reverse(
            "admisiones:lote_importacion_detalle",
            kwargs={"lote_id": lote.pk},
        )
    except Exception:
        url_resumen = ""

    payload = {
        "type": "send_notification",
        "kind": "import_progress",
        "title": "Importación de aspirantes",
        "message": _mensaje_progreso(lote, final=final),
        "url": url_resumen,
        "severity": "success" if (final and lote.filas_fallidas == 0) else "info",
        "institucion_id": lote.institucion_id,
    }
    try:
        async_to_sync(channel_layer.group_send)(
            f"user_{lote.creado_por_id}", payload
        )
    except Exception as exc:
        logger.warning("No se pudo emitir progreso WS del lote %s: %s", lote.pk, exc)


def _mensaje_progreso(lote, *, final=False):
    if lote.estado == LoteImportacionAspirantes.Estado.FALLIDO:
        return f"Importación fallida: {lote.mensaje_error_general or 'ver detalle'}"
    if final:
        if lote.dry_run:
            return (
                f"Simulación completada: {lote.filas_exitosas} OK, "
                f"{lote.filas_fallidas} con errores de {lote.total_filas}."
            )
        return (
            f"Importación completada: {lote.filas_exitosas} aspirantes creados, "
            f"{lote.filas_fallidas} con errores de {lote.total_filas}."
        )
    return (
        f"Procesando aspirantes: {lote.filas_procesadas}/{lote.total_filas} "
        f"({lote.progreso_porcentaje}%)."
    )


def _parsear_fecha(valor) -> date:
    """Convierte el valor *raw* de una celda de fecha de Excel al tipo ``date``.

    ``pd.read_excel(dtype=str)`` puede producir cadenas en distintos formatos
    según el tipo de celda en el libro:

    * Celda de tipo *fecha* en Excel → openpyxl la lee como ``datetime`` y
      pandas la serializa a string: ``"2000-05-15 00:00:00"``.
    * Celda de *texto* → se conserva tal cual: ``"15/05/2000"``, etc.
    * En algunos entornos/versiones puede llegar como número serial de Excel:
      ``"36561"`` o ``"36561.0"``.

    Acepta también objetos ``datetime.date``, ``datetime.datetime`` y
    ``pandas.Timestamp`` por si en algún futuro se cambia el ``dtype``.
    """
    from datetime import datetime as _dt

    # ── Casos no-string ────────────────────────────────────────────────────
    if isinstance(valor, date) and not isinstance(valor, _dt):
        return valor
    if isinstance(valor, _dt):
        return valor.date()
    if hasattr(valor, "to_pydatetime"):          # pandas.Timestamp
        try:
            return valor.to_pydatetime().date()
        except Exception:
            pass

    # ── Normalización del string ───────────────────────────────────────────
    texto = str(valor or "").strip()
    if not texto or texto.lower() in {"nat", "none", "null", "nan"}:
        raise ValueError("vacío o nulo")

    # Quitar componente de tiempo:  "2000-05-15 00:00:00" → "2000-05-15"
    for sep in (" ", "T"):
        if sep in texto:
            texto = texto.split(sep)[0]
            break

    # ── Formatos explícitos (Colombia primero) ─────────────────────────────
    FORMATOS = (
        "%d/%m/%Y",   # 15/05/2000   ← formato colombiano habitual
        "%d-%m-%Y",   # 15-05-2000
        "%Y-%m-%d",   # 2000-05-15   ← ISO; lo que queda al quitar el tiempo
        "%d/%m/%y",   # 15/05/00
        "%d-%m-%y",   # 15-05-00
        "%Y/%m/%d",   # 2000/05/15
        "%d.%m.%Y",   # 15.05.2000
        "%d.%m.%y",   # 15.05.00
    )
    for fmt in FORMATOS:
        try:
            return _dt.strptime(texto, fmt).date()
        except ValueError:
            continue

    # ── Número serial de Excel (fallback para celdas mal formateadas) ──────
    try:
        serial = float(texto)
        if 1 <= serial <= 2_958_465:             # rango 1900-01-01 / 9999-12-31
            from datetime import timedelta
            # La época de Excel es 0 = 30-dic-1899 (compensa el bug del año
            # bisiesto 1900 que Excel heredó de Lotus 1-2-3).
            return date(1899, 12, 30) + timedelta(days=int(serial))
    except (ValueError, TypeError):
        pass

    raise ValueError(f"formato no reconocido: '{texto}'")


def _parsear_fila(row, grados_por_nombre):
    """Valida y convierte una fila del Excel a un dict listo para crear el Aspirante."""

    def _v(col, default=""):
        return str(row.get(col, default) or "").strip()

    documento = _v("numero_documento")
    grado_nombre = _v("grado_aspira")

    # Accedemos al valor *raw* para que _parsear_fecha pueda manejar
    # directamente Timestamps, datetimes y los distintos formatos de string
    # que produce openpyxl/pandas al forzar dtype=str.
    fecha_raw = row.get("fecha_nacimiento", "")
    fecha_str = str(fecha_raw or "").strip()

    if not documento:
        raise _FilaInvalida("Falta el número de documento.")
    if not grado_nombre:
        raise _FilaInvalida("Falta el grado al que aspira.")
    if not fecha_str or fecha_str.lower() in {"nat", "none", "null", "nan"}:
        raise _FilaInvalida("Falta la fecha de nacimiento.")

    grado = grados_por_nombre.get(grado_nombre.lower())
    if not grado:
        raise _FilaInvalida(
            f"El grado '{grado_nombre}' no existe en la institución (revisa la plantilla)."
        )

    try:
        fecha_nacimiento = _parsear_fecha(fecha_raw)
    except ValueError as exc:
        raise _FilaInvalida(
            f"Fecha de nacimiento inválida: '{fecha_str}' — {exc}. "
            "Usa el formato DD/MM/YYYY (ej. 15/05/2000)."
        )
    if fecha_nacimiento >= date.today():
        raise _FilaInvalida("La fecha de nacimiento debe ser anterior a hoy.")

    sexo = (_v("sexo") or "O").upper()
    if sexo not in {"M", "F", "O"}:
        sexo = "O"

    paga_raw = _v("paga_inscripcion").upper()
    paga = paga_raw in {"SI", "SÍ", "TRUE", "1", "YES", "Y"}

    # Normalizar tipo_documento
    tipo_doc_raw = _v("tipo_documento").upper()
    tipo_doc_validos = {"TI", "CC", "RC", "PA", "CE", "OT"}
    tipo_documento = tipo_doc_raw if tipo_doc_raw in tipo_doc_validos else None

    # Normalizar grupo_sanguineo
    gs_raw = _v("grupo_sanguineo").upper().replace(" ", "")
    gs_validos = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}
    grupo_sanguineo = gs_raw if gs_raw in gs_validos else None

    return {
        "documento": documento,
        "grado": grado,
        "nombres": _v("nombres") or "Sin nombre",
        "apellidos": _v("apellidos") or "Sin apellido",
        "fecha_nacimiento": fecha_nacimiento,
        "email_contacto": _v("email_contacto"),
        "telefono_contacto": _v("telefono_contacto") or None,
        "sexo": sexo,
        "tipo_documento": tipo_documento,
        "lugar_nacimiento": _v("lugar_nacimiento") or None,
        "grupo_sanguineo": grupo_sanguineo,
        "eps": _v("eps") or None,
        "discapacidad": _v("discapacidad") or None,
        "colegio_procedencia": _v("colegio_procedencia") or None,
        "municipio_ciudad": _v("municipio_ciudad") or None,
        "departamento": _v("departamento") or None,
        "direccion": _v("direccion") or None,
        "paga_inscripcion": paga,
    }


# ---------------------------------------------------------------------------
# Tarea principal
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    soft_time_limit=60 * 30,   # 30 min
    time_limit=60 * 35,        # 35 min
    name="admisiones.procesar_importacion_aspirantes",
)
def procesar_importacion_aspirantes_task(self, lote_id):
    """Procesa un lote de importación de aspirantes desde Excel.

    Ejecuta en orden:
      1. Marca el lote como ``EN_PROCESO``, publica progreso.
      2. Abre el Excel y normaliza columnas.
      3. Pre-carga grados de la institución para evitar N+1.
      4. Crea (o simula crear, si ``dry_run``) los aspirantes fila a fila con
         savepoint individual; las filas con error no rompen el resto del lote.
      5. Envía correos de bienvenida usando una sola conexión SMTP.
      6. Actualiza el lote con resumen + errores por fila + WebSocket final.
    """
    try:
        lote = (
            LoteImportacionAspirantes.objects
            .select_related("institucion", "creado_por")
            .get(pk=lote_id)
        )
    except LoteImportacionAspirantes.DoesNotExist:
        logger.error("Lote de importación %s no existe; se ignora la tarea.", lote_id)
        return

    if lote.estado != LoteImportacionAspirantes.Estado.PENDIENTE:
        logger.info(
            "Lote %s ya está en estado %s; se omite el reprocesamiento.",
            lote.pk, lote.estado,
        )
        return

    institucion = lote.institucion

    # Guardamos el task_id para que la UI pueda cancelarlo (revoke).
    lote.task_id = self.request.id or ""
    lote.estado = LoteImportacionAspirantes.Estado.EN_PROCESO
    lote.fecha_inicio = timezone.now()
    lote.save(update_fields=["task_id", "estado", "fecha_inicio"])
    _publicar_progreso(lote)

    errores: list[dict] = []
    filas_exitosas = 0
    filas_fallidas = 0
    filas_con_advertencia = 0

    smtp_connection = None
    try:
        # 1) Leer archivo
        archivo_path = lote.archivo.path
        if not os.path.exists(archivo_path):
            raise RuntimeError("El archivo del lote ya no existe en disco.")

        df = pd.read_excel(archivo_path, dtype=str, keep_default_na=False)
        df.columns = [str(col).strip().lower() for col in df.columns]
        faltantes = [c for c in COLUMNAS_OBLIGATORIAS if c not in df.columns]
        if faltantes:
            raise RuntimeError(
                "Faltan columnas obligatorias en la plantilla: "
                + ", ".join(faltantes)
            )

        total = int(len(df))
        lote.total_filas = total
        lote.save(update_fields=["total_filas"])
        _publicar_progreso(lote)

        # 2) Pre-cache grados
        grados_qs = (
            Grado.objects.filter(institucion=institucion)
            .select_related("nivel_escolaridad")
        )
        grados_por_nombre = {g.nombre.lower(): g for g in grados_qs}

        # 3) Set existente para detectar duplicados de documento en una sola query
        existentes = set(
            Aspirante.objects.filter(institucion=institucion)
            .values_list("numero_documento", flat=True)
        )

        # 4) SMTP reutilizable solo si NO es dry-run
        if not lote.dry_run:
            smtp_connection = _crear_conexion_smtp(institucion)

        cancelado_por_usuario = False

        # 5) Procesar filas
        for index, row in df.iterrows():
            fila_num = int(index) + 2  # +1 por header, +1 por base-0

            # Cancelación cooperativa: cada N filas releemos el flag desde BD.
            if (int(index) % 25) == 0 and _se_pidio_cancelar(lote.pk):
                cancelado_por_usuario = True
                logger.info("Lote %s: cancelación solicitada, abortando bucle.", lote.pk)
                break

            documento_raw = str(row.get("numero_documento", "")).strip()
            try:
                datos = _parsear_fila(row, grados_por_nombre)
                if datos["documento"] in existentes:
                    raise _FilaInvalida(
                        f"Ya existe un aspirante con documento '{datos['documento']}' en esta institución."
                    )

                if lote.dry_run:
                    # En simulación no persistimos, pero sí marcamos para detectar
                    # duplicados dentro del propio Excel.
                    existentes.add(datos["documento"])
                else:
                    aspirante, resultado_inscripcion, aviso_correo = _crear_aspirante_desde_datos(
                        datos, institucion, lote, smtp_connection
                    )
                    existentes.add(aspirante.numero_documento)

                    # Rastreamos si esta fila generó al menos una advertencia
                    # para no incrementar filas_con_advertencia más de una vez.
                    fila_tiene_advertencia = False

                    # Si la inscripción se completó pero el cobro NO se pudo crear
                    # por configuración faltante (ConceptoPago, nivel, etc.),
                    # registramos una ADVERTENCIA: la fila se creó OK, pero hay
                    # algo que el operador debe arreglar antes de que el aspirante
                    # pueda pagar. No la contamos como fallida.
                    cobro = resultado_inscripcion.cobro_inscripcion
                    if cobro.es_warning:
                        fila_tiene_advertencia = True
                        errores.append({
                            "tipo": "warning",
                            "fila": fila_num,
                            "documento": documento_raw,
                            "mensaje": cobro.mensaje,
                            # Mantenemos clave 'error' por compatibilidad con la
                            # plantilla y el export Excel anteriores.
                            "error": cobro.mensaje,
                        })

                    # Si el envío de correo de bienvenida falló, lo registramos
                    # también como advertencia visible en la tabla de incidencias.
                    if aviso_correo:
                        fila_tiene_advertencia = True
                        errores.append({
                            "tipo": "warning",
                            "fila": fila_num,
                            "documento": documento_raw,
                            "mensaje": aviso_correo,
                            "error": aviso_correo,
                        })

                    if fila_tiene_advertencia:
                        filas_con_advertencia += 1

                filas_exitosas += 1
            except _FilaInvalida as exc:
                filas_fallidas += 1
                errores.append({
                    "tipo": "error",
                    "fila": fila_num,
                    "documento": documento_raw,
                    "mensaje": str(exc),
                    "error": str(exc),
                })
            except IntegrityError as exc:
                logger.warning(
                    "Lote %s fila %s: IntegrityError tratado como duplicado: %s",
                    lote.pk, fila_num, exc,
                )
                filas_fallidas += 1
                errores.append({
                    "tipo": "error",
                    "fila": fila_num,
                    "documento": documento_raw,
                    "mensaje": "Documento duplicado en la institución (creación concurrente).",
                    "error": "Documento duplicado en la institución (creación concurrente).",
                })
            except Exception as exc:
                logger.error(
                    "Lote %s fila %s: error inesperado: %s",
                    lote.pk, fila_num, exc, exc_info=True,
                )
                filas_fallidas += 1
                errores.append({
                    "tipo": "error",
                    "fila": fila_num,
                    "documento": documento_raw,
                    "mensaje": f"Error inesperado ({type(exc).__name__}). Revisa los logs.",
                    "error": f"Error inesperado ({type(exc).__name__}). Revisa los logs.",
                })

            # Persistencia y notificación cada N filas o al final
            if (int(index) + 1) % 25 == 0 or (int(index) + 1) == total:
                lote.filas_procesadas = int(index) + 1
                lote.filas_exitosas = filas_exitosas
                lote.filas_fallidas = filas_fallidas
                lote.filas_con_advertencia = filas_con_advertencia
                lote.errores = errores
                lote.save(update_fields=[
                    "filas_procesadas", "filas_exitosas", "filas_fallidas",
                    "filas_con_advertencia", "errores",
                ])
                _publicar_progreso(lote)

        # 6) Cierre
        lote.filas_exitosas = filas_exitosas
        lote.filas_fallidas = filas_fallidas
        lote.filas_con_advertencia = filas_con_advertencia
        lote.errores = errores
        lote.fecha_fin = timezone.now()
        if cancelado_por_usuario:
            lote.estado = LoteImportacionAspirantes.Estado.CANCELADO
            lote.mensaje_error_general = (
                "Lote cancelado por el usuario. Las filas previamente creadas se conservan."
            )
            lote.save()
            _publicar_progreso(lote, final=True)
            logger.info(
                "Lote %s CANCELADO en fila %s. %s OK, %s con errores.",
                lote.pk, lote.filas_procesadas, filas_exitosas, filas_fallidas,
            )
        else:
            lote.filas_procesadas = total
            lote.estado = LoteImportacionAspirantes.Estado.COMPLETADO
            lote.save()
            _publicar_progreso(lote, final=True)
            logger.info(
                "Lote %s COMPLETADO. %s OK, %s con errores, total %s.",
                lote.pk, filas_exitosas, filas_fallidas, total,
            )

    except Exception as exc:
        logger.error("Lote %s falló: %s", lote.pk, exc, exc_info=True)
        lote.estado = LoteImportacionAspirantes.Estado.FALLIDO
        lote.mensaje_error_general = str(exc)[:1000]
        lote.fecha_fin = timezone.now()
        lote.save(update_fields=["estado", "mensaje_error_general", "fecha_fin"])
        _publicar_progreso(lote, final=True)
    finally:
        if smtp_connection is not None:
            try:
                smtp_connection.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Persistencia de UNA fila
# ---------------------------------------------------------------------------

@transaction.atomic
def _crear_aspirante_desde_datos(datos, institucion, lote, smtp_connection):
    """Crea Aspirante + perfiles + cuenta de inscripción para una fila válida.

    Se ejecuta dentro de su propia transacción (savepoint dentro de la atómica
    de la tarea). Si algo falla, NO arrastra el lote: la tarea atrapa y reporta.

    Devuelve una tupla ``(aspirante, ResultadoInscripcion, aviso_correo)`` donde
    ``aviso_correo`` es ``None`` si el correo se envió bien, o un string con el
    mensaje de error para que la tarea lo registre como advertencia visible.
    """
    aspirante = Aspirante(
        institucion=institucion,
        nombres=datos["nombres"],
        apellidos=datos["apellidos"],
        numero_documento=datos["documento"],
        grado_aspira=datos["grado"],
        fecha_nacimiento=datos["fecha_nacimiento"],
        email_contacto=datos["email_contacto"],
        telefono_contacto=datos["telefono_contacto"],
        sexo=datos["sexo"],
        tipo_documento=datos["tipo_documento"],
        lugar_nacimiento=datos["lugar_nacimiento"],
        grupo_sanguineo=datos["grupo_sanguineo"],
        eps=datos["eps"],
        discapacidad=datos["discapacidad"],
        colegio_procedencia=datos["colegio_procedencia"],
        municipio_ciudad=datos["municipio_ciudad"],
        departamento=datos["departamento"],
        direccion=datos["direccion"],
        requiere_pago_inscripcion=datos["paga_inscripcion"],
        lote_importacion=lote,
    )
    # No queremos que la señal abra otra conexión SMTP por fila. El correo lo
    # enviaremos manualmente reusando la conexión del lote.
    aspirante._omitir_correo_bienvenida = True
    aspirante.save()

    resultado = aspirante.procesar_inscripcion_completa()

    # Intentamos enviar el correo de bienvenida reutilizando la conexión del
    # lote. Un fallo aquí NO tumba la creación del aspirante, pero SÍ se
    # devuelve como aviso para que la tarea lo muestre en la tabla de errores.
    aviso_correo = None
    if smtp_connection is not None:
        try:
            enviado = enviar_correo_bienvenida(
                request=None,
                aspirante=aspirante,
                connection=smtp_connection,
            )
            if not enviado:
                aviso_correo = (
                    f"No se envió correo de bienvenida a '{aspirante.email_contacto}': "
                    "la función de envío devolvió False (revisa el email del aspirante)."
                )
        except Exception as exc:
            aviso_correo = (
                f"Error al enviar correo de bienvenida a '{aspirante.email_contacto}': {exc}"
            )
            logger.warning(
                "Lote %s: aviso de correo para aspirante %s: %s",
                lote.pk, aspirante.pk, exc,
            )

    return aspirante, resultado, aviso_correo


@shared_task(name="admisiones.reenviar_correos_bienvenida_lote")
def reenviar_correos_bienvenida_lote(lote_id: int, user_id: int = None) -> dict:
    """Reenvía el correo de bienvenida a todos los aspirantes de un lote ya procesado.

    Útil cuando el lote se procesó con el backend en modo consola (desarrollo)
    o cuando los correos fallaron por credenciales SMTP no configuradas en ese momento.

    Al terminar:
    - Guarda un resumen detallado en ``lote.resumen_correos``.
    - Envía una notificación WebSocket al usuario que solicitó el reenvío
      (``user_id``) o al creador del lote como respaldo.
    """
    from datetime import datetime as _dt
    from .utils import _email_valido

    # ── helpers locales ────────────────────────────────────────────────────
    def _notificar(uid, titulo, mensaje, severity="info"):
        if not uid:
            return
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        try:
            url = reverse(
                "admisiones:lote_importacion_detalle",
                kwargs={"lote_id": lote_id},
            )
        except Exception:
            url = ""
        try:
            async_to_sync(channel_layer.group_send)(
                f"user_{uid}",
                {
                    "type": "send_notification",
                    "kind": "email_resend_result",
                    "title": titulo,
                    "message": mensaje,
                    "url": url,
                    "severity": severity,
                    "institucion_id": lote.institucion_id,
                },
            )
        except Exception as exc:
            logger.warning("reenviar_correos: no se pudo enviar WS a user %s: %s", uid, exc)

    # ── carga del lote ─────────────────────────────────────────────────────
    try:
        lote = LoteImportacionAspirantes.objects.select_related("institucion").get(pk=lote_id)
    except LoteImportacionAspirantes.DoesNotExist:
        logger.error("reenviar_correos: lote %s no existe.", lote_id)
        return {"ok": 0, "errores_count": 0, "motivo": "lote_no_existe"}

    notify_uid = user_id or lote.creado_por_id
    institucion = lote.institucion
    aspirantes = Aspirante.objects.filter(lote_importacion=lote).select_related("institucion")
    total = aspirantes.count()

    if total == 0:
        resumen = {
            "tipo": "resend", "fecha": _dt.now().isoformat(),
            "ok": 0, "errores_count": 0, "omitidos": 0, "total": 0,
            "detalle_errores": [], "motivo": "sin_aspirantes",
        }
        lote.resumen_correos = resumen
        lote.save(update_fields=["resumen_correos"])
        _notificar(notify_uid, "Reenvío de correos", "No hay aspirantes vinculados a este lote.", "warning")
        return resumen

    smtp = _crear_conexion_smtp(institucion)
    if smtp is None:
        resumen = {
            "tipo": "resend", "fecha": _dt.now().isoformat(),
            "ok": 0, "errores_count": 0, "omitidos": 0, "total": total,
            "detalle_errores": [], "motivo": "smtp_no_configurado",
        }
        lote.resumen_correos = resumen
        lote.save(update_fields=["resumen_correos"])
        _notificar(
            notify_uid,
            "Reenvío de correos — sin SMTP",
            f"La institución no tiene credenciales SMTP configuradas. "
            f"Configúralas en el panel de administración para poder enviar correos.",
            "warning",
        )
        logger.warning(
            "reenviar_correos: institución %s sin SMTP configurado.",
            getattr(institucion, "nombre", institucion),
        )
        return resumen

    # ── bucle de envío ─────────────────────────────────────────────────────
    ok = 0
    errores_count = 0
    omitidos = 0
    detalle_errores: list[dict] = []          # máx. 100 entradas para no inflar el JSON

    for aspirante in aspirantes:
        if not _email_valido(aspirante.email_contacto):
            logger.warning(
                "reenviar_correos lote %s: aspirante %s email inválido (%s), omitido.",
                lote_id, aspirante.pk, aspirante.email_contacto,
            )
            omitidos += 1
            if len(detalle_errores) < 100:
                detalle_errores.append({
                    "nombres": f"{aspirante.nombres} {aspirante.apellidos}",
                    "documento": aspirante.numero_documento,
                    "email": aspirante.email_contacto or "(vacío)",
                    "error": "Email inválido o vacío — corrige la dirección del aspirante.",
                    "tipo": "omitido",
                })
            continue

        try:
            enviado = enviar_correo_bienvenida(request=None, aspirante=aspirante, connection=smtp)
            if enviado:
                ok += 1
            else:
                errores_count += 1
                if len(detalle_errores) < 100:
                    detalle_errores.append({
                        "nombres": f"{aspirante.nombres} {aspirante.apellidos}",
                        "documento": aspirante.numero_documento,
                        "email": aspirante.email_contacto,
                        "error": "El correo no fue aceptado por el servidor (sin excepción).",
                        "tipo": "error",
                    })
        except Exception as exc:
            errores_count += 1
            logger.warning(
                "reenviar_correos lote %s: error con aspirante %s (%s): %s",
                lote_id, aspirante.pk, aspirante.email_contacto, exc,
            )
            if len(detalle_errores) < 100:
                detalle_errores.append({
                    "nombres": f"{aspirante.nombres} {aspirante.apellidos}",
                    "documento": aspirante.numero_documento,
                    "email": aspirante.email_contacto,
                    "error": str(exc),
                    "tipo": "error",
                })

    # ── guardar resumen ────────────────────────────────────────────────────
    resumen = {
        "tipo": "resend",
        "fecha": _dt.now().isoformat(timespec="seconds"),
        "ok": ok,
        "errores_count": errores_count,
        "omitidos": omitidos,
        "total": total,
        "detalle_errores": detalle_errores,
    }
    lote.resumen_correos = resumen
    lote.save(update_fields=["resumen_correos"])

    logger.info(
        "reenviar_correos lote %s: %s enviados, %s errores, %s omitidos de %s.",
        lote_id, ok, errores_count, omitidos, total,
    )

    # ── notificación WebSocket al usuario ──────────────────────────────────
    if errores_count == 0 and omitidos == 0:
        severity = "success"
        titulo = f"✅ Reenvío completado — lote #{lote_id}"
        mensaje = f"{ok} correos enviados correctamente."
    elif ok > 0:
        severity = "warning"
        titulo = f"⚠️ Reenvío con problemas — lote #{lote_id}"
        partes = [f"{ok} enviados"]
        if errores_count:
            partes.append(f"{errores_count} con error")
        if omitidos:
            partes.append(f"{omitidos} omitidos (email inválido)")
        mensaje = ", ".join(partes) + ". Ver detalles en el lote."
    else:
        severity = "error"
        titulo = f"❌ Reenvío fallido — lote #{lote_id}"
        partes = []
        if errores_count:
            partes.append(f"{errores_count} con error")
        if omitidos:
            partes.append(f"{omitidos} omitidos (email inválido)")
        mensaje = (", ".join(partes) or "0 enviados") + ". Revisa los detalles en el lote."

    _notificar(notify_uid, titulo, mensaje, severity)
    return resumen
