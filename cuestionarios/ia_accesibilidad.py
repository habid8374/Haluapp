# cuestionarios/ia_accesibilidad.py
"""IA de apoyo a la accesibilidad (Ola 3).

Dos funciones reutilizables y TOLERANTES A FALLOS:

- `simplificar_texto(institucion, texto)`  → enunciado en "lectura fácil".
- `describir_imagen(institucion, imagen)`  → texto alternativo (alt) de una imagen.

Ambas usan la credencial de IA de LA institución (nunca una global): Google
Gemini como motor principal y, si está configurada, Claude (Anthropic) como
respaldo automático — igual que el resto de la plataforma. Si no hay credencial
o se agotó la cuota, devuelven `(False, mensaje)` en vez de romper: la interfaz
muestra un aviso amable y sigue funcionando sin la ayuda de IA.

Devuelven siempre una tupla `(ok: bool, resultado_o_mensaje: str)`.
"""
import logging
import mimetypes

from finanzas.institucion_credentials import (
    google_api_key as _google_api_key,
    claude_api_key as _claude_api_key,
)

logger = logging.getLogger(__name__)

_MODELO_GEMINI = 'gemini-2.5-flash'
_MODELO_CLAUDE = 'claude-sonnet-4-20250514'  # respaldo; ajustable por la institución

_PROMPT_SIMPLE = (
    "Reescribe el siguiente enunciado escolar en 'lectura fácil' para un "
    "estudiante con dificultades de lectura o comprensión. Usa frases cortas y "
    "palabras sencillas, conserva EXACTAMENTE el significado y no reveles ni "
    "cambies la respuesta. Responde solo con el texto reescrito, en español.\n\n"
    "Enunciado:\n\"\"\"{texto}\"\"\""
)
_PROMPT_ALT = (
    "Escribe el texto alternativo (alt) de esta imagen para un estudiante con "
    "discapacidad visual. Descripción objetiva y breve (máximo 2 frases), en "
    "español. No interpretes cuál es la respuesta correcta. Responde solo con la "
    "descripción."
)


def _sin_credenciales_msg():
    return (False, "La institución no tiene configurada una API de IA (Gemini o Claude).")


# ── Gemini ────────────────────────────────────────────────────────────────────

def _gemini_texto(api_key, prompt):
    from google import genai
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(model=_MODELO_GEMINI, contents=prompt)
    return (resp.text or '').strip()


def _gemini_imagen(api_key, data, mime):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model=_MODELO_GEMINI,
        contents=[types.Part.from_bytes(data=data, mime_type=mime), _PROMPT_ALT],
    )
    return (resp.text or '').strip()


# ── Claude (respaldo, solo texto) ───────────────────────────────────────────────

def _claude_texto(api_key, prompt):
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=_MODELO_CLAUDE,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    partes = [b.text for b in msg.content if getattr(b, 'type', '') == 'text']
    return "\n".join(partes).strip()


# ── API pública ─────────────────────────────────────────────────────────────────

def simplificar_texto(institucion, texto):
    texto = (texto or '').strip()
    if not texto:
        return (False, "No hay texto para simplificar.")
    prompt = _PROMPT_SIMPLE.format(texto=texto)

    gkey = _google_api_key(institucion)
    if gkey:
        try:
            out = _gemini_texto(gkey, prompt)
            if out:
                return (True, out)
        except Exception as exc:
            logger.warning("Simplificar (Gemini) falló: %s", exc)

    ckey = _claude_api_key(institucion)
    if ckey:
        try:
            out = _claude_texto(ckey, prompt)
            if out:
                return (True, out)
        except Exception as exc:
            logger.warning("Simplificar (Claude) falló: %s", exc)

    if not gkey and not ckey:
        return _sin_credenciales_msg()
    return (False, "La IA no está disponible en este momento (cuota o error). Intenta más tarde.")


def describir_imagen(institucion, imagen):
    """`imagen` es un FieldFile (pregunta.imagen). Devuelve (ok, alt)."""
    if not imagen:
        return (False, "La pregunta no tiene imagen.")
    gkey = _google_api_key(institucion)
    if not gkey:
        # La descripción de imágenes requiere Gemini (visión).
        return (False, "Para describir imágenes se necesita la API de Google (Gemini) de la institución.")
    try:
        with imagen.open('rb') as fh:
            data = fh.read()
        mime = mimetypes.guess_type(imagen.name)[0] or 'image/jpeg'
        out = _gemini_imagen(gkey, data, mime)
        if out:
            return (True, out)
        return (False, "La IA no devolvió una descripción.")
    except Exception as exc:
        logger.warning("Describir imagen (Gemini) falló: %s", exc)
        return (False, "La IA no está disponible en este momento (cuota o error). Intenta más tarde.")
