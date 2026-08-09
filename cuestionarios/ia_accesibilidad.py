# cuestionarios/ia_accesibilidad.py
"""IA de apoyo a la accesibilidad (Ola 3).

- `simplificar_texto(institucion, texto)`  → enunciado en "lectura fácil".
- `describir_imagen(institucion, imagen)`  → texto alternativo (alt) de una imagen.

Delegan en la compuerta central `finanzas.ia`, que aplica el TOPE de IA de la
institución, registra el consumo (tokens/costo) y usa Gemini (principal) con
Claude (respaldo). Devuelven `(ok, resultado_o_mensaje)`.
"""
import logging
import mimetypes

from finanzas import ia as _ia

logger = logging.getLogger(__name__)

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


def simplificar_texto(institucion, texto):
    texto = (texto or '').strip()
    if not texto:
        return (False, "No hay texto para simplificar.")
    return _ia.generar_texto(institucion, _PROMPT_SIMPLE.format(texto=texto))


def describir_imagen(institucion, imagen):
    """`imagen` es un FieldFile (pregunta.imagen). Devuelve (ok, alt)."""
    if not imagen:
        return (False, "La pregunta no tiene imagen.")
    try:
        with imagen.open('rb') as fh:
            data = fh.read()
        mime = mimetypes.guess_type(imagen.name)[0] or 'image/jpeg'
    except Exception as exc:
        logger.warning("No se pudo leer la imagen: %s", exc)
        return (False, "No se pudo leer la imagen.")
    return _ia.generar_desde_imagen(institucion, data, mime, _PROMPT_ALT)
