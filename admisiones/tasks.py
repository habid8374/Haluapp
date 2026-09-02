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

import io
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

from gestion_academica.models import Grado, CaracterizacionEstudiante

from .models import Aspirante, LoteImportacionAspirantes
from .utils import enviar_correo_bienvenida

logger = logging.getLogger(__name__)


# Columnas esperadas en la plantilla Excel (en minúsculas, ya normalizadas).
COLUMNAS_OBLIGATORIAS = ("primer_nombre", "primer_apellido", "numero_documento", "grado_aspira", "fecha_nacimiento", "email_contacto")


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

# Sentinel: indica que el envío se hará vía Brevo API (sin conexión SMTP real).
_BREVO_API_ACTIVO = object()


def _crear_conexion_smtp(institucion):
    """Devuelve una conexión SMTP abierta y reutilizable para los correos de bienvenida.

    Si la institución no tiene credenciales, devuelve None y la tarea simplemente
    omite el envío de correos (manteniendo el registro en BD).

    Si la institución tiene su propia Brevo API Key configurada, devuelve
    _BREVO_API_ACTIVO (sentinel) para indicar que los correos se enviarán vía
    HTTP API sin necesidad de SMTP.
    """
    # SIEMPRE la clave Brevo de ESTA institución — nunca un respaldo global
    # (ver regla crítica en CLAUDE.md).
    _brevo_key = getattr(institucion, 'brevo_api_key', '') or ''
    if _brevo_key:
        return _BREVO_API_ACTIVO

    if not (institucion.email_host_user and institucion.email_host_password):
        return None
    port = institucion.email_port or 587
    # Puerto 465 usa SSL directo; cualquier otro usa STARTTLS (email_use_tls).
    use_ssl = (port == 465)
    use_tls = False if use_ssl else bool(institucion.email_use_tls)
    try:
        conn = get_connection(
            backend='django.core.mail.backends.smtp.EmailBackend',
            host=institucion.email_host,
            port=port,
            username=institucion.email_host_user,
            password=institucion.email_host_password,
            use_tls=use_tls,
            use_ssl=use_ssl,
            timeout=10,
        )
        conn.open()  # Falla rápido: si SMTP no responde, el error ocurre aquí (1 vez).
        return conn
    except Exception as exc:
        logger.warning(
            "No fue posible abrir conexión SMTP reutilizable para %s: %s — "
            "se omitirán los correos de bienvenida del lote.",
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


def _norm_texto(s):
    """Normaliza para comparar: sin acentos, mayúsculas, sin espacios extremos."""
    import unicodedata
    return (
        unicodedata.normalize("NFKD", str(s))
        .encode("ascii", "ignore")
        .decode("utf-8")
        .upper()
        .strip()
    )


def _match_choice(raw, choices):
    """Mapea un texto del Excel a un código de TextChoices.

    Acepta el código ('INDIGENA') o la etiqueta ('Indígena'), sin distinguir
    mayúsculas ni acentos. Devuelve el código, o None si está vacío/no coincide.
    """
    if not raw:
        return None
    objetivo = _norm_texto(raw)
    for code, label in choices:
        if _norm_texto(code) == objetivo or _norm_texto(label) == objetivo:
            return code
    return None


def _bool_si_no(raw):
    """Interpreta SI/NO (y variantes) del Excel como booleano. Vacío = False."""
    return _norm_texto(raw) in {"SI", "S", "TRUE", "1", "YES", "Y", "X", "VERDADERO"}


def _parsear_fila(row, grados_por_nombre, catalogos=None, enfasis_por_nombre=None):
    """Valida y convierte una fila del Excel a un dict listo para crear el Aspirante.

    ``catalogos`` (opcional): dict de dicts {code→obj} para resolver las columnas
    codificadas SIMAT (departamento/municipio/etnia/EPS). Los desplegables de la
    plantilla entregan "CODIGO - NOMBRE"; tomamos el código antes de " - ".

    ``enfasis_por_nombre`` (opcional): dict {nombre en minúsculas → Enfasis} del
    catálogo de la institución. El Énfasis NUNCA se autocrea desde el Excel (a
    diferencia del Grupo): si la celda trae texto y no matchea ningún énfasis
    existente, la fila NO se rechaza — queda registrada en
    ``"enfasis_no_encontrado"`` para que el llamador la marque como advertencia.
    """

    def _v(col, default=""):
        return str(row.get(col, default) or "").strip()

    def _fk(col, clave_catalogo):
        if not catalogos:
            return None
        raw = _v(col)
        if not raw:
            return None
        code = raw.split(" - ", 1)[0].strip()
        cat = catalogos.get(clave_catalogo, {})
        return cat.get(code) or cat.get(raw)

    def _split2(texto):
        partes = (texto or "").split()
        return (partes[0][:60], " ".join(partes[1:])[:60]) if partes else ("", "")

    documento = _v("numero_documento")
    grado_nombre = _v("grado_aspira")

    # Accedemos al valor *raw* para que _parsear_fecha pueda manejar
    # directamente Timestamps, datetimes y los distintos formatos de string
    # que produce openpyxl/pandas al forzar dtype=str.
    fecha_raw = row.get("fecha_nacimiento", "")
    fecha_str = str(fecha_raw or "").strip()

    # Nombres SIMAT (4 campos). Se admite la plantilla antigua (nombres/apellidos)
    # como respaldo para no romper archivos ya diligenciados.
    primer_nombre = _v("primer_nombre") or _split2(_v("nombres"))[0]
    segundo_nombre = _v("segundo_nombre") or _split2(_v("nombres"))[1]
    primer_apellido = _v("primer_apellido") or _split2(_v("apellidos"))[0]
    segundo_apellido = _v("segundo_apellido") or _split2(_v("apellidos"))[1]

    if not documento:
        raise _FilaInvalida("Falta el número de documento.")
    if not primer_nombre:
        raise _FilaInvalida("Falta el primer nombre.")
    if not primer_apellido:
        raise _FilaInvalida("Falta el primer apellido.")
    if not grado_nombre:
        raise _FilaInvalida("Falta el grado al que aspira.")
    if not fecha_str or fecha_str.lower() in {"nat", "none", "null", "nan"}:
        raise _FilaInvalida("Falta la fecha de nacimiento.")

    grado = grados_por_nombre.get(grado_nombre.lower())
    if not grado:
        raise _FilaInvalida(
            f"El grado '{grado_nombre}' no existe en la institución (revisa la plantilla)."
        )

    # Énfasis/taller (modalidad técnica) — opcional, no se autocrea.
    enfasis_nombre = _v("enfasis")
    enfasis_obj = None
    enfasis_no_encontrado = None
    if enfasis_nombre:
        enfasis_obj = (enfasis_por_nombre or {}).get(enfasis_nombre.lower())
        if enfasis_obj is None:
            enfasis_no_encontrado = enfasis_nombre

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
    tipo_doc_validos = {"TI", "CC", "RC", "PA", "CE", "NES", "PEP", "VISA", "TMF", "OT"}
    tipo_documento = tipo_doc_raw if tipo_doc_raw in tipo_doc_validos else None

    # Normalizar grupo_sanguineo
    gs_raw = _v("grupo_sanguineo").upper().replace(" ", "")
    gs_validos = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}
    grupo_sanguineo = gs_raw if gs_raw in gs_validos else None

    # ── Caracterización SIMAT/SIMPADE (columnas opcionales) ──────────────────
    # Mapeo tolerante: acepta código o etiqueta. Si un valor no coincide se
    # ignora silenciosamente (queda None) para no tumbar la fila.
    C = CaracterizacionEstudiante
    sisben_puntaje_raw = _v("sisben_puntaje").replace(",", ".")
    try:
        from decimal import Decimal
        sisben_puntaje = Decimal(sisben_puntaje_raw) if sisben_puntaje_raw else None
    except (ArithmeticError, ValueError):
        sisben_puntaje = None

    # FK de catálogo (se calculan una sola vez; de aquí derivamos los campos de
    # texto internos para no duplicar columnas en la plantilla).
    depto_nac = _fk("cod_depto_nacimiento", "depto")
    mpio_nac = _fk("cod_mpio_nacimiento", "mpio")
    depto_res = _fk("cod_depto_residencia", "depto")
    mpio_res = _fk("cod_mpio_residencia", "mpio")
    eps_obj = _fk("cod_eps_simat", "eps")

    def _nom_mpio_depto(mpio):
        try:
            return f"{mpio.nombre}, {mpio.departamento.nombre}"
        except Exception:
            return None

    return {
        "documento": documento,
        "grado": grado,
        "enfasis": enfasis_obj,
        "enfasis_no_encontrado": enfasis_no_encontrado,
        # El nombre "completo" (para mostrar y generar el usuario) se compone de
        # los 4 campos SIMAT, que son la fuente única.
        "nombres": " ".join(p for p in [primer_nombre, segundo_nombre] if p) or "Sin nombre",
        "apellidos": " ".join(p for p in [primer_apellido, segundo_apellido] if p) or "Sin apellido",
        "fecha_nacimiento": fecha_nacimiento,
        "email_contacto": _v("email_contacto"),
        "telefono_contacto": _v("telefono_contacto") or None,
        "sexo": sexo,
        "tipo_documento": tipo_documento,
        # Texto interno derivado del desplegable (una sola columna por concepto)
        "lugar_nacimiento": _v("lugar_nacimiento") or _nom_mpio_depto(mpio_nac),
        "grupo_sanguineo": grupo_sanguineo,
        "eps": _v("eps") or (eps_obj.nombre if eps_obj else None),
        "discapacidad": _v("discapacidad") or None,
        "colegio_procedencia": _v("colegio_procedencia") or None,
        "municipio_ciudad": _v("municipio_ciudad") or (mpio_res.nombre if mpio_res else None),
        "departamento": _v("departamento") or (depto_res.nombre if depto_res else (mpio_res.departamento.nombre if mpio_res else None)),
        "direccion": _v("direccion") or None,
        "paga_inscripcion": paga,
        # ── Caracterización ──
        "pais_origen": _v("pais_origen") or None,
        "zona_residencia": _match_choice(_v("zona_residencia"), C.ZonaResidencia.choices),
        "regimen_salud": _match_choice(_v("regimen_salud"), C.RegimenSalud.choices),
        "discapacidad_categoria": _match_choice(_v("discapacidad_categoria"), C.Discapacidad.choices),
        "capacidad_excepcional": _match_choice(_v("capacidad_excepcional"), C.CapacidadExcepcional.choices),
        "grupo_etnico": _match_choice(_v("grupo_etnico"), C.GrupoEtnico.choices),
        "estrato": _match_choice(_v("estrato"), C.Estrato.choices),
        "sisben_grupo": _v("sisben_grupo") or None,
        "sisben_puntaje": sisben_puntaje,
        "victima_conflicto": _bool_si_no(_v("victima_conflicto")),
        "tipo_poblacion_victima": _match_choice(_v("tipo_poblacion_victima"), C.TipoPoblacionVictima.choices),
        "srpa": _bool_si_no(_v("srpa")),
        "apoyo_academico_especial": _bool_si_no(_v("apoyo_academico_especial")),
        # ── SIMAT: identidad separada, ubicación DANE y matrícula ──
        "primer_nombre": primer_nombre,
        "segundo_nombre": segundo_nombre,
        "primer_apellido": primer_apellido,
        "segundo_apellido": segundo_apellido,
        "nacionalidad": _v("nacionalidad") or None,
        "barrio": _v("barrio") or None,
        "grupo": _v("grupo") or None,
        "jornada": (_v("jornada").upper().replace(" ", "_")
                    if _v("jornada").upper().replace(" ", "_") in
                    {"MANANA", "TARDE", "NOCHE", "UNICA", "COMPLETA", "FIN_DE_SEMANA"} else None),
        "campesino": _bool_si_no(_v("campesino")),
        "matricula_contratada": _bool_si_no(_v("matricula_contratada")),
        "repitente": _bool_si_no(_v("repitente")),
        "departamento_nacimiento": depto_nac,
        "municipio_nacimiento": mpio_nac,
        "departamento_residencia": depto_res,
        "municipio_residencia": mpio_res,
        "lugar_expedicion_departamento": _fk("cod_depto_expedicion", "depto"),
        "lugar_expedicion_municipio": _fk("cod_mpio_expedicion", "mpio"),
        "etnia_simat": _fk("cod_etnia_simat", "etnia"),
        "resguardo": _fk("cod_resguardo", "resguardo"),
        "eps_simat": eps_obj,
        "sede": _fk("nombre_sede", "sede"),
        # ── Acudiente / Familiar ──
        "acudiente_nombres": _v("acudiente_nombres") or None,
        "acudiente_apellidos": _v("acudiente_apellidos") or None,
        "acudiente_tipo_documento": (_v("acudiente_tipo_documento").upper()
                                     if _v("acudiente_tipo_documento").upper() in tipo_doc_validos else None),
        "acudiente_documento": _v("acudiente_documento") or None,
        "acudiente_parentesco": (_v("acudiente_parentesco").upper()
                                 if _v("acudiente_parentesco").upper() in
                                 {"PADRE", "MADRE", "ABUELO", "TIO", "HERMANO", "TUTOR", "OTRO"} else None),
        "acudiente_email": _v("acudiente_email") or None,
        "acudiente_telefono": _v("acudiente_telefono") or None,
        # ── SIMAT/SIMPADE codificados (Fase 3): el valor de la plantilla YA es el
        #    código oficial (desplegables). Se toma tal cual (mayúsculas en SI/NO).
        "sisben_simat": _v("sisben_simat").upper() or None,
        "caracter": _v("caracter") or None,
        "especialidad": _v("especialidad") or None,
        "metodologia": _v("metodologia") or None,
        "situacion_va": _v("situacion_va") or None,
        "condicion_va": _v("condicion_va") or None,
        "fuente_recurso": _v("fuente_recurso") or None,
        "tipo_internado": _v("tipo_internado") or None,
        "valoracion_p1": _v("valoracion_p1") or None,
        "valoracion_p2": _v("valoracion_p2") or None,
        "subsidiado": _v("subsidiado").upper() or None,
        "es_nuevo": _v("es_nuevo").upper() or None,
        "proviene_sector_privado": _v("proviene_sector_privado").upper() or None,
        "proviene_otro_municipio": _v("proviene_otro_municipio").upper() or None,
        "madre_cabeza_familia": _v("madre_cabeza_familia").upper() or None,
        "hijo_madre_cabeza_familia": _v("hijo_madre_cabeza_familia").upper() or None,
        "beneficiario_veterano": _v("beneficiario_veterano").upper() or None,
        "beneficiario_heroe": _v("beneficiario_heroe").upper() or None,
        "numero_convenio": _v("numero_convenio") or None,
        "institucion_bienestar": _v("institucion_bienestar") or None,
        "expulsor_departamento": _fk("cod_depto_expulsor", "depto"),
        "expulsor_municipio": _fk("cod_mpio_expulsor", "mpio"),
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
        # 1) Leer archivo — primero desde bytes en BD, luego desde disco como fallback
        if lote.archivo_bytes:
            df = pd.read_excel(io.BytesIO(bytes(lote.archivo_bytes)), dtype=str, keep_default_na=False)
        else:
            archivo_path = lote.archivo.path if lote.archivo else None
            if not archivo_path or not os.path.exists(archivo_path):
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

        # 2a.bis) Pre-cache énfasis/talleres (modalidad técnica) — catálogo
        # propio de la institución, no se autocrea desde el Excel.
        from gestion_academica.models import Enfasis
        enfasis_por_nombre = {
            e.nombre.lower(): e
            for e in Enfasis.objects.filter(institucion=institucion, activo=True)
        }

        # 2b) Pre-cache catálogos SIMAT (código→objeto) para resolver las FK
        from simat.models import Departamento, Municipio, Etnia, EPS, Resguardo, Sede
        catalogos = {
            "depto": {d.codigo: d for d in Departamento.objects.all()},
            "mpio": {m.codigo: m for m in Municipio.objects.all()},
            "etnia": {e.codigo: e for e in Etnia.objects.all()},
            "resguardo": {r.codigo: r for r in Resguardo.objects.all()},
            "eps": {e.codigo: e for e in EPS.objects.all()},
            # Sede es por institución y en la plantilla va por NOMBRE
            "sede": {s.nombre: s for s in Sede.objects.filter(institucion=institucion)},
        }

        # 3) Set existente para detectar duplicados de documento en una sola query
        existentes = set(
            Aspirante.objects.filter(institucion=institucion)
            .values_list("numero_documento", flat=True)
        )

        # 4) SMTP reutilizable solo si NO es dry-run
        _smtp_advertencia_general = None
        if not lote.dry_run:
            # SIEMPRE la clave Brevo de ESTA institución — nunca un respaldo global.
            _brevo_activo = bool(getattr(institucion, 'brevo_api_key', ''))
            _tiene_credenciales_smtp = bool(
                getattr(institucion, "email_host_user", None)
                and getattr(institucion, "email_host_password", None)
            )
            smtp_connection = _crear_conexion_smtp(institucion)
            if _brevo_activo:
                _smtp_advertencia_general = None  # Brevo API gestiona los correos
            elif _tiene_credenciales_smtp and smtp_connection is None:
                _smtp_advertencia_general = (
                    "No se pudo conectar al servidor SMTP de la institución "
                    "(timeout o credenciales incorrectas). "
                    "Los correos de bienvenida NO fueron enviados en este lote."
                )
            elif not _tiene_credenciales_smtp:
                _smtp_advertencia_general = (
                    "La institución no tiene SMTP configurado. "
                    "Los correos de bienvenida NO fueron enviados. "
                    "Configura el SMTP en el perfil de la institución."
                )

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
                datos = _parsear_fila(row, grados_por_nombre, catalogos, enfasis_por_nombre)
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

                    # Si la celda de "enfasis" traía texto pero no matcheó
                    # ningún énfasis del catálogo de la institución, el
                    # aspirante se crea igual (sin énfasis) pero se avisa —
                    # nunca se autocrea un énfasis nuevo por error de tipeo.
                    if datos.get("enfasis_no_encontrado"):
                        fila_tiene_advertencia = True
                        errores.append({
                            "tipo": "warning",
                            "fila": fila_num,
                            "documento": documento_raw,
                            "mensaje": (
                                f"El énfasis '{datos['enfasis_no_encontrado']}' no existe en el "
                                "catálogo de la institución; el aspirante se creó sin énfasis asignado."
                            ),
                            "error": (
                                f"Énfasis '{datos['enfasis_no_encontrado']}' no encontrado."
                            ),
                        })

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
        # Agregar advertencia general de SMTP si aplica
        if _smtp_advertencia_general:
            errores.insert(0, {
                "tipo": "warning",
                "fila": "-",
                "documento": "-",
                "mensaje": _smtp_advertencia_general,
                "error": _smtp_advertencia_general,
            })

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
        enfasis=datos.get("enfasis"),
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
        # ── Caracterización SIMAT/SIMPADE ──
        pais_origen=datos["pais_origen"],
        zona_residencia=datos["zona_residencia"],
        regimen_salud=datos["regimen_salud"],
        discapacidad_categoria=datos["discapacidad_categoria"],
        capacidad_excepcional=datos["capacidad_excepcional"],
        grupo_etnico=datos["grupo_etnico"],
        estrato=datos["estrato"],
        sisben_grupo=datos["sisben_grupo"],
        sisben_puntaje=datos["sisben_puntaje"],
        victima_conflicto=datos["victima_conflicto"],
        tipo_poblacion_victima=datos["tipo_poblacion_victima"],
        srpa=datos["srpa"],
        apoyo_academico_especial=datos["apoyo_academico_especial"],
        # ── SIMAT (Fase 2): identidad separada, ubicación DANE y matrícula ──
        primer_nombre=datos.get("primer_nombre", ""),
        segundo_nombre=datos.get("segundo_nombre", ""),
        primer_apellido=datos.get("primer_apellido", ""),
        segundo_apellido=datos.get("segundo_apellido", ""),
        nacionalidad=datos.get("nacionalidad") or "",
        barrio=datos.get("barrio") or "",
        grupo=datos.get("grupo") or "",
        jornada=datos.get("jornada") or "",
        campesino=datos.get("campesino", False),
        matricula_contratada=datos.get("matricula_contratada", False),
        repitente=datos.get("repitente", False),
        departamento_nacimiento=datos.get("departamento_nacimiento"),
        municipio_nacimiento=datos.get("municipio_nacimiento"),
        departamento_residencia=datos.get("departamento_residencia"),
        municipio_residencia=datos.get("municipio_residencia"),
        lugar_expedicion_departamento=datos.get("lugar_expedicion_departamento"),
        lugar_expedicion_municipio=datos.get("lugar_expedicion_municipio"),
        etnia_simat=datos.get("etnia_simat"),
        resguardo=datos.get("resguardo"),
        eps_simat=datos.get("eps_simat"),
        sede=datos.get("sede"),
        # ── SIMAT/SIMPADE codificados (Fase 3) ──
        sisben_simat=datos.get("sisben_simat") or "",
        caracter=datos.get("caracter") or "",
        especialidad=datos.get("especialidad") or "",
        metodologia=datos.get("metodologia") or "",
        situacion_va=datos.get("situacion_va") or "",
        condicion_va=datos.get("condicion_va") or "",
        fuente_recurso=datos.get("fuente_recurso") or "",
        tipo_internado=datos.get("tipo_internado") or "",
        valoracion_p1=datos.get("valoracion_p1") or "",
        valoracion_p2=datos.get("valoracion_p2") or "",
        subsidiado=datos.get("subsidiado") or "",
        es_nuevo=datos.get("es_nuevo") or "",
        proviene_sector_privado=datos.get("proviene_sector_privado") or "",
        proviene_otro_municipio=datos.get("proviene_otro_municipio") or "",
        madre_cabeza_familia=datos.get("madre_cabeza_familia") or "",
        hijo_madre_cabeza_familia=datos.get("hijo_madre_cabeza_familia") or "",
        beneficiario_veterano=datos.get("beneficiario_veterano") or "",
        beneficiario_heroe=datos.get("beneficiario_heroe") or "",
        numero_convenio=datos.get("numero_convenio") or "",
        institucion_bienestar=datos.get("institucion_bienestar") or "",
        expulsor_departamento=datos.get("expulsor_departamento"),
        expulsor_municipio=datos.get("expulsor_municipio"),
        # ── Acudiente / Familiar (procesar_inscripcion_completa crea el Familiar) ──
        acudiente_nombres=datos.get("acudiente_nombres") or "",
        acudiente_apellidos=datos.get("acudiente_apellidos") or "",
        acudiente_tipo_documento=datos.get("acudiente_tipo_documento"),
        acudiente_documento=datos.get("acudiente_documento") or "",
        acudiente_parentesco=datos.get("acudiente_parentesco") or "",
        acudiente_email=datos.get("acudiente_email") or "",
        acudiente_telefono=datos.get("acudiente_telefono") or "",
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
        # Si es Brevo API, enviar_correo_dinamico lo maneja sin conexión SMTP.
        conn_param = None if smtp_connection is _BREVO_API_ACTIVO else smtp_connection
        try:
            enviado = enviar_correo_bienvenida(
                request=None,
                aspirante=aspirante,
                connection=conn_param,
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
        # SIEMPRE la clave Brevo de ESTA institución — nunca un respaldo global.
        _brevo_key_en_este_servicio = getattr(institucion, 'brevo_api_key', '') or ''
        if not _brevo_key_en_este_servicio:
            _motivo_msg = (
                "Esta institución aún no tiene configurada su cuenta de correo (Brevo). "
                "Ve a Configuración › Correo y completa el campo 'Brevo API Key'."
            )
        else:
            _motivo_msg = (
                "No se pudo abrir conexión SMTP (el puerto puede estar bloqueado). "
                "Verifica las credenciales SMTP de la institución."
            )
        resumen = {
            "tipo": "resend", "fecha": _dt.now().isoformat(),
            "ok": 0, "errores_count": 0, "omitidos": 0, "total": total,
            "detalle_errores": [], "motivo": "smtp_no_configurado",
            "mensaje": _motivo_msg,
        }
        lote.resumen_correos = resumen
        lote.save(update_fields=["resumen_correos"])
        _notificar(
            notify_uid,
            "Reenvío de correos — sin configuración de correo",
            _motivo_msg,
            "warning",
        )
        logger.warning(
            "reenviar_correos: institución %s sin SMTP/Brevo propio configurado.",
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
