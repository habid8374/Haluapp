"""Vistas de la Pizarra de Trazado de Letras — actividad por curso."""
import base64
import binascii
import json
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from .models import (
    IntentoTrazado, PlantillaTrazado, TableroTrazado, TrazoEstudiante,
)

MAX_AUDIO = 3 * 1024 * 1024
MAX_TRAZO = 1 * 1024 * 1024   # 1 MB por dibujo PNG
MIN_PLANTILLAS = 1
MAX_PLANTILLAS = 20


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


def _audio_valido(f):
    ct = getattr(f, 'content_type', '') or ''
    return f.size <= MAX_AUDIO and (ct.startswith('audio/') or ct == 'video/webm')


def _leer_plantillas(request):
    indices = []
    for i in request.POST.getlist('fila'):
        if i.isdigit() and i not in indices:
            indices.append(i)
    plantillas = []
    for i in indices:
        texto = (request.POST.get(f'texto_{i}') or '').strip()[:20]
        audio = request.FILES.get(f'audio_{i}')
        if not texto:
            continue
        if audio and not _audio_valido(audio):
            return None, "Cada audio debe pesar máximo 3 MB."
        plantillas.append({'texto': texto, 'audio': audio})
        if len(plantillas) > MAX_PLANTILLAS:
            return None, f"Máximo {MAX_PLANTILLAS} letras/palabras por tablero."
    return plantillas, None


# ── Docente / Coordinador ────────────────────────────────────────────────────

@login_required
def lista(request):
    _solo_docente_coord(request.user)
    tableros = _scope(TableroTrazado.objects.all(), request.user).select_related(
        'curso__materia', 'curso__grado'
    ).prefetch_related('plantillas', 'intentos')
    if (getattr(request.user, 'rol', '') or '') == 'docente' and not request.user.is_superuser:
        docente = getattr(request.user, 'docente', None)
        tableros = tableros.filter(curso__docentes_asignados=docente) if docente else tableros.none()
    return render(request, 'trazado/lista.html', {
        'titulo_pagina': 'Trazado de Letras', 'tableros': tableros,
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

        plantillas, error = _leer_plantillas(request)
        if not titulo or not curso or not tipo:
            messages.error(request, "Completa el título, el curso y la categoría.")
        elif error:
            messages.error(request, error)
        elif plantillas is None or len(plantillas) < MIN_PLANTILLAS:
            messages.error(request, "Agrega al menos una letra o palabra para trazar.")
        else:
            with transaction.atomic():
                tablero = TableroTrazado.objects.create(
                    institucion=curso.institucion, curso=curso, titulo=titulo,
                    instrucciones=instrucciones, tipo_actividad=tipo,
                    nota_maxima=nota_maxima, creado_por=request.user,
                    fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
                )
                for n, p in enumerate(plantillas, start=1):
                    PlantillaTrazado.objects.create(
                        tablero=tablero, orden=n, texto=p['texto'], audio=p['audio'],
                    )
            messages.success(request, "Tablero creado. Revísalo y publícalo para los estudiantes.")
            return redirect('trazado:detalle', pk=tablero.pk)

    return render(request, 'trazado/form.html', {
        'titulo_pagina': 'Nuevo tablero de trazado', 'cursos': cursos, 'tipos': tipos,
    })


@login_required
def detalle(request, pk):
    _solo_docente_coord(request.user)
    tablero = get_object_or_404(
        _scope(TableroTrazado.objects.all(), request.user).select_related('curso__materia', 'curso__grado'),
        pk=pk,
    )
    return render(request, 'trazado/detalle.html', {
        'titulo_pagina': tablero.titulo, 'tablero': tablero,
        'plantillas': tablero.plantillas.all(),
    })


@require_POST
@login_required
def publicar(request, pk):
    _solo_docente_coord(request.user)
    tablero = get_object_or_404(_scope(TableroTrazado.objects.all(), request.user), pk=pk)
    if tablero.plantillas.count() < MIN_PLANTILLAS:
        messages.error(request, "Necesitas al menos una plantilla para publicar.")
        return redirect('trazado:detalle', pk=tablero.pk)
    from gestion_academica.models import ActividadCalificable
    with transaction.atomic():
        if not tablero.actividad_calificable:
            ac = ActividadCalificable.objects.create(
                curso=tablero.curso, tipo_actividad=tablero.tipo_actividad,
                titulo=tablero.titulo, descripcion=tablero.instrucciones or None,
                institucion=tablero.institucion, fecha_publicacion=timezone.localdate(),
            )
            tablero.actividad_calificable = ac
        tablero.estado = TableroTrazado.Estado.PUBLICADO
        tablero.save(update_fields=['actividad_calificable', 'estado'])
    messages.success(request, "¡Tablero publicado! Ya aparece a los estudiantes del curso.")
    return redirect('trazado:detalle', pk=tablero.pk)


@require_POST
@login_required
def cerrar(request, pk):
    _solo_docente_coord(request.user)
    tablero = get_object_or_404(_scope(TableroTrazado.objects.all(), request.user), pk=pk)
    tablero.estado = TableroTrazado.Estado.CERRADO
    tablero.fecha_cierre = timezone.now()
    tablero.save(update_fields=['estado', 'fecha_cierre'])
    messages.success(request, "Tablero cerrado.")
    return redirect('trazado:detalle', pk=tablero.pk)


@require_POST
@login_required
def editar_fechas(request, pk):
    _solo_docente_coord(request.user)
    tablero = get_object_or_404(_scope(TableroTrazado.objects.all(), request.user), pk=pk)
    tablero.fecha_inicio = _parse_dt(request.POST.get('fecha_inicio'))
    tablero.fecha_fin = _parse_dt(request.POST.get('fecha_fin'))
    tablero.save(update_fields=['fecha_inicio', 'fecha_fin'])
    messages.success(request, "Fechas actualizadas.")
    return redirect('trazado:detalle', pk=tablero.pk)


@require_POST
@login_required
def eliminar(request, pk):
    _solo_docente_coord(request.user)
    tablero = get_object_or_404(_scope(TableroTrazado.objects.all(), request.user), pk=pk)
    tablero.delete()
    messages.success(request, "Tablero eliminado.")
    return redirect('trazado:lista')


@login_required
def resultados(request, pk):
    _solo_docente_coord(request.user)
    tablero = get_object_or_404(
        _scope(TableroTrazado.objects.all(), request.user).select_related('curso__grado'), pk=pk,
    )
    intentos = tablero.intentos.select_related('estudiante__usuario').prefetch_related(
        'trazos__plantilla').order_by('estudiante__usuario__first_name')
    return render(request, 'trazado/resultados.html', {
        'titulo_pagina': f'Resultados: {tablero.titulo}', 'tablero': tablero, 'intentos': intentos,
    })


# ── Estudiante ───────────────────────────────────────────────────────────────

def _estudiante(user):
    return getattr(user, 'estudiante', None)


@login_required
def mis_tableros(request):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None or not estudiante.grado_actual_id:
        return render(request, 'trazado/mis_tableros.html', {'titulo_pagina': 'Trazado de Letras', 'items': []})

    tableros = TableroTrazado.objects.filter(
        institucion=estudiante.institucion,
        curso__grado=estudiante.grado_actual,
        estado=TableroTrazado.Estado.PUBLICADO,
    ).select_related('curso__materia').order_by('-creado_en')
    hechos = {
        i.tablero_id: i for i in
        IntentoTrazado.objects.filter(estudiante=estudiante, tablero__in=tableros)
    }
    items = []
    for t in tableros:
        disp, msg = t.estado_disponibilidad()
        items.append({'tablero': t, 'intento': hechos.get(t.id), 'disp': disp, 'msg': msg})
    return render(request, 'trazado/mis_tableros.html', {
        'titulo_pagina': 'Trazado de Letras', 'items': items,
    })


def _tablero_para_estudiante(pk, estudiante):
    return get_object_or_404(
        TableroTrazado, pk=pk, institucion=estudiante.institucion,
        curso__grado=estudiante.grado_actual, estado=TableroTrazado.Estado.PUBLICADO,
    )


@login_required
def resolver(request, pk):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None:
        raise PermissionDenied

    tablero = _tablero_para_estudiante(pk, estudiante)
    intento = IntentoTrazado.objects.filter(tablero=tablero, estudiante=estudiante).first()
    if intento and intento.completado:
        return redirect('trazado:resultado', pk=tablero.pk)

    disp, msg = tablero.estado_disponibilidad()
    if disp != 'disponible':
        messages.warning(request, msg)
        return redirect('trazado:mis_tableros')

    if intento is None:
        intento = IntentoTrazado.objects.create(
            tablero=tablero, institucion=tablero.institucion, estudiante=estudiante,
            total=tablero.plantillas.count(),
        )

    hechas_ids = set(intento.trazos.values_list('plantilla_id', flat=True))
    plantillas = [{
        'id': p.id, 'texto': p.texto,
        'audio': p.audio.url if p.audio else '',
        'hecha': p.id in hechas_ids,
    } for p in tablero.plantillas.all()]

    return render(request, 'trazado/resolver.html', {
        'titulo_pagina': tablero.titulo, 'tablero': tablero,
        'plantillas_json': plantillas,
        'url_guardar': reverse('trazado:guardar_trazo', args=[tablero.pk]),
        'url_resultado': reverse('trazado:resultado', args=[tablero.pk]),
    })


@require_POST
@login_required
def guardar_trazo(request, pk):
    """AJAX: recibe el dibujo (base64) de UNA plantilla y lo guarda."""
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None:
        raise PermissionDenied

    tablero = _tablero_para_estudiante(pk, estudiante)
    disp, _m = tablero.estado_disponibilidad()
    if disp != 'disponible':
        return JsonResponse({'error': 'Esta actividad ya no está disponible.'}, status=403)

    try:
        datos = json.loads(request.body or '{}')
        plantilla_id = int(datos.get('plantilla'))
        data_url = str(datos.get('imagen') or '')
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Datos inválidos.'}, status=400)

    if ';base64,' not in data_url or not data_url.startswith('data:image/'):
        return JsonResponse({'error': 'Imagen inválida.'}, status=400)
    cabecera, b64 = data_url.split(';base64,', 1)
    try:
        binario = base64.b64decode(b64)
    except (binascii.Error, ValueError):
        return JsonResponse({'error': 'Imagen inválida.'}, status=400)
    if len(binario) > MAX_TRAZO:
        return JsonResponse({'error': 'El dibujo es demasiado grande.'}, status=400)

    plantilla = get_object_or_404(PlantillaTrazado, pk=plantilla_id, tablero=tablero)

    with transaction.atomic():
        intento = (
            IntentoTrazado.objects.select_for_update()
            .filter(tablero=tablero, estudiante=estudiante).first()
        )
        if intento is None:
            intento = IntentoTrazado.objects.create(
                tablero=tablero, institucion=tablero.institucion, estudiante=estudiante,
                total=tablero.plantillas.count(),
            )
        if intento.completado:
            return JsonResponse({'error': 'Ya completaste esta actividad.'}, status=403)

        trazo, _created = TrazoEstudiante.objects.get_or_create(
            intento=intento, plantilla=plantilla,
        )
        trazo.imagen.save(f'trazo_{intento.id}_{plantilla.id}.png', ContentFile(binario), save=True)

        total = tablero.plantillas.count()
        hechas = intento.trazos.count()
        intento.hechas = hechas
        terminado = hechas >= total
        if terminado and not intento.completado:
            intento.completado = True
            intento.total = total
            intento.porcentaje = Decimal(100)
            intento.puntaje = tablero.nota_maxima
            intento.fin = timezone.now()
            _registrar_calificacion(tablero, estudiante, tablero.nota_maxima, hechas, total)
        intento.save()

    return JsonResponse({'ok': True, 'hechas': hechas, 'total': total, 'terminado': terminado})


def _registrar_calificacion(tablero, estudiante, puntaje, hechas, total):
    if not tablero.actividad_calificable_id:
        return
    from gestion_academica.models import Calificacion
    Calificacion.objects.update_or_create(
        estudiante=estudiante,
        actividad_calificable=tablero.actividad_calificable,
        institucion=tablero.institucion,
        defaults={
            'valor_numerico': puntaje,
            'observaciones': f"Trazado completado: {hechas}/{total} plantillas. Revisa los dibujos para ajustar la nota si lo deseas.",
        },
    )


@login_required
def resultado(request, pk):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None:
        raise PermissionDenied
    tablero = get_object_or_404(TableroTrazado, pk=pk, institucion=estudiante.institucion)
    intento = get_object_or_404(IntentoTrazado, tablero=tablero, estudiante=estudiante, completado=True)
    return render(request, 'trazado/resultado.html', {
        'titulo_pagina': f'Resultado: {tablero.titulo}', 'tablero': tablero, 'intento': intento,
    })
