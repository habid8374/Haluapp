"""Halu STEAM — Simulaciones interactivas (PhET, Universidad de Colorado
Boulder, código abierto CC-BY: https://phet.colorado.edu/en/about/source-code).

El catálogo (`SimulacionSTEAM`) sigue el mismo patrón multi-tenant que
`BancoPregunta` en Simulacros: `es_publica=True` con `institucion=None` son
simulaciones curadas por la plataforma, visibles para TODAS las
instituciones; una institución puede además tener sus propias simulaciones
privadas. La asignación a un curso (`AsignacionSimulacionSTEAM`) SÍ es un
dato propio de cada colegio.

El estudiante nunca ve el catálogo completo — solo lo que su(s) docente(s)
le asignaron a un curso que él puede ver (respeta el aislamiento por
énfasis vía `cursos_visibles_para_estudiante`).
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from ..forms import AsignacionSimulacionSTEAMForm
from ..models import AsignacionSimulacionSTEAM, PeriodoAcademico, SimulacionSTEAM
from ..utils import cursos_visibles_para_estudiante
from ._main import get_filtered_queryset


def _es_coordinador_o_admin(user):
    rol = getattr(user, 'rol', '') or ''
    return rol in ('coordinador', 'administrador', 'admin_institucion', 'rector') or user.is_superuser


def _puede_gestionar_asignacion(user, asignacion):
    if user.is_superuser or _es_coordinador_o_admin(user):
        return True
    return hasattr(user, 'docente') and asignacion.curso.docentes_asignados.filter(pk=user.docente.pk).exists()


def _url_embed_phet(simulacion):
    """PhET publica cada simulación HTML5 en
    phet.colorado.edu/sims/html/<slug>/latest/<slug>_all.html — un build que
    trae selector de idioma incluido (mismo patrón documentado en su botón
    oficial «Embed»). El slug es el último tramo de la URL de la página que
    guardamos (phet.colorado.edu/en/simulations/<slug>)."""
    from urllib.parse import urlparse
    slug = urlparse(simulacion.url).path.rstrip('/').rsplit('/', 1)[-1]
    if not slug:
        return None
    return f"https://phet.colorado.edu/sims/html/{slug}/latest/{slug}_all.html"


def _simulacion_visible_para(user, pk):
    """Una simulación se puede abrir si: (a) el usuario es docente/coordinador
    con acceso al catálogo (pública o privada de su institución), o (b) es un
    estudiante con una asignación vigente a un curso que puede ver (respeta
    el aislamiento por énfasis)."""
    institucion = getattr(user, 'institucion_asociada', None)
    if user.is_superuser or user.has_perm('gestion_academica.view_simulacionsteam'):
        return SimulacionSTEAM.objects.filter(
            Q(es_publica=True) | Q(institucion=institucion), pk=pk, activo=True,
        ).first()
    if hasattr(user, 'estudiante'):
        estudiante = user.estudiante
        if not estudiante.grado_actual_id:
            return None
        periodo_activo = PeriodoAcademico.objects.filter(activo=True, institucion=estudiante.institucion).first()
        if not periodo_activo:
            return None
        cursos = cursos_visibles_para_estudiante(estudiante, periodo_activo)
        asignacion = AsignacionSimulacionSTEAM.objects.filter(
            simulacion_id=pk, curso__in=cursos,
        ).select_related('simulacion').first()
        return asignacion.simulacion if asignacion else None
    return None


# ─── Docente / Coordinador ────────────────────────────────────────────────────

@login_required
@permission_required('gestion_academica.view_simulacionsteam', raise_exception=True)
def catalogo_simulaciones_steam(request):
    """Catálogo de simulaciones (públicas de la plataforma + privadas de la
    institución), con un botón para asignarla a un curso propio."""
    institucion = getattr(request.user, 'institucion_asociada', None)
    if request.user.is_superuser:
        qs = SimulacionSTEAM.objects.filter(activo=True)
    else:
        qs = SimulacionSTEAM.objects.filter(
            Q(es_publica=True) | Q(institucion=institucion), activo=True,
        )
    area = request.GET.get('area', '')
    if area:
        qs = qs.filter(area=area)

    context = {
        'simulaciones': qs.order_by('area', 'titulo'),
        'areas': SimulacionSTEAM.Area.choices,
        'area_seleccionada': area,
        'asignar_form': AsignacionSimulacionSTEAMForm(request=request),
        'titulo_pagina': _("Catálogo de Simulaciones STEAM"),
    }
    return render(request, 'gestion_academica/catalogo_simulaciones_steam.html', context)


@login_required
@permission_required('gestion_academica.add_asignacionsimulacionsteam', raise_exception=True)
def asignar_simulacion_steam(request, simulacion_pk):
    institucion = getattr(request.user, 'institucion_asociada', None)
    simulacion = get_object_or_404(
        SimulacionSTEAM.objects.filter(Q(es_publica=True) | Q(institucion=institucion), activo=True),
        pk=simulacion_pk,
    )
    if request.method == 'POST':
        form = AsignacionSimulacionSTEAMForm(request.POST, request=request)
        if form.is_valid():
            asignacion = form.save(commit=False)
            asignacion.simulacion = simulacion
            asignacion.institucion = institucion
            asignacion.asignado_por = request.user
            try:
                asignacion.save()
                messages.success(request, _("«%(titulo)s» asignada al curso.") % {'titulo': simulacion.titulo})
            except IntegrityError:
                messages.warning(request, _("Esa simulación ya estaba asignada a ese curso."))
            return redirect('gestion_academica:catalogo_simulaciones_steam')
        messages.error(request, _("Revisa el formulario — no se pudo asignar."))
    return redirect('gestion_academica:catalogo_simulaciones_steam')


@login_required
@permission_required('gestion_academica.view_asignacionsimulacionsteam', raise_exception=True)
def mis_asignaciones_simulaciones_steam(request):
    """Coordinación ve todas las asignaciones de la institución; un docente
    solo las de los cursos donde está asignado."""
    qs = get_filtered_queryset(
        AsignacionSimulacionSTEAM, request.user,
        AsignacionSimulacionSTEAM.objects.select_related('simulacion', 'curso', 'curso__materia', 'curso__grado'),
    )
    if not (request.user.is_superuser or _es_coordinador_o_admin(request.user)):
        if hasattr(request.user, 'docente'):
            qs = qs.filter(curso__docentes_asignados=request.user.docente)
        else:
            qs = qs.none()
    context = {
        'asignaciones': qs.order_by('-creado_en'),
        'titulo_pagina': _("Simulaciones Asignadas"),
    }
    return render(request, 'gestion_academica/mis_asignaciones_simulaciones_steam.html', context)


@login_required
@permission_required('gestion_academica.delete_asignacionsimulacionsteam', raise_exception=True)
def eliminar_asignacion_simulacion_steam(request, pk):
    asignacion = get_object_or_404(
        get_filtered_queryset(AsignacionSimulacionSTEAM, request.user), pk=pk,
    )
    if not _puede_gestionar_asignacion(request.user, asignacion):
        messages.error(request, _("No tienes permiso para quitar esta asignación."))
        return redirect('gestion_academica:mis_asignaciones_simulaciones_steam')
    if request.method == 'POST':
        titulo = asignacion.simulacion.titulo
        asignacion.delete()
        messages.success(request, _("Se quitó «%(titulo)s» del curso.") % {'titulo': titulo})
    return redirect('gestion_academica:mis_asignaciones_simulaciones_steam')


@login_required
def abrir_simulacion_steam(request, pk):
    """Visor propio de Halu: incrusta la simulación en un iframe para que
    nunca se salga de la app (clave en PWA/celular, donde un enlace con
    target="_blank" saca al navegador del sistema). Siempre deja un enlace
    de respaldo a la página oficial por si una simulación puntual no admite
    incrustarse."""
    simulacion = _simulacion_visible_para(request.user, pk)
    if not simulacion:
        messages.error(request, _("No tienes acceso a esa simulación."))
        return redirect('gestion_academica:inicio_academico')

    volver_url = (
        'gestion_academica:catalogo_simulaciones_steam'
        if not hasattr(request.user, 'estudiante') else 'gestion_academica:mis_simulaciones_steam'
    )
    context = {
        'simulacion': simulacion,
        'url_embed': _url_embed_phet(simulacion),
        'volver_url': volver_url,
        'titulo_pagina': simulacion.titulo,
    }
    return render(request, 'gestion_academica/visor_simulacion_steam.html', context)


# ─── Estudiante ───────────────────────────────────────────────────────────────

@login_required
def mis_simulaciones_steam(request):
    """Simulaciones asignadas a los cursos que el estudiante puede ver en el
    período activo (respeta el aislamiento por énfasis/taller)."""
    if not hasattr(request.user, 'estudiante'):
        messages.error(request, _("Esta pantalla es solo para estudiantes."))
        return redirect('gestion_academica:inicio_academico')

    estudiante = request.user.estudiante
    asignaciones = AsignacionSimulacionSTEAM.objects.none()
    periodo_activo = None
    if estudiante.grado_actual_id:
        periodo_activo = PeriodoAcademico.objects.filter(
            activo=True, institucion=estudiante.institucion,
        ).first()
        if periodo_activo:
            cursos = cursos_visibles_para_estudiante(estudiante, periodo_activo)
            asignaciones = (
                AsignacionSimulacionSTEAM.objects
                .filter(curso__in=cursos)
                .select_related('simulacion', 'curso', 'curso__materia')
                .order_by('-creado_en')
            )
    context = {
        'asignaciones': asignaciones,
        'titulo_pagina': _("Mis Simulaciones STEAM"),
    }
    return render(request, 'gestion_academica/mis_simulaciones_steam.html', context)
