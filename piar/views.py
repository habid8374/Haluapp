from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db import IntegrityError

from .models import PIAR, AjustePIAR
from gestion_academica.models import Estudiante, Grado, Materia


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _get_institucion(request):
    return getattr(request.user, 'institucion_asociada', None)


def _es_coordinador_o_admin(user):
    rol = getattr(user, 'rol', '') or ''
    return rol in ('coordinador', 'admin_institucion') or user.is_superuser


def _es_docente_o_superior(user):
    rol = getattr(user, 'rol', '') or ''
    return rol in ('docente', 'coordinador', 'admin_institucion') or user.is_superuser


# ──────────────────────────────────────────────
# Lista de PIARs
# ──────────────────────────────────────────────

@login_required
def lista_piars(request):
    if not _es_docente_o_superior(request.user):
        messages.error(request, 'No tienes permiso para acceder a los PIARs.')
        return redirect('gestion_academica:inicio_academico')

    institucion = _get_institucion(request)
    piars = PIAR.objects.filter(institucion=institucion).select_related(
        'estudiante__usuario', 'grado', 'docente_lider'
    ).order_by('-año_lectivo', 'estudiante')

    # Filters from GET
    año = request.GET.get('año')
    estado = request.GET.get('estado')
    grado_id = request.GET.get('grado_id')

    if año:
        try:
            piars = piars.filter(año_lectivo=int(año))
        except ValueError:
            pass
    if estado:
        piars = piars.filter(estado=estado)
    if grado_id:
        try:
            piars = piars.filter(grado_id=int(grado_id))
        except ValueError:
            pass

    grados = Grado.objects.filter(institucion=institucion).order_by('nombre')
    años = (
        PIAR.objects.filter(institucion=institucion)
        .values_list('año_lectivo', flat=True)
        .distinct()
        .order_by('-año_lectivo')
    )

    filtros = {'año': año, 'estado': estado, 'grado_id': grado_id}

    return render(request, 'piar/lista_piars.html', {
        'titulo_pagina': 'PIARs — Planes de Ajustes Razonables',
        'piars': piars,
        'grados': grados,
        'años': años,
        'estados': PIAR.Estado.choices,
        'filtros': filtros,
    })


# ──────────────────────────────────────────────
# Crear PIAR
# ──────────────────────────────────────────────

@login_required
def crear_piar(request):
    if not _es_coordinador_o_admin(request.user):
        messages.error(request, 'Solo coordinadores pueden crear PIARs.')
        return redirect('piar:lista_piars')

    institucion = _get_institucion(request)
    estudiantes = (
        Estudiante.objects.filter(institucion=institucion, activo=True)
        .select_related('usuario', 'grado_actual')
        .order_by('usuario__last_name')
    )
    grados = Grado.objects.filter(institucion=institucion).order_by('nombre')
    materias = Materia.objects.filter(institucion=institucion).order_by('nombre_materia')
    docentes = (
        institucion.usuarios.filter(rol='docente').order_by('last_name', 'first_name')
        if institucion else []
    )

    if request.method == 'POST':
        estudiante_id = request.POST.get('estudiante')
        año_lectivo = request.POST.get('año_lectivo')
        grado_id = request.POST.get('grado')
        condicion = request.POST.get('condicion')
        condicion_descripcion = request.POST.get('condicion_descripcion', '')
        fortalezas = request.POST.get('fortalezas', '')
        barreras = request.POST.get('barreras', '')
        apoyos = request.POST.get('apoyos', '')
        compromisos_familia = request.POST.get('compromisos_familia', '')
        compromisos_docentes = request.POST.get('compromisos_docentes', '')
        compromisos_institucion = request.POST.get('compromisos_institucion', '')
        docente_lider_id = request.POST.get('docente_lider')
        fecha_elaboracion = request.POST.get('fecha_elaboracion')
        fecha_revision = request.POST.get('fecha_revision') or None
        estado = request.POST.get('estado', PIAR.Estado.BORRADOR)
        observaciones_generales = request.POST.get('observaciones_generales', '')

        try:
            estudiante = get_object_or_404(Estudiante, pk=estudiante_id, institucion=institucion)
            grado = None
            if grado_id:
                grado = Grado.objects.filter(pk=grado_id, institucion=institucion).first()
            if grado is None:
                grado = estudiante.grado_actual

            docente_lider = None
            if docente_lider_id:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                docente_lider = User.objects.filter(pk=docente_lider_id, institucion_asociada=institucion).first()

            piar = PIAR.objects.create(
                institucion=institucion,
                estudiante=estudiante,
                año_lectivo=int(año_lectivo),
                grado=grado,
                condicion=condicion,
                condicion_descripcion=condicion_descripcion,
                fortalezas=fortalezas,
                barreras=barreras,
                apoyos=apoyos,
                compromisos_familia=compromisos_familia,
                compromisos_docentes=compromisos_docentes,
                compromisos_institucion=compromisos_institucion,
                docente_lider=docente_lider,
                fecha_elaboracion=fecha_elaboracion,
                fecha_revision=fecha_revision,
                estado=estado,
                observaciones_generales=observaciones_generales,
            )
            messages.success(request, f'PIAR creado exitosamente para {estudiante}.')
            return redirect('piar:detalle_piar', pk=piar.pk)
        except IntegrityError:
            messages.error(request, 'Este estudiante ya tiene PIAR para ese año.')
        except Exception as e:
            messages.error(request, f'Error al crear el PIAR: {e}')

    return render(request, 'piar/form_piar.html', {
        'titulo_pagina': 'Nuevo PIAR',
        'estudiantes': estudiantes,
        'grados': grados,
        'materias': materias,
        'docentes': docentes,
        'condiciones': PIAR.Condicion.choices,
        'estados': PIAR.Estado.choices,
        'año_actual': timezone.now().year,
        'piar': None,
    })


# ──────────────────────────────────────────────
# Detalle PIAR
# ──────────────────────────────────────────────

@login_required
def detalle_piar(request, pk):
    if not _es_docente_o_superior(request.user):
        messages.error(request, 'No tienes permiso para ver este PIAR.')
        return redirect('gestion_academica:inicio_academico')

    institucion = _get_institucion(request)
    piar = get_object_or_404(PIAR, pk=pk, institucion=institucion)

    ajustes_qs = piar.ajustes.select_related('materia').all()
    ajustes_por_periodo = {1: [], 2: [], 3: [], 4: []}
    for ajuste in ajustes_qs:
        if ajuste.periodo in ajustes_por_periodo:
            ajustes_por_periodo[ajuste.periodo].append(ajuste)

    materias = Materia.objects.filter(institucion=institucion).order_by('nombre_materia')

    return render(request, 'piar/detalle_piar.html', {
        'titulo_pagina': f'PIAR {piar.año_lectivo} — {piar.estudiante}',
        'piar': piar,
        'ajustes_por_periodo': ajustes_por_periodo,
        'materias': materias,
    })


# ──────────────────────────────────────────────
# Editar PIAR
# ──────────────────────────────────────────────

@login_required
def editar_piar(request, pk):
    if not _es_coordinador_o_admin(request.user):
        messages.error(request, 'Solo coordinadores pueden editar PIARs.')
        return redirect('piar:lista_piars')

    institucion = _get_institucion(request)
    piar = get_object_or_404(PIAR, pk=pk, institucion=institucion)

    grados = Grado.objects.filter(institucion=institucion).order_by('nombre')
    docentes = (
        institucion.usuarios.filter(rol='docente').order_by('last_name', 'first_name')
        if institucion else []
    )

    if request.method == 'POST':
        grado_id = request.POST.get('grado')
        piar.condicion = request.POST.get('condicion', piar.condicion)
        piar.condicion_descripcion = request.POST.get('condicion_descripcion', piar.condicion_descripcion)
        piar.fortalezas = request.POST.get('fortalezas', piar.fortalezas)
        piar.barreras = request.POST.get('barreras', piar.barreras)
        piar.apoyos = request.POST.get('apoyos', piar.apoyos)
        piar.compromisos_familia = request.POST.get('compromisos_familia', piar.compromisos_familia)
        piar.compromisos_docentes = request.POST.get('compromisos_docentes', piar.compromisos_docentes)
        piar.compromisos_institucion = request.POST.get('compromisos_institucion', piar.compromisos_institucion)
        piar.fecha_elaboracion = request.POST.get('fecha_elaboracion', piar.fecha_elaboracion)
        piar.fecha_revision = request.POST.get('fecha_revision') or None
        piar.estado = request.POST.get('estado', piar.estado)
        piar.observaciones_generales = request.POST.get('observaciones_generales', piar.observaciones_generales)

        if grado_id:
            piar.grado = Grado.objects.filter(pk=grado_id, institucion=institucion).first()

        docente_lider_id = request.POST.get('docente_lider')
        if docente_lider_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            piar.docente_lider = User.objects.filter(pk=docente_lider_id, institucion_asociada=institucion).first()
        else:
            piar.docente_lider = None

        piar.save()
        messages.success(request, 'PIAR actualizado exitosamente.')
        return redirect('piar:detalle_piar', pk=piar.pk)

    return render(request, 'piar/form_piar.html', {
        'titulo_pagina': f'Editar PIAR — {piar.estudiante}',
        'piar': piar,
        'grados': grados,
        'docentes': docentes,
        'condiciones': PIAR.Condicion.choices,
        'estados': PIAR.Estado.choices,
        'año_actual': timezone.now().year,
    })


# ──────────────────────────────────────────────
# Eliminar PIAR
# ──────────────────────────────────────────────

@login_required
@require_POST
def eliminar_piar(request, pk):
    if not _es_coordinador_o_admin(request.user):
        messages.error(request, 'Solo coordinadores pueden eliminar PIARs.')
        return redirect('piar:lista_piars')

    institucion = _get_institucion(request)
    piar = get_object_or_404(PIAR, pk=pk, institucion=institucion)
    nombre = str(piar)
    piar.delete()
    messages.success(request, f'PIAR "{nombre}" eliminado.')
    return redirect('piar:lista_piars')


# ──────────────────────────────────────────────
# Crear Ajuste
# ──────────────────────────────────────────────

@login_required
@require_POST
def crear_ajuste(request, piar_pk):
    if not _es_docente_o_superior(request.user):
        messages.error(request, 'No tienes permiso para agregar ajustes.')
        return redirect('piar:lista_piars')

    institucion = _get_institucion(request)
    piar = get_object_or_404(PIAR, pk=piar_pk, institucion=institucion)

    materia_id = request.POST.get('materia_id')
    periodo = request.POST.get('periodo')
    logro_ajustado = request.POST.get('logro_ajustado', '')
    estrategias_flexibles = request.POST.get('estrategias_flexibles', '')
    ajuste_evaluativo = request.POST.get('ajuste_evaluativo', '')
    recursos_apoyo = request.POST.get('recursos_apoyo', '')

    materia = None
    if materia_id:
        materia = Materia.objects.filter(pk=materia_id, institucion=institucion).first()

    AjustePIAR.objects.create(
        piar=piar,
        materia=materia,
        periodo=int(periodo),
        logro_ajustado=logro_ajustado,
        estrategias_flexibles=estrategias_flexibles,
        ajuste_evaluativo=ajuste_evaluativo,
        recursos_apoyo=recursos_apoyo,
    )
    messages.success(request, 'Ajuste agregado exitosamente.')
    return redirect('piar:detalle_piar', pk=piar_pk)


# ──────────────────────────────────────────────
# Editar Ajuste
# ──────────────────────────────────────────────

@login_required
def editar_ajuste(request, piar_pk, ajuste_pk):
    if not _es_docente_o_superior(request.user):
        messages.error(request, 'No tienes permiso para editar ajustes.')
        return redirect('piar:lista_piars')

    institucion = _get_institucion(request)
    piar = get_object_or_404(PIAR, pk=piar_pk, institucion=institucion)
    ajuste = get_object_or_404(AjustePIAR, pk=ajuste_pk, piar=piar)
    materias = Materia.objects.filter(institucion=institucion).order_by('nombre_materia')

    if request.method == 'POST':
        materia_id = request.POST.get('materia_id')
        ajuste.materia = Materia.objects.filter(pk=materia_id, institucion=institucion).first() if materia_id else None
        ajuste.periodo = int(request.POST.get('periodo', ajuste.periodo))
        ajuste.logro_ajustado = request.POST.get('logro_ajustado', ajuste.logro_ajustado)
        ajuste.estrategias_flexibles = request.POST.get('estrategias_flexibles', ajuste.estrategias_flexibles)
        ajuste.ajuste_evaluativo = request.POST.get('ajuste_evaluativo', ajuste.ajuste_evaluativo)
        ajuste.recursos_apoyo = request.POST.get('recursos_apoyo', ajuste.recursos_apoyo)
        ajuste.seguimiento = request.POST.get('seguimiento', ajuste.seguimiento)
        ajuste.alcanzado = request.POST.get('alcanzado') == 'on'
        ajuste.save()
        messages.success(request, 'Ajuste actualizado exitosamente.')
        return redirect('piar:detalle_piar', pk=piar_pk)

    return render(request, 'piar/form_ajuste.html', {
        'titulo_pagina': 'Editar Ajuste PIAR',
        'piar': piar,
        'ajuste': ajuste,
        'materias': materias,
        'periodos': AjustePIAR.PERIODO_CHOICES,
    })


# ──────────────────────────────────────────────
# Eliminar Ajuste
# ──────────────────────────────────────────────

@login_required
@require_POST
def eliminar_ajuste(request, piar_pk, ajuste_pk):
    if not _es_docente_o_superior(request.user):  # A07 — verificar rol antes de eliminar
        messages.error(request, 'No tienes permiso para eliminar ajustes.')
        return redirect('piar:lista_piars')
    institucion = _get_institucion(request)
    piar = get_object_or_404(PIAR, pk=piar_pk, institucion=institucion)
    ajuste = get_object_or_404(AjustePIAR, pk=ajuste_pk, piar=piar)
    ajuste.delete()
    messages.success(request, 'Ajuste eliminado.')
    return redirect('piar:detalle_piar', pk=piar_pk)


# ──────────────────────────────────────────────
# Actualizar Seguimiento (AJAX)
# ──────────────────────────────────────────────

@login_required
@require_POST
def actualizar_seguimiento(request, piar_pk, ajuste_pk):
    institucion = _get_institucion(request)
    piar = get_object_or_404(PIAR, pk=piar_pk, institucion=institucion)
    ajuste = get_object_or_404(AjustePIAR, pk=ajuste_pk, piar=piar)

    ajuste.seguimiento = request.POST.get('seguimiento', ajuste.seguimiento)
    ajuste.alcanzado = request.POST.get('alcanzado', '').lower() in ('true', '1', 'on', 'yes')
    ajuste.save()
    return JsonResponse({'ok': True, 'alcanzado': ajuste.alcanzado, 'seguimiento': ajuste.seguimiento})
