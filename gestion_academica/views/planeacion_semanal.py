"""
gestion_academica/views/planeacion_semanal.py
=============================================
Módulo de Malla Curricular y Plan Semanal Docente.

Flujo:
  Coordinador crea MallaCurricular (estructura del año).
  Docente crea PlanSemanal semana a semana vinculado a su curso.
  Docente agrega ítems → puede convertirlos en Deber o ActividadCalificable.
  Docente envía el plan → Coordinador aprueba o devuelve con observaciones.
"""
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Count, Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..models import (
    ActividadCalificable,
    Curso,
    DBAPredefinido,
    Deber,
    Docente,
    EscalaValorativa,
    Grado,
    ItemMalla,
    ItemPlanSemanal,
    MallaCurricular,
    Materia,
    Notificacion,
    PlanSemanal,
    TipoActividad,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_institucion(request):
    return getattr(request.user, 'institucion_asociada', None)


def _push_ws(group_name: str, *, kind: str, title: str, message: str,
             url: str = '', severity: str = 'info') -> None:
    """
    Envía una notificación WebSocket en tiempo real al grupo indicado.
    Falla silenciosamente si Redis / Channels no está disponible,
    para no interrumpir el flujo HTTP normal.
    """
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'send_notification',
                    'kind': kind,
                    'title': title,
                    'message': message,
                    'url': url,
                    'severity': severity,
                },
            )
    except Exception:
        pass  # no romper el flujo si el canal no está disponible


def _week_bounds(d: date):
    """Returns (monday, friday) of the ISO week that contains *d*."""
    monday = d - timedelta(days=d.weekday())
    friday = monday + timedelta(days=4)
    return monday, friday


def _label_semana(inicio: date, fin: date) -> str:
    meses = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
             'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    s = f"{inicio.day} {meses[inicio.month - 1]}"
    e = f"{fin.day} {meses[fin.month - 1]} {fin.year}"
    return f"{s} – {e}"


# ══════════════════════════════════════════════════════════════════════════════
#  MALLA CURRICULAR  (Coordinador / Jefe de Área)
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@permission_required('gestion_academica.view_mallacurricular', raise_exception=True)
def malla_curricular_list(request):
    """Lista de mallas curriculares; el coordinador puede crear nuevas."""
    institucion = _get_institucion(request)
    año_actual  = date.today().year
    años        = list(range(año_actual - 1, año_actual + 3))
    # Filtro por año desde querystring — DEBE ir antes del queryset
    try:
        año_filtro = int(request.GET.get('año', año_actual))
    except (ValueError, TypeError):
        año_filtro = año_actual

    mallas = (
        MallaCurricular.objects
        .filter(institucion=institucion, año_lectivo=año_filtro)
        .select_related('materia', 'grado')
        .annotate(total_items=Count('items'))
        .order_by('grado__orden', 'materia__nombre_materia')
    )
    materias = Materia.objects.filter(institucion=institucion).order_by('nombre_materia')
    grados   = Grado.objects.filter(institucion=institucion).order_by('orden')

    if request.method == 'POST':
        materia_id  = request.POST.get('materia')
        grado_id    = request.POST.get('grado')
        año_lectivo = request.POST.get('año_lectivo', año_actual)
        desc        = request.POST.get('descripcion_general', '')
        materia = get_object_or_404(Materia, pk=materia_id, institucion=institucion)
        grado   = get_object_or_404(Grado,   pk=grado_id,   institucion=institucion)
        malla, created = MallaCurricular.objects.get_or_create(
            materia=materia, grado=grado,
            año_lectivo=año_lectivo, institucion=institucion,
            defaults={'descripcion_general': desc, 'creado_por': request.user},
        )
        if created:
            messages.success(request, f'Malla creada: {malla}')
        else:
            messages.info(request, 'Ya existe una malla para esa combinación.')
        return redirect('gestion_academica:malla_curricular_detalle', pk=malla.pk)

    # Construir estructura agrupada: grado → materia → malla (o None)
    mallas_map = {(m.grado_id, m.materia_id): m for m in mallas}
    grados_data = []
    for grado in grados:
        filas = []
        for materia in materias:
            malla = mallas_map.get((grado.pk, materia.pk))
            filas.append({'materia': materia, 'malla': malla})
        total_creadas = sum(1 for f in filas if f['malla'])
        grados_data.append({
            'grado': grado,
            'filas': filas,
            'total_creadas': total_creadas,
            'total_materias': len(materias),
            'completo': total_creadas == len(materias) and len(materias) > 0,
        })

    context = {
        'titulo_pagina': 'Mallas Curriculares',
        'grados_data': grados_data,
        'materias': materias,
        'grados': grados,
        'años': años,
        'año_actual': año_filtro,
        'total_mallas': sum(gd['total_creadas'] for gd in grados_data),
    }
    return render(request, 'gestion_academica/malla_curricular_list.html', context)


@login_required
@permission_required('gestion_academica.view_mallacurricular', raise_exception=True)
def malla_curricular_detalle(request, pk):
    """Detalle de la malla, organizado por período → mes → semana."""
    institucion = _get_institucion(request)
    malla = get_object_or_404(MallaCurricular, pk=pk, institucion=institucion)

    # Agrupar ítems por período
    items_qs = malla.items.all().order_by('periodo', 'orden')
    por_periodo = {1: [], 2: [], 3: [], 4: []}
    for item in items_qs:
        por_periodo.setdefault(item.periodo, []).append(item)

    auto_print = request.GET.get('print') == '1'
    es_bilingue = getattr(institucion, 'es_bilingue', False)
    idioma_secundario = getattr(institucion, 'get_idioma_secundario_display', lambda: '')()

    escala_qs = list(EscalaValorativa.objects.filter(institucion=institucion).order_by('-nota_maxima'))
    niveles = {
        'superior': escala_qs[0] if len(escala_qs) > 0 else None,
        'alto':     escala_qs[1] if len(escala_qs) > 1 else None,
        'basico':   escala_qs[2] if len(escala_qs) > 2 else None,
        'bajo':     escala_qs[3] if len(escala_qs) > 3 else None,
    }

    context = {
        'titulo_pagina': f'Malla Curricular · {malla.materia} · {malla.grado}',
        'malla': malla,
        'por_periodo': por_periodo,
        'periodos': [1, 2, 3, 4],
        'auto_print': auto_print,
        'es_bilingue': es_bilingue,
        'idioma_secundario': idioma_secundario,
        'niveles': niveles,
    }
    return render(request, 'gestion_academica/malla_curricular_detalle.html', context)


@login_required
def malla_curricular_imprimir(request, pk):
    """Vista limpia de impresión — sin layout del dashboard."""
    institucion = _get_institucion(request)
    malla = get_object_or_404(MallaCurricular, pk=pk, institucion=institucion)
    items_qs = malla.items.all().order_by('periodo', 'orden')
    por_periodo = {1: [], 2: [], 3: [], 4: []}
    for item in items_qs:
        por_periodo.setdefault(item.periodo, []).append(item)
    context = {
        'malla': malla,
        'por_periodo': por_periodo,
        'periodos': [1, 2, 3, 4],
    }
    return render(request, 'gestion_academica/malla_curricular_print.html', context)


@login_required
@require_POST
@permission_required('gestion_academica.delete_mallacurricular', raise_exception=True)
def malla_curricular_delete(request, pk):
    """Elimina una malla curricular completa con todos sus ítems."""
    institucion = _get_institucion(request)
    malla = get_object_or_404(MallaCurricular, pk=pk, institucion=institucion)
    nombre = f'{malla.materia} · {malla.grado} · {malla.año_lectivo}'
    malla.delete()
    messages.success(request, f'Malla eliminada: {nombre}')
    return redirect('gestion_academica:malla_curricular_list')


@login_required
def malla_docente_consulta(request):
    """
    Vista de consulta de Malla Curricular para el docente.
    Muestra (sólo lectura) todas las mallas de la institución.
    Si el docente tiene cursos asignados se destaca sus materias; si no,
    muestra todas igualmente (útil para coordinadores que prueban la vista).
    """
    institucion = _get_institucion(request)
    año_actual = date.today().year
    años = list(range(año_actual - 1, año_actual + 2))
    try:
        año_filtro = int(request.GET.get('año', año_actual))
    except (ValueError, TypeError):
        año_filtro = año_actual

    # Intentar obtener el perfil docente para filtrar sus materias
    try:
        docente = Docente.objects.get(usuario=request.user, institucion=institucion)
        cursos = (
            Curso.objects
            .filter(docentes_asignados=docente, institucion=institucion)
            .values_list('materia_id', 'grado_id')
            .distinct()
        )
        mis_pares = {(m, g) for m, g in cursos}
    except Docente.DoesNotExist:
        docente = None
        mis_pares = set()

    # Mostrar TODAS las mallas de la institución en el año seleccionado
    mallas = (
        MallaCurricular.objects
        .filter(institucion=institucion, año_lectivo=año_filtro)
        .select_related('materia', 'grado')
        .annotate(total_items=Count('items'))
        .order_by('grado__orden', 'materia__nombre_materia')
    )

    # Marcar cuáles son "mis" mallas (asignadas al docente)
    for m in mallas:
        m.es_mia = (m.materia_id, m.grado_id) in mis_pares

    return render(request, 'gestion_academica/malla_docente_consulta.html', {
        'mallas': mallas,
        'año_filtro': año_filtro,
        'años': años,
        'sin_cursos': False,
        'tiene_perfil_docente': docente is not None,
    })


@login_required
def malla_docente_detalle(request, pk):
    """
    Detalle de una malla curricular en modo sólo lectura para el docente.
    Cualquier usuario de la institución puede consultarla.
    """
    institucion = _get_institucion(request)
    malla = get_object_or_404(MallaCurricular, pk=pk, institucion=institucion)

    items_qs = malla.items.all().order_by('periodo', 'orden')
    por_periodo = {1: [], 2: [], 3: [], 4: []}
    for item in items_qs:
        por_periodo.setdefault(item.periodo, []).append(item)

    return render(request, 'gestion_academica/malla_docente_detalle.html', {
        'malla': malla,
        'por_periodo': por_periodo,
        'periodos': [1, 2, 3, 4],
    })


@login_required
@permission_required('gestion_academica.add_itemmalla', raise_exception=True)
def item_malla_add(request, pk):
    """Agrega un ítem a la malla (POST)."""
    institucion = _get_institucion(request)
    malla = get_object_or_404(MallaCurricular, pk=pk, institucion=institucion)

    if request.method == 'POST':
        periodo      = request.POST.get('periodo')
        eje          = request.POST.get('eje_tematico', '').strip()
        logro        = request.POST.get('logro', '').strip()
        ebc           = request.POST.get('ebc', '').strip()
        dba           = request.POST.get('dba', '').strip()
        evidencias_dba = request.POST.get('evidencias_dba', '').strip()
        competencias  = request.POST.get('competencias', '').strip()
        ind_bajo     = request.POST.get('indicador_bajo', '').strip()
        ind_basico   = request.POST.get('indicador_basico', '').strip()
        ind_alto     = request.POST.get('indicador_alto', '').strip()
        ind_superior = request.POST.get('indicador_superior', '').strip()
        metodologia  = request.POST.get('metodologia', '').strip()
        recursos     = request.POST.get('recursos', '').strip()
        evaluacion   = request.POST.get('evaluacion', '').strip()
        tiempo       = request.POST.get('tiempo_semanas', 10)
        # Campos L2 (bilingüe)
        eje_L2          = request.POST.get('eje_tematico_L2', '').strip()
        logro_L2        = request.POST.get('logro_L2', '').strip()
        competencias_L2 = request.POST.get('competencias_L2', '').strip()
        ind_bajo_L2     = request.POST.get('indicador_bajo_L2', '').strip()
        ind_basico_L2   = request.POST.get('indicador_basico_L2', '').strip()
        ind_alto_L2     = request.POST.get('indicador_alto_L2', '').strip()
        ind_superior_L2 = request.POST.get('indicador_superior_L2', '').strip()

        if eje and logro:
            ItemMalla.objects.create(
                malla=malla, periodo=periodo,
                eje_tematico=eje, logro=logro,
                ebc=ebc or None, dba=dba or None,
                evidencias_dba=evidencias_dba or None,
                competencias=competencias or None,
                indicador_bajo=ind_bajo or None,
                indicador_basico=ind_basico or None,
                indicador_alto=ind_alto or None,
                indicador_superior=ind_superior or None,
                metodologia=metodologia or None,
                recursos=recursos or None,
                evaluacion=evaluacion or None,
                tiempo_semanas=int(tiempo),
                eje_tematico_L2=eje_L2,
                logro_L2=logro_L2,
                competencias_L2=competencias_L2 or None,
                indicador_bajo_L2=ind_bajo_L2 or None,
                indicador_basico_L2=ind_basico_L2 or None,
                indicador_alto_L2=ind_alto_L2 or None,
                indicador_superior_L2=ind_superior_L2 or None,
            )
            messages.success(request, 'Ítem agregado a la malla.')
        else:
            messages.error(request, 'Eje temático y Logro son obligatorios.')

    return redirect('gestion_academica:malla_curricular_detalle', pk=pk)


@login_required
@permission_required('gestion_academica.change_itemmalla', raise_exception=True)
def item_malla_edit(request, item_pk):
    """Edita un ítem de malla (GET muestra formulario inline, POST guarda)."""
    institucion = _get_institucion(request)
    item = get_object_or_404(ItemMalla, pk=item_pk, malla__institucion=institucion)

    if request.method == 'POST':
        item.periodo         = request.POST.get('periodo', item.periodo)
        item.eje_tematico    = request.POST.get('eje_tematico', item.eje_tematico).strip()
        item.logro           = request.POST.get('logro', item.logro).strip()
        item.ebc             = request.POST.get('ebc', '').strip() or None
        item.dba             = request.POST.get('dba', '').strip() or None
        item.evidencias_dba  = request.POST.get('evidencias_dba', '').strip() or None
        item.competencias    = request.POST.get('competencias', '').strip() or None
        item.indicador_bajo     = request.POST.get('indicador_bajo', '').strip() or None
        item.indicador_basico   = request.POST.get('indicador_basico', '').strip() or None
        item.indicador_alto     = request.POST.get('indicador_alto', '').strip() or None
        item.indicador_superior = request.POST.get('indicador_superior', '').strip() or None
        item.metodologia     = request.POST.get('metodologia', '').strip() or None
        item.recursos        = request.POST.get('recursos', '').strip() or None
        item.evaluacion      = request.POST.get('evaluacion', '').strip() or None
        item.tiempo_semanas  = int(request.POST.get('tiempo_semanas', item.tiempo_semanas))
        # Campos L2 (bilingüe)
        item.eje_tematico_L2    = request.POST.get('eje_tematico_L2', '').strip()
        item.logro_L2           = request.POST.get('logro_L2', '').strip()
        item.competencias_L2    = request.POST.get('competencias_L2', '').strip() or None
        item.indicador_bajo_L2    = request.POST.get('indicador_bajo_L2', '').strip() or None
        item.indicador_basico_L2  = request.POST.get('indicador_basico_L2', '').strip() or None
        item.indicador_alto_L2    = request.POST.get('indicador_alto_L2', '').strip() or None
        item.indicador_superior_L2 = request.POST.get('indicador_superior_L2', '').strip() or None
        item.save()
        messages.success(request, 'Ítem actualizado.')
        return redirect('gestion_academica:malla_curricular_detalle', pk=item.malla_id)

    inst = _get_institucion(request)
    # Escala valorativa de la institución (orden descendente = superior primero)
    escala_qs = list(EscalaValorativa.objects.filter(institucion=inst).order_by('-nota_maxima'))
    # Asignar a cada posición (superior/alto/basico/bajo) el nivel institucional
    niveles = {
        'superior': escala_qs[0] if len(escala_qs) > 0 else None,
        'alto':     escala_qs[1] if len(escala_qs) > 1 else None,
        'basico':   escala_qs[2] if len(escala_qs) > 2 else None,
        'bajo':     escala_qs[3] if len(escala_qs) > 3 else None,
    }
    context = {
        'titulo_pagina': 'Editar Ítem de Malla',
        'item': item,
        'malla': item.malla,
        'es_bilingue': getattr(inst, 'es_bilingue', False),
        'idioma_secundario': getattr(inst, 'get_idioma_secundario_display', lambda: '')(),
        'niveles': niveles,
    }
    return render(request, 'gestion_academica/item_malla_edit.html', context)


@login_required
@require_POST
@permission_required('gestion_academica.delete_itemmalla', raise_exception=True)
def item_malla_delete(request, item_pk):
    """Elimina un ítem de malla."""
    institucion = _get_institucion(request)
    item = get_object_or_404(ItemMalla, pk=item_pk, malla__institucion=institucion)
    malla_pk = item.malla_id
    item.delete()
    messages.success(request, 'Ítem eliminado.')
    return redirect('gestion_academica:malla_curricular_detalle', pk=malla_pk)


# ══════════════════════════════════════════════════════════════════════════════
#  PLAN SEMANAL  (Docente)
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def mis_planes_semanales(request):
    """Dashboard del docente: lista de planes por semana con estado."""
    try:
        docente = request.user.docente
    except Exception:
        messages.error(request, 'Solo los docentes pueden acceder a los planes semanales.')
        return redirect('gestion_academica:inicio_academico')

    institucion = _get_institucion(request)
    planes = (
        PlanSemanal.objects
        .filter(docente=docente, institucion=institucion)
        .select_related('curso__materia', 'curso__grado')
        .annotate(total_items=Count('items'))
        .order_by('-semana_inicio')
    )

    # Semana actual para botón de acceso rápido
    hoy = date.today()
    lunes, viernes = _week_bounds(hoy)
    plan_semana_actual = PlanSemanal.objects.filter(
        docente=docente, semana_inicio=lunes, institucion=institucion
    ).first()

    # Cursos del docente (para selector al crear nuevo plan)
    cursos = docente.cursos_impartidos.select_related('materia', 'grado').filter(
        periodo_academico__activo=True, institucion=institucion
    )

    # Etiquetas de semana para cada plan
    planes_con_label = [
        (p, _label_semana(p.semana_inicio, p.semana_fin)) for p in planes
    ]

    context = {
        'titulo_pagina': 'Mis Planes Semanales',
        'planes_con_label': planes_con_label,
        'cursos': cursos,
        'semana_actual_inicio': lunes,
        'semana_actual_fin': viernes,
        'semana_actual_label': _label_semana(lunes, viernes),
        'plan_semana_actual': plan_semana_actual,
    }
    return render(request, 'gestion_academica/mis_planes_semanales.html', context)


@login_required
def plan_semanal_crear(request):
    """Crea un nuevo plan semanal para el docente."""
    try:
        docente = request.user.docente
    except Exception:
        return redirect('gestion_academica:inicio_academico')

    institucion = _get_institucion(request)

    if request.method == 'POST':
        curso_id        = request.POST.get('curso')
        semana_inicio_s = request.POST.get('semana_inicio')  # YYYY-MM-DD
        try:
            curso = get_object_or_404(Curso, pk=curso_id, institucion=institucion)
            semana_inicio = date.fromisoformat(semana_inicio_s)
            # Normalizar al lunes de esa semana
            semana_inicio = semana_inicio - timedelta(days=semana_inicio.weekday())
            semana_fin    = semana_inicio + timedelta(days=4)
            plan, created = PlanSemanal.objects.get_or_create(
                docente=docente, curso=curso, semana_inicio=semana_inicio,
                institucion=institucion,
                defaults={
                    'semana_fin': semana_fin,
                },
            )
            if not created:
                messages.info(request, 'Ya tienes un plan para esa semana y curso.')
            return redirect('gestion_academica:plan_semanal_detalle', pk=plan.pk)
        except Exception as e:
            messages.error(request, f'Error al crear el plan: {e}')
            return redirect('gestion_academica:mis_planes_semanales')

    return redirect('gestion_academica:mis_planes_semanales')


@login_required
def plan_semanal_detalle(request, pk):
    """Vista principal del plan semanal: ítems por día + formulario para añadir."""
    try:
        docente = request.user.docente
    except Exception:
        return redirect('gestion_academica:inicio_academico')

    institucion = _get_institucion(request)
    plan = get_object_or_404(PlanSemanal, pk=pk, docente=docente, institucion=institucion)

    # Ítems del plan agrupados por día
    items = plan.items.select_related('item_malla', 'deber', 'actividad').order_by('fecha', 'orden')
    dias = {}
    dia = plan.semana_inicio
    DIAS_NOMBRES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
    for i, nombre in enumerate(DIAS_NOMBRES):
        d = plan.semana_inicio + timedelta(days=i)
        dias[d] = {'nombre': nombre, 'items': []}
    for item in items:
        if item.fecha in dias:
            dias[item.fecha]['items'].append(item)

    # Ítems de malla disponibles para este grado + materia + semana
    malla_qs = ItemMalla.objects.filter(
        malla__grado=plan.curso.grado,
        malla__materia=plan.curso.materia,
        malla__año_lectivo=plan.semana_inicio.year,
        malla__institucion=institucion,
    ).select_related('malla')

    # TipoActividad para el modal de crear actividad
    tipos_actividad = TipoActividad.objects.filter(institucion=institucion)

    label = _label_semana(plan.semana_inicio, plan.semana_fin)

    context = {
        'titulo_pagina': f'Plan Semanal · {label}',
        'plan': plan,
        'label': label,
        'dias': dias,
        'puede_editar': plan.estado in (PlanSemanal.Estado.BORRADOR, PlanSemanal.Estado.CON_OBSERVACIONES),
        'malla_items': malla_qs,
        'tipos_actividad': tipos_actividad,
    }
    return render(request, 'gestion_academica/plan_semanal_detalle.html', context)


@login_required
@require_POST
def item_plan_add(request, pk):
    """Agrega un ítem al plan semanal."""
    try:
        docente = request.user.docente
    except Exception:
        return redirect('gestion_academica:inicio_academico')

    institucion = _get_institucion(request)
    plan = get_object_or_404(PlanSemanal, pk=pk, docente=docente, institucion=institucion)

    if plan.estado not in (PlanSemanal.Estado.BORRADOR, PlanSemanal.Estado.CON_OBSERVACIONES):
        messages.error(request, 'No puedes modificar un plan ya enviado/aprobado.')
        return redirect('gestion_academica:plan_semanal_detalle', pk=pk)

    fecha_s    = request.POST.get('fecha')
    titulo     = request.POST.get('titulo', '').strip()
    descripcion = request.POST.get('descripcion', '').strip()
    item_malla_id = request.POST.get('item_malla')

    if not titulo or not fecha_s:
        messages.error(request, 'Fecha y título son obligatorios.')
        return redirect('gestion_academica:plan_semanal_detalle', pk=pk)

    try:
        fecha = date.fromisoformat(fecha_s)
    except ValueError:
        messages.error(request, 'Fecha inválida.')
        return redirect('gestion_academica:plan_semanal_detalle', pk=pk)

    item_malla = None
    if item_malla_id:
        item_malla = ItemMalla.objects.filter(pk=item_malla_id, malla__institucion=institucion).first()

    ItemPlanSemanal.objects.create(
        plan=plan,
        fecha=fecha,
        titulo=titulo,
        descripcion=descripcion or None,
        item_malla=item_malla,
    )
    messages.success(request, 'Clase añadida al plan.')
    return redirect('gestion_academica:plan_semanal_detalle', pk=pk)


@login_required
@require_POST
def item_plan_delete(request, item_pk):
    """Elimina un ítem del plan semanal."""
    try:
        docente = request.user.docente
    except Exception:
        return redirect('gestion_academica:inicio_academico')

    institucion = _get_institucion(request)
    item = get_object_or_404(ItemPlanSemanal, pk=item_pk, plan__docente=docente, plan__institucion=institucion)
    plan_pk = item.plan_id
    if item.plan.estado in (PlanSemanal.Estado.BORRADOR, PlanSemanal.Estado.CON_OBSERVACIONES):
        item.delete()
        messages.success(request, 'Ítem eliminado.')
    else:
        messages.error(request, 'No puedes eliminar ítems de un plan ya enviado.')
    return redirect('gestion_academica:plan_semanal_detalle', pk=plan_pk)


@login_required
@require_POST
def item_plan_edit(request, item_pk):
    """Edita el título, descripción y vínculo de malla de un ítem del plan."""
    try:
        docente = request.user.docente
    except Exception:
        return redirect('gestion_academica:inicio_academico')

    institucion = _get_institucion(request)
    item = get_object_or_404(
        ItemPlanSemanal,
        pk=item_pk,
        plan__docente=docente,
        plan__institucion=institucion,
    )

    if item.plan.estado not in (PlanSemanal.Estado.BORRADOR, PlanSemanal.Estado.CON_OBSERVACIONES):
        messages.error(request, 'No puedes editar ítems de un plan ya enviado.')
        return redirect('gestion_academica:plan_semanal_detalle', pk=item.plan_id)

    titulo      = request.POST.get('titulo', '').strip()
    descripcion = request.POST.get('descripcion', '').strip()
    item_malla_id = request.POST.get('item_malla')

    if not titulo:
        messages.error(request, 'El título es obligatorio.')
        return redirect('gestion_academica:plan_semanal_detalle', pk=item.plan_id)

    item.titulo      = titulo
    item.descripcion = descripcion or None
    item.item_malla  = (
        ItemMalla.objects.filter(pk=item_malla_id, malla__institucion=institucion).first()
        if item_malla_id else None
    )
    item.save(update_fields=['titulo', 'descripcion', 'item_malla'])
    messages.success(request, 'Clase actualizada.')
    return redirect('gestion_academica:plan_semanal_detalle', pk=item.plan_id)


@login_required
def item_plan_crear_deber(request, item_pk):
    """Convierte un ítem del plan en un Deber."""
    try:
        docente = request.user.docente
    except Exception:
        return redirect('gestion_academica:inicio_academico')

    institucion = _get_institucion(request)
    item = get_object_or_404(ItemPlanSemanal, pk=item_pk, plan__docente=docente, plan__institucion=institucion)

    if item.deber:
        messages.info(request, 'Este ítem ya tiene un deber creado.')
        return redirect('gestion_academica:plan_semanal_detalle', pk=item.plan_id)

    if request.method == 'POST':
        titulo       = request.POST.get('titulo', item.titulo).strip()
        descripcion  = request.POST.get('descripcion', item.descripcion or '').strip()
        fecha_entrega = request.POST.get('fecha_entrega')

        if not fecha_entrega:
            messages.error(request, 'La fecha de entrega es obligatoria.')
            return render(request, 'gestion_academica/item_plan_crear_deber.html', {
                'titulo_pagina': 'Crear Deber desde Plan',
                'item': item,
            })

        deber = Deber.objects.create(
            curso=item.plan.curso,
            titulo=titulo,
            descripcion=descripcion or None,
            fecha_asignacion=item.fecha,
            fecha_entrega=date.fromisoformat(fecha_entrega),
            institucion=institucion,
        )
        item.deber = deber
        item.save(update_fields=['deber'])
        messages.success(request, f'Deber "{deber.titulo}" creado y vinculado al plan.')
        return redirect('gestion_academica:plan_semanal_detalle', pk=item.plan_id)

    context = {
        'titulo_pagina': 'Convertir a Deber',
        'item': item,
    }
    return render(request, 'gestion_academica/item_plan_crear_deber.html', context)


@login_required
def item_plan_crear_actividad(request, item_pk):
    """Convierte un ítem del plan en una ActividadCalificable."""
    try:
        docente = request.user.docente
    except Exception:
        return redirect('gestion_academica:inicio_academico')

    institucion = _get_institucion(request)
    item = get_object_or_404(ItemPlanSemanal, pk=item_pk, plan__docente=docente, plan__institucion=institucion)

    if item.actividad:
        messages.info(request, 'Este ítem ya tiene una actividad evaluativa creada.')
        return redirect('gestion_academica:plan_semanal_detalle', pk=item.plan_id)

    tipos = TipoActividad.objects.filter(institucion=institucion)

    if request.method == 'POST':
        titulo          = request.POST.get('titulo', item.titulo).strip()
        descripcion     = request.POST.get('descripcion', item.descripcion or '').strip()
        tipo_id         = request.POST.get('tipo_actividad')
        fecha_entrega_s = request.POST.get('fecha_entrega_limite', '')

        tipo = get_object_or_404(TipoActividad, pk=tipo_id, institucion=institucion)

        actividad = ActividadCalificable.objects.create(
            curso=item.plan.curso,
            tipo_actividad=tipo,
            titulo=titulo,
            descripcion=descripcion or None,
            institucion=institucion,
            fecha_publicacion=item.fecha,
            fecha_entrega_limite=date.fromisoformat(fecha_entrega_s) if fecha_entrega_s else None,
        )
        item.actividad = actividad
        item.save(update_fields=['actividad'])
        messages.success(request, f'Actividad "{actividad.titulo}" creada y vinculada al plan.')
        return redirect('gestion_academica:plan_semanal_detalle', pk=item.plan_id)

    context = {
        'titulo_pagina': 'Convertir a Actividad Evaluativa',
        'item': item,
        'tipos': tipos,
    }
    return render(request, 'gestion_academica/item_plan_crear_actividad.html', context)


@login_required
@require_POST
def plan_semanal_enviar(request, pk):
    """Docente envía el plan al coordinador."""
    try:
        docente = request.user.docente
    except Exception:
        return redirect('gestion_academica:inicio_academico')

    institucion = _get_institucion(request)
    plan = get_object_or_404(PlanSemanal, pk=pk, docente=docente, institucion=institucion)

    if plan.estado not in (PlanSemanal.Estado.BORRADOR, PlanSemanal.Estado.CON_OBSERVACIONES):
        messages.warning(request, 'El plan ya fue enviado anteriormente.')
        return redirect('gestion_academica:plan_semanal_detalle', pk=pk)

    if not plan.items.exists():
        messages.error(request, 'El plan no tiene ítems. Agrega al menos una clase antes de enviar.')
        return redirect('gestion_academica:plan_semanal_detalle', pk=pk)

    es_reenvio = plan.estado == PlanSemanal.Estado.CON_OBSERVACIONES
    plan.estado = PlanSemanal.Estado.ENVIADO
    plan.fecha_envio = timezone.now()
    plan.observaciones_coordinador = None
    plan.save(update_fields=['estado', 'fecha_envio', 'observaciones_coordinador'])

    # Notificar a coordinadores: BD + WebSocket en tiempo real
    from django.contrib.auth import get_user_model
    from django.urls import reverse
    User = get_user_model()
    coordinadores = User.objects.filter(
        institucion_asociada=institucion,
        rol__in=['coordinador', 'administrador'],
        is_active=True,
    )
    label_semana = _label_semana(plan.semana_inicio, plan.semana_fin)
    docente_nombre = request.user.get_full_name() or request.user.username
    accion_txt = 'reenviado corregido' if es_reenvio else 'enviado para revisión'
    titulo_ws  = '📋 Plan reenviado' if es_reenvio else '📋 Nuevo plan para revisar'
    url_revision = reverse('gestion_academica:revisar_plan_semanal', args=[plan.pk])

    for coord in coordinadores:
        # Notificación persistente en BD
        Notificacion.objects.create(
            destinatario=coord,
            mensaje=(
                f'{docente_nombre} ha {accion_txt}: '
                f'{plan.curso.materia.nombre_materia} · {label_semana}'
            ),
            enlace=url_revision,
            institucion=institucion,
        )
        # Push WebSocket instantáneo
        _push_ws(
            f'user_{coord.pk}',
            kind='plan_enviado',
            title=titulo_ws,
            message=(
                f'{docente_nombre} · {plan.curso.materia.nombre_materia} · {label_semana}'
            ),
            url=url_revision,
            severity='warning' if es_reenvio else 'info',
        )

    messages.success(request, 'Plan enviado al coordinador para revisión.')
    return redirect('gestion_academica:plan_semanal_detalle', pk=pk)


# ══════════════════════════════════════════════════════════════════════════════
#  COORDINADOR — Supervisión y Revisión
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@permission_required('gestion_academica.view_plansemanal', raise_exception=True)
def supervisar_planes_semanales(request):
    """Dashboard del coordinador: semáforo de planes por docente y semana."""
    institucion = _get_institucion(request)

    # Semana a visualizar (por defecto la actual)
    hoy = date.today()
    lunes_actual, viernes_actual = _week_bounds(hoy)

    semana_s = request.GET.get('semana')
    if semana_s:
        try:
            semana_ref = date.fromisoformat(semana_s)
            lunes_sel, viernes_sel = _week_bounds(semana_ref)
        except ValueError:
            lunes_sel, viernes_sel = lunes_actual, viernes_actual
    else:
        lunes_sel, viernes_sel = lunes_actual, viernes_actual

    # Todos los docentes de la institución
    docentes = Docente.objects.filter(institucion=institucion).select_related('usuario')

    # Planes de la semana seleccionada
    planes_semana = (
        PlanSemanal.objects
        .filter(institucion=institucion, semana_inicio=lunes_sel)
        .select_related('docente__usuario', 'curso__materia', 'curso__grado')
        .annotate(total_items=Count('items'))
    )
    planes_por_docente = {p.docente_id: p for p in planes_semana}

    # Últimos planes pendientes de revisión (ENVIADOS)
    pendientes = (
        PlanSemanal.objects
        .filter(institucion=institucion, estado=PlanSemanal.Estado.ENVIADO)
        .select_related('docente__usuario', 'curso__materia', 'curso__grado')
        .annotate(total_items=Count('items'))
        .order_by('fecha_envio')[:20]
    )

    # Semanas para navegación (últimas 4 + próximas 2)
    semanas_nav = []
    for delta in range(-4, 3):
        d = lunes_sel + timedelta(weeks=delta)
        semanas_nav.append({
            'inicio': d,
            'fin': d + timedelta(days=4),
            'label': _label_semana(d, d + timedelta(days=4)),
            'activa': d == lunes_sel,
        })

    context = {
        'titulo_pagina': 'Supervisión de Planes Semanales',
        'docentes': docentes,
        'planes_por_docente': planes_por_docente,
        'pendientes': pendientes,
        'semana_inicio': lunes_sel,
        'semana_fin': viernes_sel,
        'semana_label': _label_semana(lunes_sel, viernes_sel),
        'semanas_nav': semanas_nav,
        'PlanEstado': PlanSemanal.Estado,
    }
    return render(request, 'gestion_academica/supervisar_planes_semanales.html', context)


@login_required
def revisar_plan_semanal(request, pk):
    """Coordinador revisa un plan: puede aprobar o devolver con observaciones."""
    user = request.user
    if not (user.is_superuser or (user.is_staff and getattr(user, 'rol', None) in ['coordinador', 'administrador'])):
        from django.contrib import messages as _msg
        _msg.error(request, 'Acceso denegado. Solo coordinadores pueden revisar planes.')
        return redirect('gestion_academica:inicio_academico')

    institucion = _get_institucion(request)
    plan = get_object_or_404(
        PlanSemanal.objects.select_related('docente__usuario', 'curso__materia', 'curso__grado'),
        pk=pk, institucion=institucion,
    )
    items = plan.items.select_related('item_malla', 'deber', 'actividad').order_by('fecha', 'orden')

    # Agrupar ítems por día
    dias = {}
    DIAS_NOMBRES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
    for i, nombre in enumerate(DIAS_NOMBRES):
        d = plan.semana_inicio + timedelta(days=i)
        dias[d] = {'nombre': nombre, 'items': []}
    for item in items:
        if item.fecha in dias:
            dias[item.fecha]['items'].append(item)

    if request.method == 'POST':
        accion = request.POST.get('accion')  # 'aprobar' | 'observar'
        observaciones = request.POST.get('observaciones', '').strip()

        if accion == 'aprobar':
            plan.estado = PlanSemanal.Estado.APROBADO
            plan.observaciones_coordinador = None
        elif accion == 'observar':
            if not observaciones:
                messages.error(request, 'Debes escribir las observaciones para devolver el plan.')
                return redirect('gestion_academica:revisar_plan_semanal', pk=pk)
            plan.estado = PlanSemanal.Estado.CON_OBSERVACIONES
            plan.observaciones_coordinador = observaciones
        else:
            messages.error(request, 'Acción no válida.')
            return redirect('gestion_academica:revisar_plan_semanal', pk=pk)

        plan.revisado_por = request.user
        plan.fecha_revision = timezone.now()
        plan.save(update_fields=['estado', 'observaciones_coordinador', 'revisado_por', 'fecha_revision'])

        # Notificación al docente: BD + WebSocket en tiempo real
        from django.urls import reverse
        label_semana = _label_semana(plan.semana_inicio, plan.semana_fin)
        aprobado      = accion == 'aprobar'
        url_detalle   = reverse('gestion_academica:plan_semanal_detalle', args=[plan.pk])

        Notificacion.objects.create(
            destinatario=plan.docente.usuario,
            mensaje=(
                f'Tu plan semanal ({label_semana}) '
                f'fue {"aprobado ✅" if aprobado else "devuelto con observaciones ⚠️"}.'
            ),
            enlace=url_detalle,
            institucion=plan.institucion,
        )

        _push_ws(
            f'user_{plan.docente.usuario.pk}',
            kind='plan_revisado',
            title='✅ Plan aprobado' if aprobado else '⚠️ Plan devuelto con observaciones',
            message=(
                f'{plan.curso.materia.nombre_materia} · {label_semana}'
                if aprobado else
                f'{plan.curso.materia.nombre_materia} · {label_semana} — revisa las observaciones.'
            ),
            url=url_detalle,
            severity='success' if aprobado else 'warning',
        )

        msg = 'Plan aprobado.' if aprobado else 'Plan devuelto con observaciones.'
        messages.success(request, msg)
        return redirect('gestion_academica:supervisar_planes_semanales')

    context = {
        'titulo_pagina': f'Revisar Plan · {plan.docente.usuario.get_full_name()}',
        'plan': plan,
        'label': _label_semana(plan.semana_inicio, plan.semana_fin),
        'dias': dias,
        'puede_revisar': plan.estado == PlanSemanal.Estado.ENVIADO,
    }
    return render(request, 'gestion_academica/revisar_plan_semanal.html', context)


# ---------------------------------------------------------------------------
# API — Biblioteca de DBA predefinidos (MEN)
# ---------------------------------------------------------------------------

@login_required
def dba_predefinido_api(request):
    """
    Devuelve los DBA oficiales del MEN filtrados por área y grado.
    GET /academico/api/dba/?area=matematicas&grado=4
    """
    area  = request.GET.get('area', '').strip()
    grado = request.GET.get('grado', '').strip()

    qs = DBAPredefinido.objects.all()
    if area:
        qs = qs.filter(area=area)
    if grado:
        qs = qs.filter(grado=grado)

    data = [
        {
            'id':          d.id,
            'numero':      d.numero,
            'enunciado':   d.enunciado,
            'evidencias':  d.evidencias,
            'area_label':  d.get_area_display(),
            'grado_label': d.get_grado_display(),
            'version':     d.version_men,
        }
        for d in qs.order_by('numero')
    ]
    return JsonResponse({'dba': data})


# ---------------------------------------------------------------------------

@login_required
@require_POST
def generar_indicadores_ia(request):
    """
    Genera los 4 indicadores de desempeño con Gemini a partir del DBA,
    evidencias de aprendizaje y la escala valorativa de la institución.
    POST /academico/api/generar-indicadores/
    """
    import json as _json
    import google.generativeai as genai
    from finanzas.institucion_credentials import google_api_key as _get_api_key

    institucion = _get_institucion(request)
    if not institucion:
        return JsonResponse({'error': 'Institución no encontrada.'}, status=400)

    dba        = request.POST.get('dba', '').strip()
    evidencias = request.POST.get('evidencias', '').strip()
    materia    = request.POST.get('materia', '').strip()
    grado      = request.POST.get('grado', '').strip()

    if not dba and not evidencias:
        return JsonResponse(
            {'error': 'Ingresa el DBA o las evidencias antes de generar indicadores con IA.'},
            status=400,
        )

    escala_qs = list(EscalaValorativa.objects.filter(institucion=institucion).order_by('-nota_maxima'))
    niv = {
        'superior': escala_qs[0] if len(escala_qs) > 0 else None,
        'alto':     escala_qs[1] if len(escala_qs) > 1 else None,
        'basico':   escala_qs[2] if len(escala_qs) > 2 else None,
        'bajo':     escala_qs[3] if len(escala_qs) > 3 else None,
    }

    def _niv_str(obj, nombre_fb, min_fb, max_fb):
        if obj:
            return f"{obj.nombre_desempeno} ({obj.nota_minima}–{obj.nota_maxima})"
        return f"{nombre_fb} ({min_fb}–{max_fb})"

    api_key = _get_api_key(institucion)
    if not api_key:
        return JsonResponse(
            {'error': 'La institución no tiene configurada la clave de API de Google (Gemini).'},
            status=500,
        )

    prompt = f"""Eres un experto en currículo escolar colombiano (Ley 115, Decreto 1290, MEN).

Genera 4 indicadores de desempeño para un ítem de malla curricular, uno por cada nivel de la escala valorativa de la institución. Reglas:
- Concretos y observables (el docente puede verificarlos en el aula)
- Progresivos: cada nivel exige mayor autonomía y profundidad cognitiva que el anterior
- Redactados en tercera persona: "El estudiante..."
- Coherentes con el DBA y sus evidencias
- Máximo 2 oraciones por indicador

Datos del ítem:
- Materia: {materia or 'No especificada'}
- Grado: {grado or 'No especificado'}
- DBA: {dba or 'No especificado'}
- Evidencias de aprendizaje: {evidencias or 'No especificadas'}

Escala valorativa de la institución:
- Nivel más bajo: {_niv_str(niv['bajo'], 'Bajo', '1,0', '2,9')}
- Nivel básico: {_niv_str(niv['basico'], 'Básico', '3,0', '3,9')}
- Nivel alto: {_niv_str(niv['alto'], 'Alto', '4,0', '4,5')}
- Nivel superior: {_niv_str(niv['superior'], 'Superior', '4,6', '5,0')}

Responde ÚNICAMENTE con JSON válido, sin markdown ni explicaciones:
{{"bajo": "...", "basico": "...", "alto": "...", "superior": "..."}}"""

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        text = response.text.strip()
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]
            text = text.strip()
        data = _json.loads(text)
        return JsonResponse({
            'bajo':     data.get('bajo', ''),
            'basico':   data.get('basico', ''),
            'alto':     data.get('alto', ''),
            'superior': data.get('superior', ''),
        })
    except Exception as e:
        err = str(e)
        if '429' in err or 'quota' in err.lower() or 'rate' in err.lower():
            return JsonResponse(
                {'error': 'El asistente HALU alcanzó el límite de solicitudes. Intenta en unos minutos.'},
                status=429,
            )
        return JsonResponse({'error': 'Error al generar con IA. Intenta de nuevo.'}, status=500)
