"""
Módulos por institución ("plan" del colegio).

Utilidades para saber qué módulos tiene contratado una institución y para
bloquear el acceso a los que no compró. La fuente de verdad es el M2M
`InstitucionEducativa.modulos_contratados` sobre el catálogo `ModuloPlataforma`.

Reglas:
- El superusuario (propietario de la plataforma) SIEMPRE tiene acceso a todo.
- Una institución solo "tiene" un módulo si está en sus `modulos_contratados`
  y el módulo está `activo`.
- El núcleo académico (gestión académica: notas, deberes, horarios) NO se
  bloquea nunca; solo se controlan los módulos que existan como fila de
  catálogo con su `prefijo_url`.
"""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect
from django.utils.translation import gettext as _


# Referencia de los módulos sembrados de fábrica (migraciones 0031 y 0032). El
# propietario puede agregar/editar/quitar más desde el admin (Módulos de la
# plataforma) — esta lista es solo documentación; la fuente de verdad es la BD.
# El núcleo académico (/academico/), Finanzas (/finanzas/, con su propio
# interruptor) y la infraestructura (auth, mensajería, SIMAT, panel del dueño)
# NO se bloquean con este sistema.
MODULOS_SEED = [
    ('admisiones', 'Admisiones', '/admisiones/'),
    ('simulacros', 'Simulacros (ICFES/Saber)', '/simulacros/'),
    ('piar', 'PIAR (inclusión)', '/piar/'),
    ('recursos_educativos', 'Recursos educativos', '/academico/recursos/'),
    ('evaluacion_docente', 'Evaluación docente', '/evaluacion-docente/'),
    ('autoevaluacion', 'Autoevaluación institucional', '/autoevaluacion/'),
    ('recursos_interactivos', 'Recursos interactivos (juegos)', '/crucigramas/ …'),
    ('cuestionarios', 'Cuestionarios / Evaluaciones', '/cuestionarios/'),
]


def institucion_tiene_modulo(institucion, codigo):
    """True si la institución tiene contratado y activo el módulo `codigo`."""
    if institucion is None:
        return False
    try:
        return institucion.modulos_contratados.filter(codigo=codigo, activo=True).exists()
    except Exception:
        return False


def modulos_activos_de(institucion):
    """Conjunto de códigos de módulos contratados y activos de la institución."""
    if institucion is None:
        return set()
    try:
        return set(
            institucion.modulos_contratados.filter(activo=True).values_list('codigo', flat=True)
        )
    except Exception:
        return set()


# ── Cache de los prefijos de URL bloqueables (para el middleware) ────────────
# Solo depende del catálogo ModuloPlataforma (cambia poco), NO de qué contrató
# cada institución (eso se consulta en vivo). Así, cuando el propietario marca o
# desmarca un módulo para un colegio, aplica de inmediato.
CACHE_KEY_PREFIJOS = 'modulos_prefijos_bloqueables_v1'


def prefijos_bloqueables():
    """Lista de (prefijo_url, codigo) de los módulos activos que se bloquean por
    URL. Un módulo puede cubrir VARIAS rutas: se separan por espacios o comas en
    el campo `prefijo_url` (ej. los juegos interactivos). Cacheada 5 min; se
    limpia sola al editar el catálogo."""
    from django.core.cache import cache
    data = cache.get(CACHE_KEY_PREFIJOS)
    if data is None:
        pares = []
        try:
            from finanzas.models import ModuloPlataforma
            for prefijos, codigo in (
                ModuloPlataforma.objects.filter(activo=True)
                .exclude(prefijo_url='')
                .values_list('prefijo_url', 'codigo')
            ):
                for p in (prefijos or '').replace(',', ' ').split():
                    pares.append((p, codigo))
        except Exception:
            pares = []
        data = pares
        cache.set(CACHE_KEY_PREFIJOS, data, 300)
    return data


def limpiar_cache_prefijos():
    """Invalida la cache de prefijos (se llama al guardar/borrar un módulo)."""
    try:
        from django.core.cache import cache
        cache.delete(CACHE_KEY_PREFIJOS)
    except Exception:
        pass


def requiere_modulo(codigo):
    """Decorador de vista: exige que la institución del usuario tenga contratado
    el módulo `codigo`. El superusuario pasa siempre. Si no lo tiene, muestra un
    mensaje amable y redirige al inicio académico (no un error técnico).

    El bloqueo por URL del módulo completo lo hace el middleware; este decorador
    sirve para proteger vistas sueltas o reforzar el control."""
    def decorador(vista):
        @wraps(vista)
        def _envuelta(request, *args, **kwargs):
            user = getattr(request, 'user', None)
            if user is not None and user.is_authenticated and not user.is_superuser:
                institucion = getattr(user, 'institucion_asociada', None)
                if not institucion_tiene_modulo(institucion, codigo):
                    messages.warning(
                        request,
                        _("Tu institución no tiene contratado este módulo. "
                          "Si te interesa activarlo, contacta al administrador de la plataforma."),
                    )
                    return redirect('gestion_academica:inicio_academico')
            return vista(request, *args, **kwargs)
        return _envuelta
    return decorador
