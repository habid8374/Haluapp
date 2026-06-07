"""Servicio reutilizable de health-check del backend HALU.

Esta es la **lógica canónica** del comando ``verificar_admisiones_health``.
Tanto el comando de manage.py como la tarea Celery del dashboard de
mantenimiento del super-admin invocan a ``ejecutar_health_check``.

Idea clave: en vez de imprimir directamente a stdout, recolectamos cada
"línea" del reporte como un evento estructurado. Eso permite:

- Persistir el resultado completo en BD (modelo ``EjecucionHealthCheck``).
- Reportar progreso en vivo a través de WebSocket (Channels).
- Mostrar el mismo reporte en CLI, dashboard y monitoring externo.

Uso típico:

    from admisiones.services.health_check import ejecutar_health_check

    resultado = ejecutar_health_check(
        institucion_id=None,
        progreso_callback=lambda evento: print(evento),  # opcional
    )
    if resultado.errores:
        ...
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------

NIVEL_OK = "OK"
NIVEL_WARN = "WARN"
NIVEL_ERR = "ERR"
NIVEL_INFO = "INFO"  # encabezados de sección


@dataclass
class EventoHealthCheck:
    """Una línea del reporte. Serializable a JSON."""

    nivel: str           # OK / WARN / ERR / INFO
    paso: str            # "1/8", "2/8", etc. — "" para encabezados libres
    titulo: str          # título del paso (solo para INFO de encabezado)
    mensaje: str         # contenido del evento

    def to_dict(self):
        return {
            "nivel": self.nivel,
            "paso": self.paso,
            "titulo": self.titulo,
            "mensaje": self.mensaje,
        }


@dataclass
class ResultadoHealthCheck:
    """Resultado completo del health-check."""

    eventos: List[EventoHealthCheck] = field(default_factory=list)
    errores: int = 0
    warnings: int = 0
    pasos_totales: int = 8

    @property
    def ok(self) -> bool:
        return self.errores == 0

    def to_dict(self):
        return {
            "ok": self.ok,
            "errores": self.errores,
            "warnings": self.warnings,
            "pasos_totales": self.pasos_totales,
            "eventos": [e.to_dict() for e in self.eventos],
        }


# ---------------------------------------------------------------------------
# Constantes (mismas que el comando)
# ---------------------------------------------------------------------------

PLANTILLAS_CRITICAS = [
    "admisiones/portal_postulante.html",
    "admisiones/portal_postulante_pagado.html",
    "admisiones/pago_procesando.html",
    "admisiones/lote_progreso.html",
    "admisiones/importar_aspirantes.html",
    "admisiones/dashboard.html",
    "emails/bienvenida_aspirante.html",
]

URLS_CRITICAS = [
    ("admisiones:dashboard_admisiones", {}),
    ("admisiones:importar_aspirantes", {}),
    ("admisiones:descargar_plantilla_importacion", {}),
    ("admisiones:lista_grados_aspirantes", {}),
    ("admisiones:pago_procesando", {}),
    ("admisiones:mercadopago_webhook", {}),
    ("admisiones:lote_importacion_detalle", {"lote_id": 1}),
    ("admisiones:lote_importacion_estado", {"lote_id": 1}),
    ("admisiones:lote_importacion_cancelar", {"lote_id": 1}),
    ("admisiones:lote_importacion_reintentar", {"lote_id": 1}),
]

PASOS_TOTALES = 8


# ---------------------------------------------------------------------------
# Runner principal
# ---------------------------------------------------------------------------

ProgresoCallback = Callable[[EventoHealthCheck], None]


def ejecutar_health_check(
    institucion_id: Optional[int] = None,
    progreso_callback: Optional[ProgresoCallback] = None,
) -> ResultadoHealthCheck:
    """Ejecuta los 8 pasos del health-check y devuelve el resultado.

    Si se pasa ``progreso_callback``, se invoca con CADA evento generado
    en tiempo real (útil para WebSocket).
    """
    resultado = ResultadoHealthCheck(pasos_totales=PASOS_TOTALES)

    def emit(nivel: str, mensaje: str, *, paso: str = "", titulo: str = "") -> None:
        evento = EventoHealthCheck(nivel=nivel, paso=paso, titulo=titulo, mensaje=mensaje)
        resultado.eventos.append(evento)
        if nivel == NIVEL_ERR:
            resultado.errores += 1
        elif nivel == NIVEL_WARN:
            resultado.warnings += 1
        if progreso_callback is not None:
            try:
                progreso_callback(evento)
            except Exception:
                logger.exception("Error en progreso_callback del health-check (se ignora).")

    # ------------------------------------------------------------------
    # 1/8 Redis
    # ------------------------------------------------------------------
    emit(NIVEL_INFO, "Verificando Redis (broker de Celery)…", paso="1/8", titulo="Redis (broker)")
    _check_redis(emit)

    # ------------------------------------------------------------------
    # 2/8 Celery
    # ------------------------------------------------------------------
    emit(NIVEL_INFO, "Verificando workers de Celery…", paso="2/8", titulo="Celery (workers)")
    _check_celery(emit)

    # ------------------------------------------------------------------
    # 3/8 Channels
    # ------------------------------------------------------------------
    emit(NIVEL_INFO, "Verificando Channel Layer (Django Channels)…", paso="3/8", titulo="Django Channels")
    _check_channels(emit)

    # ------------------------------------------------------------------
    # 4/8 Plantillas críticas
    # ------------------------------------------------------------------
    emit(NIVEL_INFO, "Verificando plantillas críticas…", paso="4/8", titulo="Plantillas críticas")
    _check_plantillas(emit)

    # ------------------------------------------------------------------
    # 5/8 URLs críticas
    # ------------------------------------------------------------------
    emit(NIVEL_INFO, "Verificando URLs nombradas…", paso="5/8", titulo="URLs nombradas")
    _check_urls(emit)

    # ------------------------------------------------------------------
    # 6/8 Instituciones (SMTP + Mercado Pago)
    # ------------------------------------------------------------------
    emit(NIVEL_INFO, "Verificando configuración multi-tenant por institución…",
         paso="6/8", titulo="Configuración por institución")
    _check_instituciones(emit, institucion_id)

    # ------------------------------------------------------------------
    # 7/8 Conceptos de pago (inscripción + matrícula + pensión)
    # ------------------------------------------------------------------
    emit(NIVEL_INFO, "Verificando Conceptos de Pago por nivel…",
         paso="7/8", titulo="Conceptos de Pago")
    _check_conceptos_pago(emit, institucion_id)

    # ------------------------------------------------------------------
    # 8/8 Estudiantes en mora
    # ------------------------------------------------------------------
    emit(NIVEL_INFO, "Verificando estudiantes en mora (Fase C)…",
         paso="8/8", titulo="Estudiantes en mora")
    _check_mora_estudiantes(emit, institucion_id)

    return resultado


# ---------------------------------------------------------------------------
# Checks individuales (todos reciben `emit` y nunca rompen, capturan excepciones)
# ---------------------------------------------------------------------------

def _check_redis(emit):
    from django.conf import settings
    broker_url = getattr(settings, "CELERY_BROKER_URL", None)
    if not broker_url:
        emit(NIVEL_ERR, "CELERY_BROKER_URL no está definido en settings.")
        return
    try:
        import redis  # type: ignore
    except ImportError:
        emit(NIVEL_WARN, "La librería `redis` no está instalada; no se puede verificar Redis directamente.")
        return
    try:
        client = redis.Redis.from_url(broker_url, socket_connect_timeout=2, socket_timeout=2)
        if client.ping():
            emit(NIVEL_OK, f"Redis responde PING en {broker_url}.")
        else:
            emit(NIVEL_ERR, f"Redis no respondió correctamente al PING en {broker_url}.")
    except Exception as exc:
        emit(NIVEL_ERR, f"No se pudo conectar a Redis ({broker_url}): {exc}")


def _check_celery(emit):
    try:
        from proyecto_colegio.celery import app as celery_app
    except Exception as exc:
        emit(NIVEL_ERR, f"No se pudo importar la app Celery: {exc}")
        return
    try:
        insp = celery_app.control.inspect(timeout=2.0)
        ping = insp.ping() or {}
        if not ping:
            emit(NIVEL_WARN,
                 "No hay workers Celery respondiendo. Inicia con: `celery -A proyecto_colegio worker -l INFO`.")
            return
        emit(NIVEL_OK, f"Workers Celery vivos: {list(ping.keys())}")
        registered = insp.registered() or {}
        tareas = []
        for tasks in registered.values():
            tareas.extend(tasks)
        if "admisiones.procesar_importacion_aspirantes" in tareas:
            emit(NIVEL_OK, "Tarea `admisiones.procesar_importacion_aspirantes` registrada.")
        else:
            emit(NIVEL_ERR,
                 "La tarea `admisiones.procesar_importacion_aspirantes` NO está registrada en el worker.")
    except Exception as exc:
        emit(NIVEL_WARN, f"No se pudo inspeccionar Celery: {exc}")


def _check_channels(emit):
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
    except ImportError:
        emit(NIVEL_ERR, "Channels no está instalado (`pip install channels channels-redis`).")
        return
    layer = get_channel_layer()
    if layer is None:
        emit(NIVEL_ERR, "CHANNEL_LAYERS no está configurado. El progreso WS no funcionará.")
        return
    try:
        async_to_sync(layer.group_send)("_healthcheck_admisiones_", {"type": "ping"})
        emit(NIVEL_OK, f"Channel layer responde ({type(layer).__name__}).")
    except Exception as exc:
        emit(NIVEL_ERR, f"Channel layer falló al hacer group_send: {exc}")


def _check_plantillas(emit):
    from django.template import TemplateDoesNotExist
    from django.template.loader import get_template
    for nombre in PLANTILLAS_CRITICAS:
        try:
            get_template(nombre)
            emit(NIVEL_OK, f"Plantilla '{nombre}' encontrada.")
        except TemplateDoesNotExist:
            emit(NIVEL_ERR, f"Plantilla '{nombre}' NO existe.")
        except Exception as exc:
            emit(NIVEL_WARN, f"Plantilla '{nombre}': error al cargar ({exc}).")


def _check_urls(emit):
    from django.urls import NoReverseMatch, reverse
    for nombre, kwargs in URLS_CRITICAS:
        try:
            url = reverse(nombre, kwargs=kwargs)
            emit(NIVEL_OK, f"URL '{nombre}' resuelve a {url}.")
        except NoReverseMatch as exc:
            emit(NIVEL_ERR, f"URL '{nombre}' no resuelve: {exc}")


def _check_instituciones(emit, institucion_id):
    from finanzas.models import InstitucionEducativa
    qs = InstitucionEducativa.objects.all()
    if institucion_id:
        qs = qs.filter(pk=institucion_id)
        if not qs.exists():
            emit(NIVEL_ERR, f"No existe la institución con ID {institucion_id}.")
            return
    if not qs.exists():
        emit(NIVEL_WARN, "No hay instituciones registradas en la BD.")
        return
    for inst in qs:
        emit(NIVEL_INFO, f"-> {inst} (id={inst.pk})")
        _check_smtp_inst(emit, inst)
        _check_mercadopago_inst(emit, inst)


def _check_smtp_inst(emit, inst):
    host = getattr(inst, "email_host", "") or ""
    user = getattr(inst, "email_host_user", "") or ""
    password = getattr(inst, "email_host_password", "") or ""
    if host and user and password:
        emit(NIVEL_OK, f"  SMTP configurado ({host}, user={user}).")
    elif host or user or password:
        emit(NIVEL_WARN, f"  SMTP parcialmente configurado (host='{host}', user='{user}'); revisa los 3 campos.")
    else:
        emit(NIVEL_WARN, "  Sin credenciales SMTP. Los correos usarán el backend global.")


def _check_mercadopago_inst(emit, inst):
    modo_prod = bool(getattr(inst, "mp_modo_produccion", False))
    token_prod = (getattr(inst, "mp_access_token_prod", "") or "").strip()
    token_test = (getattr(inst, "mp_access_token_test", "") or "").strip()
    secret = (getattr(inst, "mp_webhook_secret", "") or "").strip()
    token_activo = token_prod if modo_prod else token_test
    modo_label = "PRODUCCIÓN" if modo_prod else "SANDBOX"
    if token_activo:
        emit(NIVEL_OK, f"  Mercado Pago [{modo_label}]: access_token configurado.")
    else:
        emit(NIVEL_WARN, f"  Mercado Pago [{modo_label}]: SIN access_token. Los aspirantes no podrán pagar.")
    if secret:
        emit(NIVEL_OK, "  Mercado Pago: webhook_secret configurado.")
    else:
        emit(NIVEL_ERR, "  Mercado Pago: webhook_secret VACÍO. TODAS las notificaciones se rechazarán con 401.")


def _check_conceptos_pago(emit, institucion_id):
    from finanzas.models import InstitucionEducativa
    from gestion_academica.models import Grado, NivelEscolaridad
    qs_inst = InstitucionEducativa.objects.all()
    if institucion_id:
        qs_inst = qs_inst.filter(pk=institucion_id)
    if not qs_inst.exists():
        emit(NIVEL_WARN, "No hay instituciones para verificar.")
        return
    for inst in qs_inst:
        emit(NIVEL_INFO, f"-> {inst} (id={inst.pk})")
        niveles_ids = (
            Grado.objects
            .filter(institucion=inst, nivel_escolaridad__isnull=False)
            .values_list("nivel_escolaridad_id", flat=True)
            .distinct()
        )
        niveles = NivelEscolaridad.objects.filter(pk__in=list(niveles_ids))
        if not niveles.exists():
            emit(NIVEL_WARN,
                 "  La institución no tiene niveles asignados a grados. No se puede cobrar inscripción ni matrícula.")
            continue
        for nivel in niveles:
            _check_concepto_para_nivel(emit, inst, nivel, flag="es_pago_inscripcion", etiqueta="Inscripción")
            _check_concepto_para_nivel(emit, inst, nivel, flag="es_pago_matricula", etiqueta="Matrícula")
            _check_pensiones_para_nivel(emit, inst, nivel)


def _check_concepto_para_nivel(emit, inst, nivel, *, flag, etiqueta):
    from finanzas.models import ConceptoPago
    qs = ConceptoPago.objects.filter(institucion=inst, nivel_escolaridad=nivel, **{flag: True})
    cantidad = qs.count()
    if cantidad == 1:
        emit(NIVEL_OK, f"  [{etiqueta}] Nivel '{nivel}': 1 concepto configurado ({qs.first().nombre_concepto}).")
    elif cantidad == 0:
        emit(NIVEL_ERR, f"  [{etiqueta}] Nivel '{nivel}': SIN ConceptoPago marcado como '{flag}=True'.")
    else:
        emit(NIVEL_ERR, f"  [{etiqueta}] Nivel '{nivel}': hay {cantidad} ConceptoPago marcados como '{flag}=True'. Deja activo solo uno.")


def _check_pensiones_para_nivel(emit, inst, nivel):
    from finanzas.models import ConceptoPago
    from finanzas.services import _año_lectivo_para
    año = _año_lectivo_para(inst)
    qs = ConceptoPago.objects.filter(institucion=inst, nivel_escolaridad=nivel, es_pago_pension=True)
    cantidad = qs.count()
    if cantidad >= 10:
        emit(NIVEL_OK, f"  [Pensiones] Nivel '{nivel}': {cantidad} conceptos (año lectivo {año}).")
    elif cantidad == 0:
        emit(NIVEL_ERR, f"  [Pensiones] Nivel '{nivel}': 0 conceptos de pensión. Ejecuta `manage.py crear_conceptos`.")
    else:
        emit(NIVEL_WARN, f"  [Pensiones] Nivel '{nivel}': solo {cantidad}/10 conceptos. Ejecuta `manage.py crear_conceptos`.")


def _check_mora_estudiantes(emit, institucion_id):
    from django.utils import timezone
    from finanzas.models import InstitucionEducativa, CuentaPorCobrarEstudiante
    from gestion_academica.models import Estudiante
    qs_inst = InstitucionEducativa.objects.all()
    if institucion_id:
        qs_inst = qs_inst.filter(pk=institucion_id)
    if not qs_inst.exists():
        emit(NIVEL_WARN, "No hay instituciones para verificar.")
        return
    hoy = timezone.localdate()
    for inst in qs_inst:
        emit(NIVEL_INFO, f"-> {inst} (id={inst.pk})")
        bloqueo_activo = bool(getattr(inst, "bloquear_portal_por_mora", True))
        gracia = int(getattr(inst, "dias_gracia_mora", 0) or 0)
        if not bloqueo_activo:
            emit(NIVEL_WARN,
                 "  Bloqueo por mora DESACTIVADO. Ningún estudiante será bloqueado.")
            continue
        estudiantes_qs = Estudiante.objects.filter(institucion=inst, activo=True)
        total = estudiantes_qs.count()
        if total == 0:
            emit(NIVEL_OK, "  Sin estudiantes activos en esta institución.")
            continue
        estudiantes_ids_morosos = set(
            CuentaPorCobrarEstudiante.objects
            .filter(estudiante__institucion=inst, estudiante__activo=True)
            .exclude(estado__in=["PAGADO", "ANULADO"])
            .filter(fecha_vencimiento_especifica__lt=hoy - timezone.timedelta(days=gracia))
            .values_list("estudiante_id", flat=True)
            .distinct()
        )
        morosos = len(estudiantes_ids_morosos)
        pct = (morosos / total * 100) if total else 0.0
        emit(NIVEL_OK,
             f"  Bloqueo activo (gracia {gracia}d). Estudiantes afectados: {morosos}/{total} ({pct:.1f}%).")
        if morosos and morosos / total >= 0.5:
            emit(NIVEL_WARN,
                 "  >50% de los estudiantes están bloqueados. Revisa la causa.")
