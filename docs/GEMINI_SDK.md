# Google Gemini / `google.generativeai` (aviso de deprecación)

Al arrancar Django puede aparecer un **FutureWarning** indicando que el paquete `google.generativeai` dejó de recibir actualizaciones y que se recomienda migrar a **`google.genai`**.

## Estado en HALU

- **Señales y tareas** (`gestion_academica/signals.py`, `gestion_academica/tasks.py`, vistas de cuestionarios con IA) siguen usando `google.generativeai` mientras la API del nuevo SDK se estabiliza en el proyecto.
- La generación de preguntas por IA en `cuestionarios` ahora registra con **`logging`** (nivel `DEBUG`/`INFO`) en lugar de `print`, para poder silenciar o centralizar logs en producción.

## Próximo paso técnico (cuando toque)

1. Añadir `google-genai` (o el paquete oficial vigente) a `requirements.txt`.
2. Sustituir `import google.generativeai as genai` por el cliente nuevo según la guía del repositorio de Google.
3. Mantener la lectura de API key por institución (`finanzas.institucion_credentials.google_api_key`).

Hasta entonces el warning es **cosmético en desarrollo** y no impide `manage.py check` ni el arranque del servidor.
