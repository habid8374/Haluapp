"""Cliente centralizado de Mercado Pago para Halu (multi-tenant).

Por qué este módulo:
- Cada institución tiene credenciales propias (test/prod) y `mp_modo_produccion`.
  Centralizar la elección del access_token aquí evita que cada vista lo repita
  (y se equivoque).
- El SDK oficial de MP no tiene reintentos ni timeout sano por defecto. Aquí
  envolvemos las dos operaciones que usamos (crear preferencia / consultar
  pago) con backoff exponencial y timeout duro.
- Cada llamada queda auditada en ``LlamadaMercadoPago``: si mañana hay una
  disputa con un padre de familia, sabemos qué se llamó, cuándo, con qué
  monto, qué respondió MP y cuánto tardó.

Uso desde una vista:
    from finanzas.mercadopago_client import crear_preferencia, consultar_pago
    resp = crear_preferencia(institucion, payload=preference_data, cuenta=cuenta)
    pago = consultar_pago(institucion, payment_id=12345, cuenta=cuenta)
"""
from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any, Optional

import mercadopago
from django.utils import timezone

from finanzas.models import InstitucionEducativa, LlamadaMercadoPago

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------------
# Excepciones
# ----------------------------------------------------------------------------

class MercadoPagoError(Exception):
    """Error estructurado al hablar con MP. Lo usan vistas y comandos."""

    def __init__(
        self,
        mensaje: str,
        *,
        estado_http: int = 0,
        respuesta: Optional[dict] = None,
        recuperable: bool = False,
    ):
        super().__init__(mensaje)
        self.estado_http = estado_http
        self.respuesta = respuesta or {}
        self.recuperable = recuperable


class MercadoPagoSinCredenciales(MercadoPagoError):
    """La institución no tiene access_token configurado para el modo activo."""


# ----------------------------------------------------------------------------
# Configuración de reintentos
# ----------------------------------------------------------------------------

REINTENTOS_MAX = 3
BACKOFF_BASE_SEG = 1.0  # 1, 2, 4 segundos
ESTADOS_HTTP_RECUPERABLES = {408, 425, 429, 500, 502, 503, 504}


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def obtener_access_token(institucion: InstitucionEducativa) -> str:
    """Devuelve el access_token activo según ``mp_modo_produccion``.

    Lanza ``MercadoPagoSinCredenciales`` si falta, para que el caller pueda
    devolver un error claro al usuario en vez de un crash genérico.
    """
    if institucion is None:
        raise MercadoPagoSinCredenciales("No se proporcionó institución.")
    if institucion.mp_modo_produccion:
        token = (institucion.mp_access_token_prod or "").strip()
        modo = "producción"
    else:
        token = (institucion.mp_access_token_test or "").strip()
        modo = "sandbox"
    if not token:
        raise MercadoPagoSinCredenciales(
            f"La institución '{institucion}' no tiene access_token de Mercado Pago "
            f"configurado para el modo '{modo}'."
        )
    return token


def _resumir_dict(data: Any, campos: tuple[str, ...]) -> dict:
    """Devuelve un subset 'auditable' (sin tokens, sin tarjetas) de un dict."""
    if not isinstance(data, dict):
        return {}
    return {k: data[k] for k in campos if k in data}


def _resumen_request_preferencia(payload: dict) -> dict:
    items = payload.get("items") or []
    return {
        "external_reference": payload.get("external_reference"),
        "n_items": len(items),
        "monto_total": sum(
            (i.get("unit_price", 0) or 0) * (i.get("quantity", 1) or 1)
            for i in items
        ),
        "currency": (items[0] or {}).get("currency_id") if items else None,
        "notification_url_presente": bool(payload.get("notification_url")),
    }


def _resumen_response_preferencia(resp: dict) -> dict:
    body = resp.get("response") or {}
    return _resumir_dict(
        body,
        ("id", "status", "init_point", "sandbox_init_point", "external_reference"),
    )


def _resumen_response_payment(resp: dict) -> dict:
    body = resp.get("response") or {}
    return _resumir_dict(
        body,
        (
            "id", "status", "status_detail",
            "transaction_amount", "external_reference",
            "payment_method_id", "payment_type_id",
            "date_approved", "currency_id",
        ),
    )


def _es_recuperable(status: int, exc: Optional[BaseException]) -> bool:
    if status in ESTADOS_HTTP_RECUPERABLES:
        return True
    if exc is not None:
        # El SDK de MP usa requests por debajo: timeouts/conexión son recuperables.
        nombre = type(exc).__name__.lower()
        if "timeout" in nombre or "connection" in nombre or "ssl" in nombre:
            return True
    return False


# ----------------------------------------------------------------------------
# Auditoría
# ----------------------------------------------------------------------------

def _registrar_llamada(
    *,
    institucion: InstitucionEducativa,
    accion: str,
    intento: int,
    latencia_ms: int,
    estado_http: int,
    exito: bool,
    error_mensaje: str = "",
    request_resumen: Optional[dict] = None,
    response_resumen: Optional[dict] = None,
    external_reference: str = "",
    monto: Optional[Decimal] = None,
    cuenta=None,
) -> None:
    """Persiste una entrada de auditoría. Nunca debe romper el flujo principal."""
    try:
        LlamadaMercadoPago.objects.create(
            institucion=institucion,
            accion=accion,
            external_reference=external_reference or "",
            monto=monto,
            cuenta=cuenta,
            intento=intento,
            latencia_ms=latencia_ms,
            estado_http=estado_http,
            exito=exito,
            error_mensaje=(error_mensaje or "")[:2000],
            request_resumen=request_resumen or {},
            response_resumen=response_resumen or {},
            modo_produccion=bool(institucion.mp_modo_produccion),
        )
    except Exception as exc:
        # La auditoría JAMÁS debe tumbar la operación real.
        logger.error("No se pudo persistir LlamadaMercadoPago: %s", exc, exc_info=True)


# ----------------------------------------------------------------------------
# Operaciones expuestas
# ----------------------------------------------------------------------------

def crear_preferencia(
    institucion: InstitucionEducativa,
    *,
    payload: dict,
    cuenta=None,
) -> dict:
    """Crea una preferencia con reintentos + auditoría.

    Devuelve el ``response['response']`` (el body útil) en éxito.
    Lanza ``MercadoPagoError`` en fallo definitivo.
    """
    token = obtener_access_token(institucion)
    sdk = mercadopago.SDK(token)

    request_resumen = _resumen_request_preferencia(payload)
    external_reference = str(payload.get("external_reference") or "")
    monto = Decimal(str(request_resumen.get("monto_total") or "0"))

    ultimo_error: Optional[Exception] = None
    for intento in range(1, REINTENTOS_MAX + 1):
        t0 = time.monotonic()
        estado_http = 0
        respuesta = None
        try:
            respuesta = sdk.preference().create(payload)
            estado_http = int(respuesta.get("status") or 0)
            latencia_ms = int((time.monotonic() - t0) * 1000)

            response_resumen = _resumen_response_preferencia(respuesta)
            exito = 200 <= estado_http < 300

            _registrar_llamada(
                institucion=institucion,
                accion=LlamadaMercadoPago.Accion.PREFERENCE_CREATE,
                intento=intento,
                latencia_ms=latencia_ms,
                estado_http=estado_http,
                exito=exito,
                error_mensaje=(
                    "" if exito else
                    str((respuesta.get("response") or {}).get("message") or "")[:1000]
                ),
                request_resumen=request_resumen,
                response_resumen=response_resumen,
                external_reference=external_reference,
                monto=monto,
                cuenta=cuenta,
            )

            if exito:
                return respuesta.get("response") or {}

            if not _es_recuperable(estado_http, None) or intento == REINTENTOS_MAX:
                raise MercadoPagoError(
                    f"Mercado Pago rechazó la creación de la preferencia: HTTP {estado_http}.",
                    estado_http=estado_http,
                    respuesta=respuesta.get("response") or {},
                    recuperable=False,
                )
        except MercadoPagoError:
            raise
        except Exception as exc:
            latencia_ms = int((time.monotonic() - t0) * 1000)
            ultimo_error = exc
            recuperable = _es_recuperable(estado_http, exc)
            _registrar_llamada(
                institucion=institucion,
                accion=LlamadaMercadoPago.Accion.PREFERENCE_CREATE,
                intento=intento,
                latencia_ms=latencia_ms,
                estado_http=estado_http,
                exito=False,
                error_mensaje=f"{type(exc).__name__}: {exc}",
                request_resumen=request_resumen,
                external_reference=external_reference,
                monto=monto,
                cuenta=cuenta,
            )
            if not recuperable or intento == REINTENTOS_MAX:
                raise MercadoPagoError(
                    f"Error al llamar a Mercado Pago tras {intento} intento(s): {exc}",
                    estado_http=estado_http,
                    recuperable=recuperable,
                ) from exc

        # Backoff exponencial antes del siguiente intento.
        time.sleep(BACKOFF_BASE_SEG * (2 ** (intento - 1)))

    # En teoría inalcanzable, pero por defensa:
    raise MercadoPagoError(
        f"Falló la creación de preferencia tras {REINTENTOS_MAX} intentos.",
        estado_http=0,
    ) from ultimo_error


def consultar_pago(
    institucion: InstitucionEducativa,
    *,
    payment_id: str,
    cuenta=None,
    external_reference: str = "",
) -> dict:
    """Consulta un pago en MP con reintentos + auditoría.

    Devuelve el ``response['response']`` (info del pago) en éxito.
    """
    token = obtener_access_token(institucion)
    sdk = mercadopago.SDK(token)

    request_resumen = {"payment_id": str(payment_id)}

    ultimo_error: Optional[Exception] = None
    for intento in range(1, REINTENTOS_MAX + 1):
        t0 = time.monotonic()
        estado_http = 0
        respuesta = None
        try:
            respuesta = sdk.payment().get(payment_id)
            estado_http = int(respuesta.get("status") or 0)
            latencia_ms = int((time.monotonic() - t0) * 1000)

            response_resumen = _resumen_response_payment(respuesta)
            body = respuesta.get("response") or {}
            exito = 200 <= estado_http < 300

            _registrar_llamada(
                institucion=institucion,
                accion=LlamadaMercadoPago.Accion.PAYMENT_GET,
                intento=intento,
                latencia_ms=latencia_ms,
                estado_http=estado_http,
                exito=exito,
                error_mensaje="" if exito else str(body.get("message") or "")[:1000],
                request_resumen=request_resumen,
                response_resumen=response_resumen,
                external_reference=external_reference or str(body.get("external_reference") or ""),
                monto=Decimal(str(body.get("transaction_amount") or "0")) if body.get("transaction_amount") else None,
                cuenta=cuenta,
            )

            if exito:
                return body

            if not _es_recuperable(estado_http, None) or intento == REINTENTOS_MAX:
                raise MercadoPagoError(
                    f"Mercado Pago rechazó la consulta del pago {payment_id}: HTTP {estado_http}.",
                    estado_http=estado_http,
                    respuesta=body,
                )
        except MercadoPagoError:
            raise
        except Exception as exc:
            latencia_ms = int((time.monotonic() - t0) * 1000)
            ultimo_error = exc
            recuperable = _es_recuperable(estado_http, exc)
            _registrar_llamada(
                institucion=institucion,
                accion=LlamadaMercadoPago.Accion.PAYMENT_GET,
                intento=intento,
                latencia_ms=latencia_ms,
                estado_http=estado_http,
                exito=False,
                error_mensaje=f"{type(exc).__name__}: {exc}",
                request_resumen=request_resumen,
                external_reference=external_reference,
                cuenta=cuenta,
            )
            if not recuperable or intento == REINTENTOS_MAX:
                raise MercadoPagoError(
                    f"Error al consultar el pago {payment_id} tras {intento} intento(s): {exc}",
                    estado_http=estado_http,
                    recuperable=recuperable,
                ) from exc

        time.sleep(BACKOFF_BASE_SEG * (2 ** (intento - 1)))

    raise MercadoPagoError(
        f"Falló la consulta del pago {payment_id} tras {REINTENTOS_MAX} intentos.",
        estado_http=0,
    ) from ultimo_error


def buscar_pagos_aprobados(
    institucion: InstitucionEducativa,
    *,
    desde,
    hasta,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Busca pagos APROBADOS en un rango de fechas (para reconciliación).

    Devuelve la respuesta cruda de `payment.search`. El reconciliador maneja
    la paginación llamando varias veces con `offset`.
    """
    token = obtener_access_token(institucion)
    sdk = mercadopago.SDK(token)

    filtros = {
        "status": "approved",
        "begin_date": desde.isoformat() + "T00:00:00.000-05:00",
        "end_date": hasta.isoformat() + "T23:59:59.999-05:00",
        "range": "date_approved",
        "limit": limit,
        "offset": offset,
    }
    request_resumen = dict(filtros)

    t0 = time.monotonic()
    estado_http = 0
    try:
        respuesta = sdk.payment().search(filtros)
        estado_http = int(respuesta.get("status") or 0)
        latencia_ms = int((time.monotonic() - t0) * 1000)
        body = respuesta.get("response") or {}
        exito = 200 <= estado_http < 300
        _registrar_llamada(
            institucion=institucion,
            accion=LlamadaMercadoPago.Accion.PAYMENT_SEARCH,
            intento=1,
            latencia_ms=latencia_ms,
            estado_http=estado_http,
            exito=exito,
            error_mensaje="" if exito else str(body.get("message") or "")[:1000],
            request_resumen=request_resumen,
            response_resumen={
                "total": (body.get("paging") or {}).get("total"),
                "limit": (body.get("paging") or {}).get("limit"),
                "offset": (body.get("paging") or {}).get("offset"),
            },
        )
        if not exito:
            raise MercadoPagoError(
                f"payment.search devolvió HTTP {estado_http}.",
                estado_http=estado_http,
                respuesta=body,
            )
        return body
    except MercadoPagoError:
        raise
    except Exception as exc:
        latencia_ms = int((time.monotonic() - t0) * 1000)
        _registrar_llamada(
            institucion=institucion,
            accion=LlamadaMercadoPago.Accion.PAYMENT_SEARCH,
            intento=1,
            latencia_ms=latencia_ms,
            estado_http=estado_http,
            exito=False,
            error_mensaje=f"{type(exc).__name__}: {exc}",
            request_resumen=request_resumen,
        )
        raise MercadoPagoError(
            f"Error al buscar pagos aprobados: {exc}",
            estado_http=estado_http,
        ) from exc
