"""Vistas del módulo de Evaluación de Desempeño Docente por las familias."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    CampanaEvaluacion, CriterioEvaluacion, RespuestaEvaluacion, ValoracionCriterio,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _institucion(user):
    return getattr(user, 'institucion_asociada', None)


def _es_coord(user):
    rol = getattr(user, 'rol', '') or ''
    return rol in ('coordinador', 'administrador') or user.is_superuser


def _scope(qs, user):
    """Filtra por institución del usuario (superusuario ve todo)."""
    if user.is_superuser:
        return qs
    inst = _institucion(user)
    return qs.filter(institucion=inst) if inst else qs.none()


def _solo_coord(user):
    if not _es_coord(user):
        raise PermissionDenied


# ── Configuración (coordinador / administrador) ──────────────────────────────

@login_required
def panel(request):
    _solo_coord(request.user)
    campanas = _scope(CampanaEvaluacion.objects.all(), request.user).select_related(
        'periodo_academico'
    ).annotate(num_respuestas=Count('respuestas'))
    n_criterios = _scope(CriterioEvaluacion.objects.filter(activo=True), request.user).count()

    from gestion_academica.models import PeriodoAcademico
    periodos = PeriodoAcademico.objects.all()
    if not request.user.is_superuser and _institucion(request.user):
        periodos = periodos.filter(institucion=_institucion(request.user))

    return render(request, 'evaluacion_docente/panel.html', {
        'titulo_pagina': 'Evaluación de Docentes',
        'campanas': campanas,
        'n_criterios': n_criterios,
        'periodos': periodos.order_by('-año_escolar', 'nombre'),
        'ESTADOS': CampanaEvaluacion.Estado,
    })


@login_required
def gestionar_criterios(request):
    _solo_coord(request.user)
    inst = _institucion(request.user)

    if request.method == 'POST':
        texto = (request.POST.get('texto') or '').strip()
        descripcion = (request.POST.get('descripcion') or '').strip()
        if not texto:
            messages.error(request, "Escribe el texto del criterio.")
        elif not inst and not request.user.is_superuser:
            messages.error(request, "Tu usuario no está asociado a una institución.")
        else:
            ultimo = _scope(CriterioEvaluacion.objects.all(), request.user).order_by('-orden').first()
            CriterioEvaluacion.objects.create(
                institucion=inst,
                texto=texto,
                descripcion=descripcion,
                orden=(ultimo.orden + 1) if ultimo else 1,
            )
            messages.success(request, "Criterio agregado.")
        return redirect('evaluacion_docente:criterios')

    criterios = _scope(CriterioEvaluacion.objects.all(), request.user)
    return render(request, 'evaluacion_docente/criterios.html', {
        'titulo_pagina': 'Criterios de evaluación',
        'criterios': criterios,
    })


@require_POST
@login_required
def criterio_editar(request, pk):
    _solo_coord(request.user)
    criterio = get_object_or_404(_scope(CriterioEvaluacion.objects.all(), request.user), pk=pk)
    texto = (request.POST.get('texto') or '').strip()
    if texto:
        criterio.texto = texto
        criterio.descripcion = (request.POST.get('descripcion') or '').strip()
        criterio.activo = request.POST.get('activo') == 'on'
        criterio.save(update_fields=['texto', 'descripcion', 'activo'])
        messages.success(request, "Criterio actualizado.")
    else:
        messages.error(request, "El texto no puede quedar vacío.")
    return redirect('evaluacion_docente:criterios')


@require_POST
@login_required
def criterio_eliminar(request, pk):
    _solo_coord(request.user)
    criterio = get_object_or_404(_scope(CriterioEvaluacion.objects.all(), request.user), pk=pk)
    try:
        criterio.delete()
        messages.success(request, "Criterio eliminado.")
    except ProtectedError:
        # Ya tiene respuestas: no se borra (se perdería el histórico); se desactiva.
        criterio.activo = False
        criterio.save(update_fields=['activo'])
        messages.info(request, "El criterio ya tiene respuestas registradas, así que se desactivó en vez de borrarse (para no perder el histórico).")
    return redirect('evaluacion_docente:criterios')


@require_POST
@login_required
def crear_campana(request):
    _solo_coord(request.user)
    from gestion_academica.models import PeriodoAcademico

    inst = _institucion(request.user)
    titulo = (request.POST.get('titulo') or '').strip()
    periodo_id = request.POST.get('periodo_academico')

    if not titulo or not periodo_id:
        messages.error(request, "Indica el título y el periodo.")
        return redirect('evaluacion_docente:panel')

    periodo_qs = PeriodoAcademico.objects.all()
    if not request.user.is_superuser:
        periodo_qs = periodo_qs.filter(institucion=inst)
    periodo = get_object_or_404(periodo_qs, pk=periodo_id)

    if not _scope(CriterioEvaluacion.objects.filter(activo=True), request.user).exists():
        messages.warning(request, "Primero crea al menos un criterio de evaluación.")
        return redirect('evaluacion_docente:criterios')

    CampanaEvaluacion.objects.create(
        institucion=inst if not request.user.is_superuser else periodo.institucion,
        periodo_academico=periodo,
        titulo=titulo,
        fecha_apertura=request.POST.get('fecha_apertura') or None,
        fecha_cierre=request.POST.get('fecha_cierre') or None,
        creada_por=request.user,
    )
    messages.success(request, "Campaña creada en borrador. Ábrela cuando quieras que las familias empiecen a evaluar.")
    return redirect('evaluacion_docente:panel')


@require_POST
@login_required
def campana_estado(request, pk):
    _solo_coord(request.user)
    campana = get_object_or_404(_scope(CampanaEvaluacion.objects.all(), request.user), pk=pk)
    accion = request.POST.get('accion')

    if accion == 'abrir':
        if not _scope(CriterioEvaluacion.objects.filter(activo=True), request.user).exists():
            messages.error(request, "No puedes abrir la campaña sin criterios activos.")
            return redirect('evaluacion_docente:panel')
        campana.estado = CampanaEvaluacion.Estado.ABIERTA
        if not campana.fecha_apertura:
            campana.fecha_apertura = timezone.localdate()
        campana.save(update_fields=['estado', 'fecha_apertura'])
        messages.success(request, "Campaña abierta. Las familias ya pueden evaluar.")
    elif accion == 'cerrar':
        campana.estado = CampanaEvaluacion.Estado.CERRADA
        if not campana.fecha_cierre:
            campana.fecha_cierre = timezone.localdate()
        campana.save(update_fields=['estado', 'fecha_cierre'])
        messages.success(request, "Campaña cerrada. Ya puedes revisar los resultados.")
    return redirect('evaluacion_docente:panel')


@login_required
def campana_resultados(request, pk):
    _solo_coord(request.user)
    campana = get_object_or_404(
        _scope(CampanaEvaluacion.objects.all(), request.user).select_related('periodo_academico'),
        pk=pk,
    )
    docentes = (
        RespuestaEvaluacion.objects.filter(campana=campana)
        .values('docente', 'docente__usuario__first_name', 'docente__usuario__last_name', 'docente__usuario__username')
        .annotate(n=Count('id', distinct=True), promedio=Avg('valoraciones__valor'))
        .order_by('-promedio')
    )
    return render(request, 'evaluacion_docente/resultados.html', {
        'titulo_pagina': f'Resultados: {campana.titulo}',
        'campana': campana,
        'docentes': docentes,
    })


@login_required
def resultados_docente(request, campana_pk, docente_pk):
    _solo_coord(request.user)
    campana = get_object_or_404(_scope(CampanaEvaluacion.objects.all(), request.user), pk=campana_pk)
    respuestas = RespuestaEvaluacion.objects.filter(campana=campana, docente_id=docente_pk)

    por_criterio = (
        ValoracionCriterio.objects.filter(respuesta__in=respuestas)
        .values('criterio__texto', 'criterio__orden')
        .annotate(promedio=Avg('valor'), n=Count('id'))
        .order_by('criterio__orden')
    )
    comentarios = []
    for r in respuestas.select_related('familiar__usuario').exclude(comentario=''):
        comentarios.append({
            'autor': 'Anónimo' if r.anonimo else (r.familiar.usuario.get_full_name() or 'Familia'),
            'texto': r.comentario,
            'fecha': r.fecha,
        })

    from gestion_academica.models import Docente
    docente = get_object_or_404(Docente.objects.select_related('usuario'), pk=docente_pk)
    global_prom = respuestas.aggregate(p=Avg('valoraciones__valor'))['p']

    return render(request, 'evaluacion_docente/resultados_docente.html', {
        'titulo_pagina': f'Resultado — {docente.usuario.get_full_name() or docente.usuario.username}',
        'campana': campana,
        'docente': docente,
        'promedio_global': global_prom,
        'total_respuestas': respuestas.count(),
        'por_criterio': por_criterio,
        'comentarios': comentarios,
    })


# ── Portal de las familias (acudientes) ──────────────────────────────────────

def _familiar(user):
    return getattr(user, 'familiar', None)


@login_required
def mis_evaluaciones(request):
    from gestion_academica.models import Curso

    familiar = _familiar(request.user)
    if familiar is None:
        raise PermissionDenied

    campanas = CampanaEvaluacion.objects.filter(
        institucion=familiar.institucion, estado=CampanaEvaluacion.Estado.ABIERTA
    ).select_related('periodo_academico')

    respondidas = set(
        RespuestaEvaluacion.objects.filter(familiar=familiar)
        .values_list('campana_id', 'docente_id', 'curso_id', 'estudiante_id')
    )

    bloques = []
    estudiantes = list(familiar.estudiantes_asociados.filter(activo=True).select_related('usuario', 'grado_actual'))
    for campana in campanas:
        items = []
        for est in estudiantes:
            if not est.grado_actual_id:
                continue
            cursos = Curso.objects.filter(
                grado=est.grado_actual, periodo_academico=campana.periodo_academico,
                institucion=campana.institucion,
            ).select_related('materia').prefetch_related('docentes_asignados__usuario')
            for curso in cursos:
                for docente in curso.docentes_asignados.all():
                    ya = (campana.id, docente.pk, curso.id, est.pk) in respondidas
                    items.append({
                        'estudiante': est, 'curso': curso, 'docente': docente, 'respondida': ya,
                    })
        if items:
            pendientes = sum(1 for i in items if not i['respondida'])
            bloques.append({'campana': campana, 'items': items, 'pendientes': pendientes})

    return render(request, 'evaluacion_docente/mis_evaluaciones.html', {
        'titulo_pagina': 'Evaluación de Docentes',
        'bloques': bloques,
    })


@login_required
def evaluar(request, campana_pk, docente_pk, curso_pk, estudiante_pk):
    from gestion_academica.models import Curso, Docente, Estudiante

    familiar = _familiar(request.user)
    if familiar is None:
        raise PermissionDenied

    campana = get_object_or_404(
        CampanaEvaluacion, pk=campana_pk, institucion=familiar.institucion,
        estado=CampanaEvaluacion.Estado.ABIERTA,
    )
    # El acudiente solo puede evaluar por su propio hijo, y a un docente que
    # realmente le dicta ese curso a ese estudiante.
    estudiante = get_object_or_404(
        familiar.estudiantes_asociados.filter(activo=True), pk=estudiante_pk
    )
    curso = get_object_or_404(
        Curso, pk=curso_pk, institucion=familiar.institucion,
        grado=estudiante.grado_actual, periodo_academico=campana.periodo_academico,
    )
    docente = get_object_or_404(curso.docentes_asignados, pk=docente_pk)

    ya = RespuestaEvaluacion.objects.filter(
        campana=campana, docente=docente, curso=curso, estudiante=estudiante, familiar=familiar,
    ).exists()

    criterios = list(
        CriterioEvaluacion.objects.filter(institucion=campana.institucion, activo=True).order_by('orden', 'id')
    )

    if request.method == 'POST':
        if ya:
            messages.info(request, "Ya habías evaluado a este docente.")
            return redirect('evaluacion_docente:mis_evaluaciones')
        valores = {}
        valido = True
        for c in criterios:
            raw = request.POST.get(f'criterio_{c.id}')
            try:
                v = int(raw)
            except (TypeError, ValueError):
                v = 0
            if v < 1 or v > 5:
                valido = False
                break
            valores[c.id] = v
        if not valido or len(valores) != len(criterios):
            messages.error(request, "Responde todos los criterios (calificación de 1 a 5).")
        else:
            try:
                with transaction.atomic():
                    resp = RespuestaEvaluacion.objects.create(
                        campana=campana, institucion=campana.institucion,
                        docente=docente, curso=curso, estudiante=estudiante, familiar=familiar,
                        anonimo=(request.POST.get('anonimo') == 'on'),
                        comentario=(request.POST.get('comentario') or '').strip(),
                    )
                    ValoracionCriterio.objects.bulk_create([
                        ValoracionCriterio(respuesta=resp, criterio_id=cid, valor=val)
                        for cid, val in valores.items()
                    ])
                messages.success(request, "¡Gracias! Tu evaluación fue registrada.")
                return redirect('evaluacion_docente:mis_evaluaciones')
            except IntegrityError:
                messages.info(request, "Esta evaluación ya había sido registrada.")
                return redirect('evaluacion_docente:mis_evaluaciones')

    return render(request, 'evaluacion_docente/evaluar.html', {
        'titulo_pagina': 'Evaluar docente',
        'campana': campana, 'docente': docente, 'curso': curso, 'estudiante': estudiante,
        'criterios': criterios, 'ya_respondida': ya,
        'rango': range(1, 6),
    })


# ── Vista del docente (su propio resultado) ──────────────────────────────────

@login_required
def mi_desempeno(request):
    docente = getattr(request.user, 'docente', None)
    if docente is None:
        raise PermissionDenied

    campanas = (
        RespuestaEvaluacion.objects.filter(docente=docente, campana__estado=CampanaEvaluacion.Estado.CERRADA)
        .values('campana', 'campana__titulo')
        .annotate(promedio=Avg('valoraciones__valor'), n=Count('id', distinct=True))
        .order_by('-campana__creada_en')
    )
    return render(request, 'evaluacion_docente/mi_desempeno.html', {
        'titulo_pagina': 'Mi Evaluación Docente',
        'campanas': campanas,
    })
