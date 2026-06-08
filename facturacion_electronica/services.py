"""Cliente de la API de Factus (facturación electrónica DIAN, Colombia).

Documentación: https://developers.factus.com.co/

Flujo:
  1. Autenticación OAuth2 (password grant) -> POST /oauth/token  (token dura ~1h)
  2. Crear y validar factura            -> POST /v2/bills/validate
  3. Consultar factura                  -> GET  /v2/bills/show/{number}

El token se cachea (Django cache) por institución+ambiente ~55 min para no
re-autenticar en cada emisión.
"""
from __future__ import annotations

import logging

import requests
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Tiempo de vida del token en caché (el token dura 1h; dejamos margen)
TOKEN_TTL_SEGUNDOS = 55 * 60
HTTP_TIMEOUT = 30

BASE_URLS = {
    "SANDBOX": "https://api-sandbox.factus.com.co",
    "PRODUCCION": "https://api.factus.com.co",
}

# ──────────────────────────────────────────────────────────────────────────
# Endpoints de documentos (rutas v2 de Factus). Validados en sandbox salvo el
# de NOTA DÉBITO.
# ──────────────────────────────────────────────────────────────────────────
ENDPOINT_FACTURA = "/v2/bills/validate"            # ✅ validado (201)
ENDPOINT_NOTA_CREDITO = "/v2/credit-notes/validate"  # ✅ validado (201)

# ⚠️⚠️ TODO — ENDPOINT A CONFIRMAR CON FACTUS ⚠️⚠️
# '/v2/debit-notes/validate' responde 405 (solo GET/HEAD). Cuando soporte de
# Factus confirme el endpoint + método correctos para CREAR la nota débito,
# actualiza SOLO esta constante (y, si el método no es POST o el JSON difiere,
# avisa para ajustar crear_nota_debito / construir_payload_nota).
ENDPOINT_NOTA_DEBITO = "/v2/debit-notes/validate"  # <-- CAMBIAR cuando Factus confirme


class FactusError(Exception):
    """Error genérico al comunicarse con Factus."""


class FactusNoConfigurado(FactusError):
    """La institución no tiene Factus activo o le faltan credenciales."""


class FactusClient:
    """Cliente delgado sobre la API de Factus para una institución concreta."""

    def __init__(self, config):
        """``config`` es una instancia de ``ConfiguracionFactus``."""
        self.config = config
        self.base_url = BASE_URLS.get(config.ambiente, BASE_URLS["SANDBOX"]).rstrip("/")

    # ──────────────────────────────────────────────────────────────
    # Autenticación
    # ──────────────────────────────────────────────────────────────
    def _cache_key(self) -> str:
        return f"factus_token:{self.config.institucion_id}:{self.config.ambiente}"

    def _validar_credenciales(self):
        if not self.config.activo:
            raise FactusNoConfigurado("El módulo de facturación electrónica no está activo para esta institución.")
        if not self.config.credenciales_completas:
            raise FactusNoConfigurado("Faltan credenciales de Factus (client_id/secret, usuario o contraseña).")

    def obtener_token(self, forzar: bool = False) -> str:
        """Devuelve un access token válido, usando caché cuando sea posible."""
        self._validar_credenciales()

        key = self._cache_key()
        if not forzar:
            cached = cache.get(key)
            if cached:
                return cached

        url = f"{self.base_url}/oauth/token"
        data = {
            "grant_type": "password",
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "username": self.config.username,
            "password": self.config.password,
        }
        try:
            resp = requests.post(url, data=data, timeout=HTTP_TIMEOUT)
        except requests.RequestException as exc:
            raise FactusError(f"No se pudo conectar con Factus: {exc}") from exc

        if resp.status_code != 200:
            logger.error("Factus auth %s: %s", resp.status_code, resp.text[:500])
            raise FactusError(f"Autenticación con Factus falló ({resp.status_code}): {resp.text[:300]}")

        body = resp.json()
        token = body.get("access_token")
        if not token:
            raise FactusError("Factus no devolvió 'access_token'.")

        # Respetar expires_in si viene; si no, usar TTL por defecto con margen.
        expires_in = body.get("expires_in") or 3600
        ttl = max(60, int(expires_in) - 300)
        cache.set(key, token, min(ttl, TOKEN_TTL_SEGUNDOS))
        return token

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.obtener_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ──────────────────────────────────────────────────────────────
    # Operaciones
    # ──────────────────────────────────────────────────────────────
    def probar_conexion(self) -> dict:
        """Verifica credenciales obteniendo un token. Útil al configurar."""
        token = self.obtener_token(forzar=True)
        return {"ok": True, "token_preview": token[:12] + "…"}

    def listar_rangos_numeracion(self) -> list[dict]:
        """Devuelve los rangos de numeración DIAN disponibles en la cuenta Factus.

        Cada ítem tiene: id, prefix, from, to, current, resolution_number, document_type.
        """
        url = f"{self.base_url}/v1/numbering-ranges"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=HTTP_TIMEOUT)
        except requests.RequestException as exc:
            raise FactusError(f"No se pudo conectar con Factus: {exc}") from exc
        if resp.status_code in (401, 403):
            self.obtener_token(forzar=True)
            try:
                resp = requests.get(url, headers=self._headers(), timeout=HTTP_TIMEOUT)
            except requests.RequestException as exc:
                raise FactusError(f"No se pudo conectar con Factus: {exc}") from exc
        body = _safe_json(resp)
        if resp.status_code != 200:
            raise FactusError(
                f"Factus no devolvió rangos ({resp.status_code}): {body.get('message') or resp.text[:200]}"
            )
        # Factus puede devolver {"data": [...]} o directamente [...]
        if isinstance(body, list):
            return body
        return body.get("data", body.get("numbering_ranges", []))

    def crear_factura(self, payload: dict) -> dict:
        """Crea y valida la factura ante la DIAN. Lanza FactusError si falla."""
        return self._post_documento(ENDPOINT_FACTURA, payload, "factura")

    def crear_nota_credito(self, payload: dict) -> dict:
        """Nota crédito (anula/reduce una factura)."""
        return self._post_documento(ENDPOINT_NOTA_CREDITO, payload, "nota crédito")

    def crear_nota_debito(self, payload: dict) -> dict:
        """Nota débito (incrementa una factura).

        ⚠️ El endpoint (ENDPOINT_NOTA_DEBITO) está PENDIENTE de confirmar con Factus
        (ver constante arriba). Cuando lo confirmen, basta actualizar esa constante.
        """
        return self._post_documento(ENDPOINT_NOTA_DEBITO, payload, "nota débito")

    def _post_documento(self, path: str, payload: dict, etiqueta: str) -> dict:
        url = f"{self.base_url}{path}"
        try:
            resp = requests.post(url, json=payload, headers=self._headers(), timeout=HTTP_TIMEOUT)
        except requests.RequestException as exc:
            raise FactusError(f"No se pudo conectar con Factus: {exc}") from exc
        if resp.status_code in (401, 403):
            self.obtener_token(forzar=True)
            try:
                resp = requests.post(url, json=payload, headers=self._headers(), timeout=HTTP_TIMEOUT)
            except requests.RequestException as exc:
                raise FactusError(f"No se pudo conectar con Factus: {exc}") from exc
        body = _safe_json(resp)
        if resp.status_code not in (200, 201):
            logger.error("Factus %s %s: %s", etiqueta, resp.status_code, resp.text[:800])
            raise FactusError(
                f"Factus rechazó la {etiqueta} ({resp.status_code}): {body.get('message') or resp.text[:300]}"
            )
        return body

    def consultar_factura(self, numero: str) -> dict:
        url = f"{self.base_url}/v2/bills/show/{numero}"
        try:
            resp = requests.get(url, headers=self._headers(), timeout=HTTP_TIMEOUT)
        except requests.RequestException as exc:
            raise FactusError(f"No se pudo conectar con Factus: {exc}") from exc
        return _safe_json(resp)


def _safe_json(resp) -> dict:
    try:
        return resp.json()
    except ValueError:
        return {"raw": resp.text}


def cliente_para(institucion):
    """Devuelve un ``FactusClient`` listo para la institución, o lanza FactusNoConfigurado."""
    from .models import ConfiguracionFactus

    config = ConfiguracionFactus.objects.filter(institucion=institucion).first()
    if not config:
        raise FactusNoConfigurado("La institución no tiene configuración de Factus.")
    return FactusClient(config)
