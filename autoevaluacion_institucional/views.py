"""Vistas de la Autoevaluación Institucional (Guía 34)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Avg, Count, Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    AreaGestion, AutoevaluacionInstitucional, ComponenteGestion,
    ESCALA_VALORACION, ValoracionGestion,
)


# ── Estructura oficial de la Guía 34 (se siembra la primera vez) ─────────────

COMPONENTES_GUIA34 = {
    AreaGestion.DIRECTIVA: [
        "Direccionamiento estratégico y horizonte institucional",
        "Gestión estratégica",
        "Gobierno escolar",
        "Cultura institucional",
        "Clima escolar",
        "Relaciones con el entorno",
    ],
    AreaGestion.ACADEMICA: [
        "Diseño pedagógico (curricular)",
        "Prácticas pedagógicas",
        "Gestión de aula",
        "Seguimiento académico",
    ],
    AreaGestion.ADMINISTRATIVA: [
        "Apoyo a la gestión académica",
        "Administración de la planta física y de los recursos",
        "Administración de servicios complementarios",
        "Talento humano",
        "Apoyo financiero y contable",
    ],
    AreaGestion.COMUNIDAD: [
        "Accesibilidad",
        "Proyección a la comunidad",
        "Participación y convivencia",
        "Prevención de riesgos",
    ],
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _institucion(user):
    return getattr(user, 'institucion_asociada', None)


def _es_coord(user):
    rol = getattr(user, 'rol', '') or ''
    return rol in ('coordinador', 'administrador') or user.is_superuser


def _solo_coord(user):
    if not _es_coord(user):
        raise PermissionDenied


def _scope(qs, user):
    """Filtra por institución del usuario (superusuario ve todo)."""
    if user.is_superuser:
        return qs
    inst = _institucion(user)
    return qs.filter(institucion=inst) if inst else qs.none()


def _asegurar_componentes(institucion):
    """Siembra los componentes oficiales de la Guía 34 si la institución no tiene."""
    if institucion is None:
        return
    if ComponenteGestion.objects.filter(institucion=institucion).exists():
        return
    nuevos = []
    for area, nombres in COMPONENTES_GUIA34.items():
        for i, nombre in enumerate(nombres, start=1):
            nuevos.append(ComponenteGestion(
                institucion=institucion, area=area, nombre=nombre, orden=i,
            ))
    ComponenteGestion.objects.bulk_create(nuevos)


# ── Panel principal ──────────────────────────────────────────────────────────

@login_required
def panel(request):
    _solo_coord(request.user)
    inst = _institucion(request.user)
    if inst:
        _asegurar_componentes(inst)

    autoevaluaciones = _scope(AutoevaluacionInstitucional.objects.all(), request.user).annotate(
        num_valoradas=Count('valoraciones', filter=Q(valoraciones__valor__isnull=False)),
        total_items=Count('valoraciones'),
    )
    n_componentes = _scope(ComponenteGestion.objects.filter(activo=True), request.user).count()

    return render(request, 'autoevaluacion_institucional/panel.html', {
        'titulo_pagina': 'Autoevaluación Institucional',
        'autoevaluaciones': autoevaluaciones,
        'n_componentes': n_componentes,
        'anio_actual': timezone.localdate().year,
    })


# ── Componentes (editar la rúbrica) ──────────────────────────────────────────

@login_required
def gestionar_componentes(request):
    _solo_coord(request.user)
    inst = _institucion(request.user)
    if inst:
        _asegurar_componentes(inst)

    if request.method == 'POST':
        area = request.POST.get('area')
        nombre = (request.POST.get('nombre') or '').strip()
        descripcion = (request.POST.get('descripcion') or '').strip()
        if area not in AreaGestion.values:
            messages.error(request, "Selecciona un área válida.")
        elif not nombre:
            messages.error(request, "Escribe el nombre del componente.")
        elif not inst and not request.user.is_superuser:
            messages.error(request, "Tu usuario no está asociado a una institución.")
        else:
            ultimo = _scope(ComponenteGestion.objects.filter(area=area), request.user).order_by('-orden').first()
            ComponenteGestion.objects.create(
                institucion=inst, area=area, nombre=nombre, descripcion=descripcion,
                orden=(ultimo.orden + 1) if ultimo else 1,
            )
            messages.success(request, "Componente agregado.")
        return redirect('autoevaluacion_institucional:componentes')

    componentes = _scope(ComponenteGestion.objects.all(), request.user)
    por_area = []
    for area in AreaGestion:
        items = [c for c in componentes if c.area == area.value]
        por_area.append({'area': area, 'items': items})

    return render(request, 'autoevaluacion_institucional/componentes.html', {
        'titulo_pagina': 'Componentes de gestión',
        'por_area': por_area,
        'AREAS': AreaGestion,
    })


@require_POST
@login_required
def componente_editar(request, pk):
    _solo_coord(request.user)
    componente = get_object_or_404(_scope(ComponenteGestion.objects.all(), request.user), pk=pk)
    nombre = (request.POST.get('nombre') or '').strip()
    if nombre:
        componente.nombre = nombre
        componente.descripcion = (request.POST.get('descripcion') or '').strip()
        componente.activo = request.POST.get('activo') == 'on'
        componente.save(update_fields=['nombre', 'descripcion', 'activo'])
        messages.success(request, "Componente actualizado.")
    else:
        messages.error(request, "El nombre no puede quedar vacío.")
    return redirect('autoevaluacion_institucional:componentes')


@require_POST
@login_required
def componente_eliminar(request, pk):
    _solo_coord(request.user)
    componente = get_object_or_404(_scope(ComponenteGestion.objects.all(), request.user), pk=pk)
    try:
        componente.delete()
        messages.success(request, "Componente eliminado.")
    except ProtectedError:
        componente.activo = False
        componente.save(update_fields=['activo'])
        messages.info(request, "El componente ya se usó en una autoevaluación, así que se desactivó en vez de borrarse (para no perder el histórico).")
    return redirect('autoevaluacion_institucional:componentes')


# ── Crear / diligenciar / cerrar ─────────────────────────────────────────────

@require_POST
@login_required
def crear_autoevaluacion(request):
    _solo_coord(request.user)
    inst = _institucion(request.user)
    if not inst:
        # La autoevaluación pertenece a un colegio concreto; sin institución no se crea.
        messages.error(request, "Tu usuario no está asociado a una institución.")
        return redirect('autoevaluacion_institucional:panel')

    _asegurar_componentes(inst)
    titulo = (request.POST.get('titulo') or '').strip()
    try:
        anio = int(request.POST.get('anio') or timezone.localdate().year)
    except (TypeError, ValueError):
        anio = timezone.localdate().year
    if not titulo:
        messages.error(request, "Escribe un título para la autoevaluación.")
        return redirect('autoevaluacion_institucional:panel')

    componentes = list(_scope(ComponenteGestion.objects.filter(activo=True), request.user))
    if not componentes:
        messages.warning(request, "Primero configura al menos un componente de gestión.")
        return redirect('autoevaluacion_institucional:componentes')

    with transaction.atomic():
        auto = AutoevaluacionInstitucional.objects.create(
            institucion=inst, anio=anio, titulo=titulo, creada_por=request.user,
        )
        ValoracionGestion.objects.bulk_create([
            ValoracionGestion(autoevaluacion=auto, componente=c) for c in componentes
        ])
    messages.success(request, "Autoevaluación creada. Ya puedes diligenciarla.")
    return redirect('autoevaluacion_institucional:diligenciar', pk=auto.pk)


@login_required
def diligenciar(request, pk):
    _solo_coord(request.user)
    auto = get_object_or_404(_scope(AutoevaluacionInstitucional.objects.all(), request.user), pk=pk)
    valoraciones = list(
        auto.valoraciones.select_related('componente').filter(componente__activo=True)
    )

    if request.method == 'POST':
        if auto.estado == AutoevaluacionInstitucional.Estado.CERRADA:
            messages.info(request, "Esta autoevaluación está cerrada y ya no se puede editar.")
            return redirect('autoevaluacion_institucional:resultados', pk=auto.pk)
        with transaction.atomic():
            for v in valoraciones:
                raw = request.POST.get(f'valor_{v.id}')
                try:
                    val = int(raw)
                except (TypeError, ValueError):
                    val = None
                v.valor = val if (val and 1 <= val <= 4) else None
                v.observaciones = (request.POST.get(f'obs_{v.id}') or '').strip()[:2000]
                v.accion_mejora = (request.POST.get(f'mejora_{v.id}') or '').strip()[:2000]
                v.save(update_fields=['valor', 'observaciones', 'accion_mejora'])
            if auto.estado == AutoevaluacionInstitucional.Estado.BORRADOR:
                auto.estado = AutoevaluacionInstitucional.Estado.EN_PROCESO
                auto.save(update_fields=['estado'])
        messages.success(request, "Avances guardados.")
        return redirect('autoevaluacion_institucional:diligenciar', pk=auto.pk)

    # Agrupar por área para el formulario.
    por_area = []
    for area in AreaGestion:
        items = [v for v in valoraciones if v.componente.area == area.value]
        if items:
            por_area.append({'area': area, 'valoraciones': items})

    return render(request, 'autoevaluacion_institucional/diligenciar.html', {
        'titulo_pagina': auto.titulo,
        'auto': auto,
        'por_area': por_area,
        'rango': range(1, 5),
        'escala': ESCALA_VALORACION,
        'solo_lectura': auto.estado == AutoevaluacionInstitucional.Estado.CERRADA,
    })


@require_POST
@login_required
def cerrar_autoevaluacion(request, pk):
    _solo_coord(request.user)
    auto = get_object_or_404(_scope(AutoevaluacionInstitucional.objects.all(), request.user), pk=pk)
    auto.estado = AutoevaluacionInstitucional.Estado.CERRADA
    auto.cerrada_en = timezone.now()
    auto.save(update_fields=['estado', 'cerrada_en'])
    messages.success(request, "Autoevaluación cerrada. Ya puedes consultar los resultados.")
    return redirect('autoevaluacion_institucional:resultados', pk=auto.pk)


@require_POST
@login_required
def reabrir_autoevaluacion(request, pk):
    _solo_coord(request.user)
    auto = get_object_or_404(_scope(AutoevaluacionInstitucional.objects.all(), request.user), pk=pk)
    auto.estado = AutoevaluacionInstitucional.Estado.EN_PROCESO
    auto.cerrada_en = None
    auto.save(update_fields=['estado', 'cerrada_en'])
    messages.success(request, "Autoevaluación reabierta para edición.")
    return redirect('autoevaluacion_institucional:diligenciar', pk=auto.pk)


# ── Resultados ───────────────────────────────────────────────────────────────

@login_required
def resultados(request, pk):
    _solo_coord(request.user)
    auto = get_object_or_404(_scope(AutoevaluacionInstitucional.objects.all(), request.user), pk=pk)

    base = auto.valoraciones.filter(valor__isnull=False)
    por_area = []
    for area in AreaGestion:
        stats = base.filter(componente__area=area.value).aggregate(
            promedio=Avg('valor'), n=Count('id'),
        )
        por_area.append({
            'area': area,
            'promedio': stats['promedio'],
            'n': stats['n'] or 0,
        })
    promedio_global = base.aggregate(p=Avg('valor'))['p']

    # Plan de mejoramiento: componentes valorados en 1 o 2 (los más urgentes).
    plan = list(
        auto.valoraciones.select_related('componente')
        .filter(valor__isnull=False, valor__lte=2)
        .order_by('valor', 'componente__area', 'componente__orden')
    )

    return render(request, 'autoevaluacion_institucional/resultados.html', {
        'titulo_pagina': f'Resultados — {auto.titulo}',
        'auto': auto,
        'por_area': por_area,
        'promedio_global': promedio_global,
        'plan': plan,
        'escala': ESCALA_VALORACION,
    })


@require_POST
@login_required
def eliminar_autoevaluacion(request, pk):
    _solo_coord(request.user)
    auto = get_object_or_404(_scope(AutoevaluacionInstitucional.objects.all(), request.user), pk=pk)
    with transaction.atomic():
        # Las valoraciones se borran en cascada; los componentes se conservan.
        auto.valoraciones.all().delete()
        auto.delete()
    messages.success(request, "Autoevaluación eliminada.")
    return redirect('autoevaluacion_institucional:panel')
