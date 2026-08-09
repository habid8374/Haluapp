# finanzas/ia.py
"""Compuerta central de IA con TOPE y MEDICIÓN de consumo por institución.

Todas las llamadas a IA deberían pasar por aquí para:
  1) revisar el tope mensual de la institución (puede_usar_ia),
  2) llamar a Gemini (principal) o Claude (respaldo, Haiku por costo),
  3) registrar el consumo (tokens + costo estimado en COP) para el panel y el tope.

Tolerante a fallos: si no hay credencial, se agotó la cuota o se superó el tope,
devuelve (False, mensaje) en vez de romper. Usa SIEMPRE la credencial de LA
institución (nunca una global), en línea con la regla multi-institución.
"""
import logging
from decimal import Decimal

from django.db.models import F
from django.utils import timezone

from finanzas.institucion_credentials import (
    google_api_key as _google_api_key,
    claude_api_key as _claude_api_key,
)

logger = logging.getLogger(__name__)

_MODELO_GEMINI = 'gemini-2.5-flash'
# Claude solo es respaldo → Haiku 4.5 (el más económico).
_MODELO_CLAUDE = 'claude-haiku-4-5-20251001'

# Precio aproximado por 1M de tokens (USD). Ajustable si cambian las tarifas.
_PRECIOS_USD = {
    _MODELO_GEMINI: (0.30, 2.50),          # gemini-2.5-flash (entrada, salida)
    'gemini-2.0-flash': (0.10, 0.40),
    'gemini-2.5-pro': (1.25, 10.00),
    _MODELO_CLAUDE: (1.00, 5.00),          # claude haiku 4.5
}
_TRM_COP = Decimal('4000')  # TRM aproximada USD→COP (ajustable).


class IATopeSuperado(Exception):
    """Se lanza cuando la institución alcanzó su tope de IA del mes (bloqueo suave)."""


def _mes_actual():
    now = timezone.now()
    return now.year, now.month


def _costo_cop(modelo, tin, tout):
    pin, pout = _PRECIOS_USD.get(modelo, (0.30, 2.50))
    usd = Decimal(str(tin or 0)) / Decimal('1000000') * Decimal(str(pin)) \
        + Decimal(str(tout or 0)) / Decimal('1000000') * Decimal(str(pout))
    return (usd * _TRM_COP).quantize(Decimal('0.01'))


def _tokens_gemini(resp):
    um = getattr(resp, 'usage_metadata', None)
    tin = getattr(um, 'prompt_token_count', 0) or 0
    tout = getattr(um, 'candidates_token_count', 0) or 0
    return tin, tout


def puede_usar_ia(institucion):
    """(bool, mensaje). False solo si hay tope activo, con bloqueo, y ya se superó."""
    if institucion is None:
        return True, ''
    tope = getattr(institucion, 'ia_tope_mensual_cop', 0) or 0
    if not tope or Decimal(str(tope)) <= 0:
        return True, ''
    if not getattr(institucion, 'ia_bloquear_al_superar', True):
        return True, ''  # solo mide, no bloquea
    from .models import ConsumoIA
    anio, mes = _mes_actual()
    c = ConsumoIA.objects.filter(institucion=institucion, anio=anio, mes=mes).first()
    usado = c.costo_estimado_cop if c else Decimal('0')
    if usado >= Decimal(str(tope)):
        return False, "Se alcanzó el límite de IA de este mes para la institución."
    return True, ''


def registrar_uso(institucion, modelo, tin, tout):
    """Acumula el consumo del mes (operaciones, tokens, costo) de forma atómica."""
    if institucion is None:
        return
    from .models import ConsumoIA
    anio, mes = _mes_actual()
    costo = _costo_cop(modelo, tin, tout)
    obj, _creado = ConsumoIA.objects.get_or_create(institucion=institucion, anio=anio, mes=mes)
    ConsumoIA.objects.filter(pk=obj.pk).update(
        operaciones=F('operaciones') + 1,
        tokens_in=F('tokens_in') + (tin or 0),
        tokens_out=F('tokens_out') + (tout or 0),
        costo_estimado_cop=F('costo_estimado_cop') + costo,
    )


def resumen_mes(institucion):
    """Dict con el consumo del mes en curso y el tope (para paneles)."""
    from .models import ConsumoIA
    anio, mes = _mes_actual()
    c = ConsumoIA.objects.filter(institucion=institucion, anio=anio, mes=mes).first()
    tope = Decimal(str(getattr(institucion, 'ia_tope_mensual_cop', 0) or 0))
    usado = c.costo_estimado_cop if c else Decimal('0')
    restante = (tope - usado) if tope > 0 else None
    pct = (float(usado / tope * 100) if tope > 0 else None)
    return {
        'anio': anio, 'mes': mes,
        'operaciones': c.operaciones if c else 0,
        'usado_cop': usado, 'tope_cop': tope,
        'restante_cop': restante, 'pct': pct,
    }


def gemini_generate(institucion, model, contents, config=None):
    """Envoltura ÚNICA para llamar a Gemini con tope + medición.

    - Revisa el tope: si se superó (y está el bloqueo), lanza `IATopeSuperado`.
    - Llama a `generate_content` con el modelo/config dados.
    - Registra el consumo (tokens + costo estimado).
    - Devuelve el objeto `response` (para no cambiar el código que lee `.text`).

    Úsala en TODOS los puntos que hoy hacen `genai.Client(...).models.generate_content(...)`.
    """
    ok, msg = puede_usar_ia(institucion)
    if not ok:
        raise IATopeSuperado(msg)
    from google import genai
    api_key = _google_api_key(institucion)
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(model=model, contents=contents, config=config)
    try:
        tin, tout = _tokens_gemini(resp)
        registrar_uso(institucion, model, tin, tout)
    except Exception:
        pass
    return resp


def generar_texto(institucion, prompt, json=False):
    """Genera texto con IA (Gemini principal, Claude Haiku respaldo). Aplica tope y
    registra consumo. Devuelve (ok, texto_o_mensaje)."""
    ok, msg = puede_usar_ia(institucion)
    if not ok:
        return False, msg

    gkey = _google_api_key(institucion)
    if gkey:
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=gkey)
            cfg = types.GenerateContentConfig(response_mime_type="application/json") if json else None
            resp = client.models.generate_content(model=_MODELO_GEMINI, contents=prompt, config=cfg)
            tin, tout = _tokens_gemini(resp)
            registrar_uso(institucion, _MODELO_GEMINI, tin, tout)
            txt = (resp.text or '').strip()
            if txt:
                return True, txt
        except Exception as exc:
            logger.warning("IA Gemini falló: %s", exc)

    ckey = _claude_api_key(institucion)
    if ckey:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=ckey)
            m = client.messages.create(
                model=_MODELO_CLAUDE, max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            txt = "\n".join(b.text for b in m.content if getattr(b, 'type', '') == 'text').strip()
            u = getattr(m, 'usage', None)
            registrar_uso(institucion, _MODELO_CLAUDE,
                          getattr(u, 'input_tokens', 0), getattr(u, 'output_tokens', 0))
            if txt:
                return True, txt
        except Exception as exc:
            logger.warning("IA Claude falló: %s", exc)

    if not gkey and not ckey:
        return False, "La institución no tiene configurada una API de IA (Gemini o Claude)."
    return False, "La IA no está disponible en este momento (cuota/límite o error). Intenta más tarde."


def generar_desde_imagen(institucion, data, mime, prompt):
    """Describe/analiza una imagen con Gemini (visión). Aplica tope y registra
    consumo. Devuelve (ok, texto_o_mensaje)."""
    ok, msg = puede_usar_ia(institucion)
    if not ok:
        return False, msg
    gkey = _google_api_key(institucion)
    if not gkey:
        return False, "Para analizar imágenes se necesita la API de Google (Gemini) de la institución."
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=gkey)
        resp = client.models.generate_content(
            model=_MODELO_GEMINI,
            contents=[types.Part.from_bytes(data=data, mime_type=mime), prompt],
        )
        tin, tout = _tokens_gemini(resp)
        registrar_uso(institucion, _MODELO_GEMINI, tin, tout)
        txt = (resp.text or '').strip()
        if txt:
            return True, txt
        return False, "La IA no devolvió una respuesta."
    except Exception as exc:
        logger.warning("IA Gemini (imagen) falló: %s", exc)
        return False, "La IA no está disponible en este momento (cuota/límite o error)."


_PROMPT_TRANSCRIBIR = (
    "Transcribe fielmente el audio a texto en español, como subtítulo para un "
    "estudiante sordo o con dificultad auditiva. Escribe solo la transcripción, "
    "sin comentarios, marcas de tiempo ni interpretación. Conserva el sentido y "
    "la puntuación natural."
)


def transcribir_audio(institucion, data, mime, prompt=None):
    """Transcribe un audio a texto con Gemini (subtítulos/accesibilidad auditiva).
    Aplica el tope de IA y registra el consumo. Devuelve (ok, texto_o_mensaje).

    `data` son los bytes del audio; `mime` su tipo (audio/mpeg, audio/ogg, …).
    Usa exclusivamente la credencial Gemini de LA institución (regla multi-tenant).
    """
    ok, msg = puede_usar_ia(institucion)
    if not ok:
        return False, msg
    gkey = _google_api_key(institucion)
    if not gkey:
        return False, "Para transcribir audio se necesita la API de Google (Gemini) de la institución."
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=gkey)
        resp = client.models.generate_content(
            model=_MODELO_GEMINI,
            contents=[
                types.Part.from_bytes(data=data, mime_type=mime),
                prompt or _PROMPT_TRANSCRIBIR,
            ],
        )
        tin, tout = _tokens_gemini(resp)
        registrar_uso(institucion, _MODELO_GEMINI, tin, tout)
        txt = (resp.text or '').strip()
        if txt:
            return True, txt
        return False, "La IA no devolvió una transcripción."
    except Exception as exc:
        logger.warning("IA Gemini (audio) falló: %s", exc)
        return False, "La IA no está disponible en este momento (cuota/límite o error)."
