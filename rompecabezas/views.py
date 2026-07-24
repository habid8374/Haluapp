"""Vistas del módulo de Rompecabezas (actividad calificable por curso)."""
import json
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from .models import IntentoRompecabezas, Rompecabezas

MAX_IMAGEN = 2 * 1024 * 1024  # 2 MB

# Presets de dificultad ofrecidos al docente — (etiqueta, filas, columnas).
# Usa gettext_lazy (no gettext): esta lista se evalúa una sola vez al cargar
# el módulo, así que con gettext normal quedaría congelada en el idioma
# activo en ese momento en vez de traducirse por cada request.
DIFICULTADES = [
    ('facil', _lazy('Fácil (3 x 3 — 9 piezas)'), 3, 3),
    ('medio', _lazy('Medio (4 x 4 — 16 piezas)'), 4, 4),
    ('dificil', _lazy('Difícil (5 x 5 — 25 piezas)'), 5, 5),
]
DIFICULTADES_MAP = {clave: (filas, columnas) for clave, _, filas, columnas in DIFICULTADES}


def _imagen_valida(f):
    return f.size <= MAX_IMAGEN and (getattr(f, 'content_type', '') or '').startswith('image/')


def _parse_dt(valor):
    """Convierte 'YYYY-MM-DDTHH:MM' del formulario a datetime consciente de zona."""
    if not valor:
        return None
    dt = parse_datetime(valor)
    if dt and settings.USE_TZ and timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


# ── Helpers ──────────────────────────────────────────────────────────────────

def _institucion(user):
    return getattr(user, 'institucion_asociada', None)


def _es_docente_o_coord(user):
    rol = getattr(user, 'rol', '') or ''
    return rol in ('docente', 'coordinador', 'administrador') or user.is_superuser


def _es_estudiante(user):
    return (getattr(user, 'rol', '') or '') == 'estudiante'


def _solo_docente_coord(user):
    if not _es_docente_o_coord(user):
        raise PermissionDenied


def _scope(qs, user):
    if user.is_superuser:
        return qs
    inst = _institucion(user)
    return qs.filter(institucion=inst) if inst else qs.none()


def _cursos_visibles(user):
    from gestion_academica.models import Curso
    qs = Curso.objects.select_related('materia', 'grado', 'periodo_academico')
    if not user.is_superuser:
        inst = _institucion(user)
        qs = qs.filter(institucion=inst) if inst else qs.none()
    if (getattr(user, 'rol', '') or '') == 'docente':
        docente = getattr(user, 'docente', None)
        qs = qs.filter(docentes_asignados=docente) if docente else qs.none()
    return qs.order_by('periodo_academico', 'grado', 'materia')


# ── Docente / Coordinador ────────────────────────────────────────────────────

@login_required
def lista(request):
    _solo_docente_coord(request.user)
    rompecabezas_qs = _scope(Rompecabezas.objects.all(), request.user).select_related(
        'curso__materia', 'curso__grado'
    ).prefetch_related('intentos')
    if (getattr(request.user, 'rol', '') or '') == 'docente' and not request.user.is_superuser:
        docente = getattr(request.user, 'docente', None)
        rompecabezas_qs = rompecabezas_qs.filter(curso__docentes_asignados=docente) if docente else rompecabezas_qs.none()
    return render(request, 'rompecabezas/lista.html', {
        'titulo_pagina': _('Rompecabezas'),
        'items': rompecabezas_qs,
    })


@login_required
def crear(request):
    _solo_docente_coord(request.user)
    from gestion_academica.models import TipoActividad
    inst = _institucion(request.user)
    cursos = _cursos_visibles(request.user)
    tipos = TipoActividad.objects.filter(institucion=inst) if inst else TipoActividad.objects.none()
    if request.user.is_superuser and not inst:
        tipos = TipoActividad.objects.all()

    if request.method == 'POST':
        titulo = (request.POST.get('titulo') or '').strip()
        curso_id = request.POST.get('curso')
        tipo_id = request.POST.get('tipo_actividad')
        instrucciones = (request.POST.get('instrucciones') or '').strip()
        dificultad = request.POST.get('dificultad') or 'facil'
        imagen = request.FILES.get('imagen')
        try:
            nota_maxima = Decimal(request.POST.get('nota_maxima') or '5')
        except Exception:
            nota_maxima = Decimal('5')

        curso = get_object_or_404(cursos, pk=curso_id) if curso_id else None
        tipo = get_object_or_404(tipos, pk=tipo_id) if tipo_id else None
        fecha_inicio = _parse_dt(request.POST.get('fecha_inicio'))
        fecha_fin = _parse_dt(request.POST.get('fecha_fin'))
        filas, columnas = DIFICULTADES_MAP.get(dificultad, (3, 3))

        if not titulo or not curso or not tipo:
            messages.error(request, _("Completa el título, el curso y la categoría."))
        elif not imagen:
            messages.error(request, _("Sube una imagen para armar el rompecabezas."))
        elif not _imagen_valida(imagen):
            messages.error(request, _("La imagen debe pesar máximo 2 MB y ser un archivo de imagen."))
        else:
            rc = Rompecabezas.objects.create(
                institucion=curso.institucion, curso=curso, titulo=titulo,
                instrucciones=instrucciones, imagen=imagen,
                filas=filas, columnas=columnas,
                tipo_actividad=tipo, nota_maxima=nota_maxima, creado_por=request.user,
                fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
            )
            messages.success(request, _("Rompecabezas creado. Revísalo y publícalo para los estudiantes."))
            return redirect('rompecabezas:detalle', pk=rc.pk)

    return render(request, 'rompecabezas/form.html', {
        'titulo_pagina': _('Nuevo rompecabezas'),
        'cursos': cursos, 'tipos': tipos, 'dificultades': DIFICULTADES,
    })


@login_required
def detalle(request, pk):
    _solo_docente_coord(request.user)
    rc = get_object_or_404(
        _scope(Rompecabezas.objects.all(), request.user).select_related('curso__materia', 'curso__grado'),
        pk=pk,
    )
    from gestion_academica.models import TipoActividad
    tipos = TipoActividad.objects.filter(institucion=rc.institucion)
    return render(request, 'rompecabezas/detalle.html', {
        'titulo_pagina': rc.titulo,
        'rc': rc,
        'tipos': tipos,
    })


@require_POST
@login_required
def publicar(request, pk):
    _solo_docente_coord(request.user)
    rc = get_object_or_404(_scope(Rompecabezas.objects.all(), request.user), pk=pk)

    from gestion_academica.models import ActividadCalificable
    with transaction.atomic():
        if not rc.actividad_calificable:
            act = ActividadCalificable.objects.create(
                curso=rc.curso, tipo_actividad=rc.tipo_actividad,
                titulo=rc.titulo, descripcion=rc.instrucciones or None,
                institucion=rc.institucion, fecha_publicacion=timezone.localdate(),
            )
            rc.actividad_calificable = act
        rc.estado = Rompecabezas.Estado.PUBLICADO
        rc.save(update_fields=['actividad_calificable', 'estado'])
    messages.success(request, _("¡Rompecabezas publicado! Ya aparece a los estudiantes del curso."))
    return redirect('rompecabezas:detalle', pk=rc.pk)


@require_POST
@login_required
def cerrar(request, pk):
    _solo_docente_coord(request.user)
    rc = get_object_or_404(_scope(Rompecabezas.objects.all(), request.user), pk=pk)
    rc.estado = Rompecabezas.Estado.CERRADO
    rc.fecha_cierre = timezone.now()
    rc.save(update_fields=['estado', 'fecha_cierre'])
    messages.success(request, _("Rompecabezas cerrado."))
    return redirect('rompecabezas:detalle', pk=rc.pk)


@require_POST
@login_required
def editar_datos(request, pk):
    _solo_docente_coord(request.user)
    from gestion_academica.models import TipoActividad
    rc = get_object_or_404(_scope(Rompecabezas.objects.all(), request.user), pk=pk)
    titulo = (request.POST.get('titulo') or '').strip()
    if not titulo:
        messages.error(request, _("El título no puede quedar vacío."))
        return redirect('rompecabezas:detalle', pk=rc.pk)
    rc.titulo = titulo
    rc.instrucciones = (request.POST.get('instrucciones') or '').strip()
    try:
        rc.nota_maxima = Decimal(request.POST.get('nota_maxima') or rc.nota_maxima)
    except Exception:
        pass
    tipo_id = request.POST.get('tipo_actividad')
    if tipo_id:
        rc.tipo_actividad = get_object_or_404(TipoActividad, pk=tipo_id, institucion=rc.institucion)
    rc.save(update_fields=['titulo', 'instrucciones', 'nota_maxima', 'tipo_actividad'])
    if rc.actividad_calificable_id:
        act = rc.actividad_calificable
        act.titulo = rc.titulo
        act.tipo_actividad = rc.tipo_actividad
        act.descripcion = rc.instrucciones or None
        act.save(update_fields=['titulo', 'tipo_actividad', 'descripcion'])
    messages.success(request, _("Datos actualizados."))
    return redirect('rompecabezas:detalle', pk=rc.pk)


@require_POST
@login_required
def editar_fechas(request, pk):
    _solo_docente_coord(request.user)
    rc = get_object_or_404(_scope(Rompecabezas.objects.all(), request.user), pk=pk)
    rc.fecha_inicio = _parse_dt(request.POST.get('fecha_inicio'))
    rc.fecha_fin = _parse_dt(request.POST.get('fecha_fin'))
    rc.save(update_fields=['fecha_inicio', 'fecha_fin'])
    messages.success(request, _("Fechas actualizadas."))
    return redirect('rompecabezas:detalle', pk=rc.pk)


@require_POST
@login_required
def eliminar(request, pk):
    _solo_docente_coord(request.user)
    rc = get_object_or_404(_scope(Rompecabezas.objects.all(), request.user), pk=pk)
    rc.delete()
    messages.success(request, _("Rompecabezas eliminado."))
    return redirect('rompecabezas:lista')


@login_required
def resultados(request, pk):
    _solo_docente_coord(request.user)
    rc = get_object_or_404(
        _scope(Rompecabezas.objects.all(), request.user).select_related('curso__grado'), pk=pk,
    )
    intentos = rc.intentos.select_related('estudiante__usuario').order_by(
        '-puntaje', 'estudiante__usuario__first_name')
    return render(request, 'rompecabezas/resultados.html', {
        'titulo_pagina': _('Resultados: %(rc_titulo)s') % {'rc_titulo': rc.titulo},
        'rc': rc,
        'intentos': intentos,
    })


# ── Estudiante ───────────────────────────────────────────────────────────────

def _estudiante(user):
    return getattr(user, 'estudiante', None)


@login_required
def mis_rompecabezas(request):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None or not estudiante.grado_actual_id:
        return render(request, 'rompecabezas/mis_rompecabezas.html', {'titulo_pagina': _('Rompecabezas'), 'items': []})

    rompecabezas_qs = Rompecabezas.objects.filter(
        institucion=estudiante.institucion,
        curso__grado=estudiante.grado_actual,
        estado=Rompecabezas.Estado.PUBLICADO,
    ).select_related('curso__materia').order_by('-creado_en')
    hechos = {
        i.rompecabezas_id: i for i in
        IntentoRompecabezas.objects.filter(estudiante=estudiante, rompecabezas__in=rompecabezas_qs)
    }
    items = []
    for rc in rompecabezas_qs:
        disp, msg = rc.estado_disponibilidad()
        items.append({'rc': rc, 'intento': hechos.get(rc.id), 'disp': disp, 'msg': msg})
    return render(request, 'rompecabezas/mis_rompecabezas.html', {
        'titulo_pagina': _('Rompecabezas'), 'items': items,
    })


@login_required
def resolver(request, pk):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None:
        raise PermissionDenied

    rc = get_object_or_404(
        Rompecabezas, pk=pk, institucion=estudiante.institucion,
        curso__grado=estudiante.grado_actual, estado=Rompecabezas.Estado.PUBLICADO,
    )
    intento = IntentoRompecabezas.objects.filter(rompecabezas=rc, estudiante=estudiante).first()
    if intento and intento.completado:
        return redirect('rompecabezas:resultado', pk=rc.pk)

    disp, msg = rc.estado_disponibilidad()
    if disp != 'disponible':
        messages.warning(request, msg)
        return redirect('rompecabezas:mis_rompecabezas')

    if request.method == 'POST':
        n = rc.num_piezas
        try:
            orden = json.loads(request.POST.get('orden') or '[]')
        except (ValueError, TypeError):
            orden = []
        try:
            movimientos = int(request.POST.get('movimientos') or 0)
        except (ValueError, TypeError):
            movimientos = 0
        try:
            tiempo_segundos = int(request.POST.get('tiempo_segundos') or 0)
        except (ValueError, TypeError):
            tiempo_segundos = 0

        # La corrección real vive aquí, nunca se confía en lo que dice el navegador:
        # el rompecabezas solo está resuelto si el orden final es exactamente 0..N-1.
        correcto = isinstance(orden, list) and orden == list(range(n))

        if not correcto:
            messages.error(request, _("Las piezas todavía no están en el orden correcto. Sigue intentando."))
            return redirect('rompecabezas:resolver', pk=rc.pk)

        puntaje = rc.nota_maxima
        with transaction.atomic():
            IntentoRompecabezas.objects.update_or_create(
                rompecabezas=rc, estudiante=estudiante,
                defaults={
                    'institucion': rc.institucion, 'completado': True,
                    'movimientos': max(movimientos, 0),
                    'tiempo_segundos': max(tiempo_segundos, 0),
                    'puntaje': puntaje, 'fin': timezone.now(),
                },
            )
            _registrar_calificacion(rc, estudiante, puntaje)
        messages.success(request, _("¡Rompecabezas armado! Aquí está tu resultado."))
        return redirect('rompecabezas:resultado', pk=rc.pk)

    return render(request, 'rompecabezas/resolver.html', {
        'titulo_pagina': rc.titulo,
        'rc': rc,
    })


def _registrar_calificacion(rc, estudiante, puntaje):
    if not rc.actividad_calificable_id:
        return
    from gestion_academica.models import Calificacion
    Calificacion.objects.update_or_create(
        estudiante=estudiante,
        actividad_calificable=rc.actividad_calificable,
        institucion=rc.institucion,
        defaults={
            'valor_numerico': puntaje,
            'observaciones': "Rompecabezas autocorregido: armado correctamente.",
        },
    )


@login_required
def resultado(request, pk):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None:
        raise PermissionDenied
    rc = get_object_or_404(Rompecabezas, pk=pk, institucion=estudiante.institucion)
    intento = get_object_or_404(IntentoRompecabezas, rompecabezas=rc, estudiante=estudiante)
    return render(request, 'rompecabezas/resultado.html', {
        'titulo_pagina': _('Resultado: %(rc_titulo)s') % {'rc_titulo': rc.titulo},
        'rc': rc,
        'intento': intento,
    })
