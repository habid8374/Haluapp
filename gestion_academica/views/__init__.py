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
from .politica_datos import *
from .eventos import *
from .idioma import *

# ── Vistas de Logros (Preescolar) ────────────────────────────────────────────
# Estas vistas existen tanto en _main.py como en una versión legacy en ia.py.
# La de _main.py es la completa y la que corresponde al template actual
# (agrupa los logros por grado → materia). Se reimporta de forma explícita al
# final para garantizar que NO quede activa la versión antigua de ia.py, que no
# construía 'logros_por_grado' y hacía que la lista siempre se viera vacía.
from ._main import (
    LogroListView,
    LogroCreateView,
    LogroUpdateView,
    LogroDeleteView,
)

# ── Despachador «Libro de Notas» ─────────────────────────────────────────────
# Existe tanto en _main.py (filtrado por institución vía get_filtered_queryset)
# como una copia legacy en ia.py que NO filtra por institución. Se reimporta la
# versión de _main.py al final para blindar el aislamiento multi-institución
# (evita que un staff pueda despachar sobre un curso de otro colegio por pk).
from ._main import redirigir_a_libro_de_notas
