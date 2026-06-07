"""
gestion_academica/views/
========================
Paquete de vistas de HALU — módulo de gestión académica.

Estructura:
  _main.py          → Monolito original (todas las vistas legacy). Se va vaciando
                       gradualmente a medida que se extraen módulos específicos.
  reportes.py       → Los 15+ reportes académicos
  ia.py             → Asistente HALU, planeador IA, análisis comportamiento, optimizador
  api_movil.py      → Todos los endpoints /api/v1/ para la app móvil

Compatibilidad hacia atrás garantizada:
  urls.py usa `from . import views` y luego `views.NombreFuncion`.
  Este __init__.py re-exporta TODO, por lo que urls.py no necesita cambios.
"""

# --- Monolito principal (base: todo lo que aún no ha sido extraído) ---
from ._main import *

# --- Módulos especializados (importados DESPUÉS para tomar precedencia) ---
# Cuando una función existe tanto en _main.py como en un módulo especializado,
# la versión del módulo especializado (más limpia, con imports propios) gana.
from .reportes import *
from .ia import *
from .api_movil import *
from .planeacion_semanal import *
from .cortes_preventivos import *
from .carga_familiares import *
