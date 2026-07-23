"""Vistas de Ordenar Secuencias — actividad calificable por curso."""
import json
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from .models import IntentoSecuencia, ItemSecuencia, SecuenciaActividad

MAX_IMAGEN = 2 * 1024 * 1024
MIN_ITEMS = 3
MAX_ITEMS = 8


def _parse_dt(valor):
    if not valor:
        return None
    dt = parse_datetime(valor)
    if dt and settings.USE_TZ and timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


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


def _imagen_valida(f):
    return f.size <= MAX_IMAGEN and (getattr(f, 'content_type', '') or '').startswith('image/')


def _leer_items(request):
    """Lee los elementos indexados. Devuelve (items, error). El ORDEN en que se
    escriben es la posición correcta (1º = posición 1, etc.)."""
    indices = []
    for i in request.POST.getlist('fila'):
        if i.isdigit() and i not in indices:
            indices.append(i)
    items = []
    for i in indices:
        texto = (request.POST.get(f'texto_{i}') or '').strip()[:60]
        imagen = request.FILES.get(f'imagen_{i}')
        if not texto and not imagen:
            continue
        if imagen and not _imagen_valida(imagen):
            return None, "Cada imagen debe pesar máximo 2 MB y ser un archivo de imagen."
        items.append({'texto': texto, 'imagen': imagen})
        if len(items) > MAX_ITEMS:
            return None, f"Máximo {MAX_ITEMS} elementos por secuencia."
    return items, None


# ── Docente / Coordinador ────────────────────────────────────────────────────

@login_required
def lista(request):
    _solo_docente_coord(request.user)
    actividades = _scope(SecuenciaActividad.objects.all(), request.user).select_related(
        'curso__materia', 'curso__grado'
    ).prefetch_related('items', 'intentos')
    if (getattr(request.user, 'rol', '') or '') == 'docente' and not request.user.is_superuser:
        docente = getattr(request.user, 'docente', None)
        actividades = actividades.filter(curso__docentes_asignados=docente) if docente else actividades.none()
    return render(request, 'secuencias/lista.html', {
        'titulo_pagina': 'Ordenar Secuencias', 'actividades': actividades,
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
        try:
            nota_maxima = Decimal(request.POST.get('nota_maxima') or '5')
        except Exception:
            nota_maxima = Decimal('5')

        curso = get_object_or_404(cursos, pk=curso_id) if curso_id else None
        tipo = get_object_or_404(tipos, pk=tipo_id) if tipo_id else None
        fecha_inicio = _parse_dt(request.POST.get('fecha_inicio'))
        fecha_fin = _parse_dt(request.POST.get('fecha_fin'))

        items, error = _leer_items(request)
        if not titulo or not curso or not tipo:
            messages.error(request, "Completa el título, el curso y la categoría.")
        elif error:
            messages.error(request, error)
        elif items is None or len(items) < MIN_ITEMS:
            messages.error(request, f"Agrega al menos {MIN_ITEMS} elementos en el orden correcto.")
        else:
            with transaction.atomic():
                act = SecuenciaActividad.objects.create(
                    institucion=curso.institucion, curso=curso, titulo=titulo,
                    instrucciones=instrucciones, tipo_actividad=tipo,
                    nota_maxima=nota_maxima, creado_por=request.user,
                    fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
                )
                for pos, it in enumerate(items, start=1):
                    ItemSecuencia.objects.create(
                        actividad=act, posicion_correcta=pos,
                        texto=it['texto'], imagen=it['imagen'],
                    )
            messages.success(request, "Secuencia creada. Revísala y publícala para los estudiantes.")
            return redirect('secuencias:detalle', pk=act.pk)

    return render(request, 'secuencias/form.html', {
        'titulo_pagina': 'Nueva secuencia', 'cursos': cursos, 'tipos': tipos,
    })


@login_required
def detalle(request, pk):
    _solo_docente_coord(request.user)
    act = get_object_or_404(
        _scope(SecuenciaActividad.objects.all(), request.user).select_related('curso__materia', 'curso__grado'),
        pk=pk,
    )
    from gestion_academica.models import TipoActividad
    tipos = TipoActividad.objects.filter(institucion=act.institucion)
    return render(request, 'secuencias/detalle.html', {
        'titulo_pagina': act.titulo, 'actividad': act,
        'items': act.items.all(), 'MIN_ITEMS': MIN_ITEMS,
        'tipos': tipos,
    })


def _renumerar(act):
    """Reasigna posicion_correcta 1..N por el orden actual (contiguo)."""
    for i, it in enumerate(act.items.order_by('posicion_correcta', 'id'), start=1):
        if it.posicion_correcta != i:
            it.posicion_correcta = i
            it.save(update_fields=['posicion_correcta'])


@require_POST
@login_required
def editar_datos(request, pk):
    from gestion_academica.models import TipoActividad
    _solo_docente_coord(request.user)
    act = get_object_or_404(_scope(SecuenciaActividad.objects.all(), request.user), pk=pk)
    titulo = (request.POST.get('titulo') or '').strip()
    if not titulo:
        messages.error(request, "El título no puede quedar vacío.")
        return redirect('secuencias:detalle', pk=act.pk)
    act.titulo = titulo
    act.instrucciones = (request.POST.get('instrucciones') or '').strip()
    try:
        act.nota_maxima = Decimal(request.POST.get('nota_maxima') or act.nota_maxima)
    except Exception:
        pass
    tipo_id = request.POST.get('tipo_actividad')
    if tipo_id:
        act.tipo_actividad = get_object_or_404(TipoActividad, pk=tipo_id, institucion=act.institucion)
    act.save(update_fields=['titulo', 'instrucciones', 'nota_maxima', 'tipo_actividad'])
    if act.actividad_calificable_id:
        a = act.actividad_calificable
        a.titulo = act.titulo
        a.tipo_actividad = act.tipo_actividad
        a.descripcion = act.instrucciones or None
        a.save(update_fields=['titulo', 'tipo_actividad', 'descripcion'])
    messages.success(request, "Datos actualizados.")
    return redirect('secuencias:detalle', pk=act.pk)


@require_POST
@login_required
def agregar_item(request, pk):
    _solo_docente_coord(request.user)
    act = get_object_or_404(_scope(SecuenciaActividad.objects.all(), request.user), pk=pk)
    texto = (request.POST.get('texto') or '').strip()[:60]
    imagen = request.FILES.get('imagen')
    if not texto and not imagen:
        messages.error(request, "El elemento necesita imagen o texto.")
        return redirect('secuencias:detalle', pk=act.pk)
    if imagen and not _imagen_valida(imagen):
        messages.error(request, "La imagen debe pesar máximo 2 MB.")
        return redirect('secuencias:detalle', pk=act.pk)
    if act.items.count() >= MAX_ITEMS:
        messages.error(request, f"Máximo {MAX_ITEMS} elementos por secuencia.")
        return redirect('secuencias:detalle', pk=act.pk)
    ultimo = act.items.order_by('-posicion_correcta').first()
    ItemSecuencia.objects.create(
        actividad=act, posicion_correcta=(ultimo.posicion_correcta + 1) if ultimo else 1,
        texto=texto, imagen=imagen,
    )
    messages.success(request, "Elemento agregado al final.")
    return redirect('secuencias:detalle', pk=act.pk)


@require_POST
@login_required
def editar_item(request, pk, item_pk):
    _solo_docente_coord(request.user)
    act = get_object_or_404(_scope(SecuenciaActividad.objects.all(), request.user), pk=pk)
    item = get_object_or_404(ItemSecuencia, pk=item_pk, actividad=act)
    texto = (request.POST.get('texto') or '').strip()[:60]
    item.texto = texto
    imagen = request.FILES.get('imagen')
    if imagen:
        if not _imagen_valida(imagen):
            messages.error(request, "La imagen debe pesar máximo 2 MB.")
            return redirect('secuencias:detalle', pk=act.pk)
        item.imagen = imagen
    elif request.POST.get('quitar_imagen') == 'on':
        item.imagen = None
    if not item.texto and not item.imagen:
        messages.error(request, "El elemento necesita imagen o texto.")
        return redirect('secuencias:detalle', pk=act.pk)
    item.save()
    messages.success(request, "Elemento actualizado.")
    return redirect('secuencias:detalle', pk=act.pk)


@require_POST
@login_required
def mover_item(request, pk, item_pk):
    _solo_docente_coord(request.user)
    act = get_object_or_404(_scope(SecuenciaActividad.objects.all(), request.user), pk=pk)
    _renumerar(act)
    item = get_object_or_404(ItemSecuencia, pk=item_pk, actividad=act)
    direccion = request.POST.get('dir')
    if direccion == 'subir':
        vecino = act.items.filter(posicion_correcta__lt=item.posicion_correcta).order_by('-posicion_correcta').first()
    else:
        vecino = act.items.filter(posicion_correcta__gt=item.posicion_correcta).order_by('posicion_correcta').first()
    if vecino:
        item.posicion_correcta, vecino.posicion_correcta = vecino.posicion_correcta, item.posicion_correcta
        item.save(update_fields=['posicion_correcta'])
        vecino.save(update_fields=['posicion_correcta'])
    return redirect('secuencias:detalle', pk=act.pk)


@require_POST
@login_required
def eliminar_item(request, pk, item_pk):
    _solo_docente_coord(request.user)
    act = get_object_or_404(_scope(SecuenciaActividad.objects.all(), request.user), pk=pk)
    item = get_object_or_404(ItemSecuencia, pk=item_pk, actividad=act)
    item.delete()
    _renumerar(act)
    messages.success(request, "Elemento eliminado.")
    return redirect('secuencias:detalle', pk=act.pk)


@require_POST
@login_required
def publicar(request, pk):
    _solo_docente_coord(request.user)
    act = get_object_or_404(_scope(SecuenciaActividad.objects.all(), request.user), pk=pk)
    if act.items.count() < MIN_ITEMS:
        messages.error(request, f"Necesitas al menos {MIN_ITEMS} elementos para publicar.")
        return redirect('secuencias:detalle', pk=act.pk)
    from gestion_academica.models import ActividadCalificable
    with transaction.atomic():
        if not act.actividad_calificable:
            ac = ActividadCalificable.objects.create(
                curso=act.curso, tipo_actividad=act.tipo_actividad,
                titulo=act.titulo, descripcion=act.instrucciones or None,
                institucion=act.institucion, fecha_publicacion=timezone.localdate(),
            )
            act.actividad_calificable = ac
        act.estado = SecuenciaActividad.Estado.PUBLICADO
        act.save(update_fields=['actividad_calificable', 'estado'])
    messages.success(request, "¡Secuencia publicada! Ya aparece a los estudiantes del curso.")
    return redirect('secuencias:detalle', pk=act.pk)


@require_POST
@login_required
def cerrar(request, pk):
    _solo_docente_coord(request.user)
    act = get_object_or_404(_scope(SecuenciaActividad.objects.all(), request.user), pk=pk)
    act.estado = SecuenciaActividad.Estado.CERRADO
    act.fecha_cierre = timezone.now()
    act.save(update_fields=['estado', 'fecha_cierre'])
    messages.success(request, "Secuencia cerrada.")
    return redirect('secuencias:detalle', pk=act.pk)


@require_POST
@login_required
def editar_fechas(request, pk):
    _solo_docente_coord(request.user)
    act = get_object_or_404(_scope(SecuenciaActividad.objects.all(), request.user), pk=pk)
    act.fecha_inicio = _parse_dt(request.POST.get('fecha_inicio'))
    act.fecha_fin = _parse_dt(request.POST.get('fecha_fin'))
    act.save(update_fields=['fecha_inicio', 'fecha_fin'])
    messages.success(request, "Fechas actualizadas.")
    return redirect('secuencias:detalle', pk=act.pk)


@require_POST
@login_required
def eliminar(request, pk):
    _solo_docente_coord(request.user)
    act = get_object_or_404(_scope(SecuenciaActividad.objects.all(), request.user), pk=pk)
    act.delete()
    messages.success(request, "Secuencia eliminada.")
    return redirect('secuencias:lista')


@login_required
def resultados(request, pk):
    _solo_docente_coord(request.user)
    act = get_object_or_404(
        _scope(SecuenciaActividad.objects.all(), request.user).select_related('curso__grado'), pk=pk,
    )
    intentos = act.intentos.select_related('estudiante__usuario').order_by(
        '-porcentaje', 'estudiante__usuario__first_name')
    return render(request, 'secuencias/resultados.html', {
        'titulo_pagina': f'Resultados: {act.titulo}', 'actividad': act, 'intentos': intentos,
    })


# ── Estudiante ───────────────────────────────────────────────────────────────

def _estudiante(user):
    return getattr(user, 'estudiante', None)


@login_required
def mis_secuencias(request):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None or not estudiante.grado_actual_id:
        return render(request, 'secuencias/mis_secuencias.html', {'titulo_pagina': 'Ordenar Secuencias', 'items': []})

    actividades = SecuenciaActividad.objects.filter(
        institucion=estudiante.institucion,
        curso__grado=estudiante.grado_actual,
        estado=SecuenciaActividad.Estado.PUBLICADO,
    ).select_related('curso__materia').order_by('-creado_en')
    hechos = {
        i.actividad_id: i for i in
        IntentoSecuencia.objects.filter(estudiante=estudiante, actividad__in=actividades)
    }
    items = []
    for a in actividades:
        disp, msg = a.estado_disponibilidad()
        items.append({'actividad': a, 'intento': hechos.get(a.id), 'disp': disp, 'msg': msg})
    return render(request, 'secuencias/mis_secuencias.html', {
        'titulo_pagina': 'Ordenar Secuencias', 'items': items,
    })


def _actividad_para_estudiante(pk, estudiante):
    return get_object_or_404(
        SecuenciaActividad, pk=pk, institucion=estudiante.institucion,
        curso__grado=estudiante.grado_actual, estado=SecuenciaActividad.Estado.PUBLICADO,
    )


@login_required
def resolver(request, pk):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None:
        raise PermissionDenied

    act = _actividad_para_estudiante(pk, estudiante)
    intento = IntentoSecuencia.objects.filter(actividad=act, estudiante=estudiante).first()
    if intento and intento.completado:
        return redirect('secuencias:resultado', pk=act.pk)

    disp, msg = act.estado_disponibilidad()
    if disp != 'disponible':
        messages.warning(request, msg)
        return redirect('secuencias:mis_secuencias')

    items = list(act.items.all())
    # Se barajan en el cliente; aquí van sin revelar la posición correcta.
    tarjetas = [{
        'id': it.id,
        'imagen': it.imagen.url if it.imagen else '',
        'texto': it.texto or '',
    } for it in items]

    if request.method == 'POST':
        # arreglo = lista de item_ids en el orden de las casillas (slot 1..N)
        try:
            arreglo = json.loads(request.POST.get('arreglo') or '[]')
        except (ValueError, TypeError):
            arreglo = []
        ids_validos = {it.id for it in items}
        pos_correcta = {it.id: it.posicion_correcta for it in items}
        total = len(items)
        aciertos = 0
        respuestas = {}
        for slot, item_id in enumerate(arreglo, start=1):
            try:
                item_id = int(item_id)
            except (TypeError, ValueError):
                continue
            if item_id not in ids_validos:
                continue
            respuestas[str(slot)] = item_id
            if pos_correcta.get(item_id) == slot:
                aciertos += 1
        porcentaje = (Decimal(aciertos) / Decimal(total) * 100).quantize(Decimal('0.01')) if total else Decimal(0)
        puntaje = (porcentaje / 100 * act.nota_maxima).quantize(Decimal('0.01'))

        with transaction.atomic():
            IntentoSecuencia.objects.update_or_create(
                actividad=act, estudiante=estudiante,
                defaults={
                    'institucion': act.institucion, 'completado': True,
                    'aciertos': aciertos, 'total': total,
                    'porcentaje': porcentaje, 'puntaje': puntaje,
                    'respuestas': respuestas, 'fin': timezone.now(),
                },
            )
            _registrar_calificacion(act, estudiante, puntaje, aciertos, total)
        messages.success(request, "¡Listo! Aquí está tu resultado.")
        return redirect('secuencias:resultado', pk=act.pk)

    return render(request, 'secuencias/resolver.html', {
        'titulo_pagina': act.titulo, 'actividad': act,
        'tarjetas_json': tarjetas, 'total': len(items),
    })


def _registrar_calificacion(act, estudiante, puntaje, aciertos, total):
    if not act.actividad_calificable_id:
        return
    from gestion_academica.models import Calificacion
    Calificacion.objects.update_or_create(
        estudiante=estudiante,
        actividad_calificable=act.actividad_calificable,
        institucion=act.institucion,
        defaults={
            'valor_numerico': puntaje,
            'observaciones': f"Ordenar secuencia autocorregida: {aciertos}/{total} en su lugar.",
        },
    )


@login_required
def resultado(request, pk):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None:
        raise PermissionDenied
    act = get_object_or_404(SecuenciaActividad, pk=pk, institucion=estudiante.institucion)
    intento = get_object_or_404(IntentoSecuencia, actividad=act, estudiante=estudiante, completado=True)
    return render(request, 'secuencias/resultado.html', {
        'titulo_pagina': f'Resultado: {act.titulo}', 'actividad': act, 'intento': intento,
    })
