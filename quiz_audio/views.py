"""Vistas del Quiz de Audio (Escucha y Elige) — actividad calificable por curso."""
import json
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from .models import IntentoQuizAudio, OpcionAudio, PreguntaAudio, QuizAudio

MAX_IMAGEN = 2 * 1024 * 1024
MAX_AUDIO = 3 * 1024 * 1024
MIN_PREGUNTAS = 2
MAX_PREGUNTAS = 15
MAX_OPCIONES = 4


def _parse_dt(valor):
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


def _imagen_valida(f):
    return f.size <= MAX_IMAGEN and (getattr(f, 'content_type', '') or '').startswith('image/')


def _audio_valido(f):
    ct = getattr(f, 'content_type', '') or ''
    return f.size <= MAX_AUDIO and (ct.startswith('audio/') or ct == 'video/webm')


def _leer_preguntas(request):
    """Lee preguntas indexadas del formulario. Devuelve (preguntas, error).
    Cada pregunta: {audio, enunciado, correcta (idx), opciones: [{imagen,texto}]}."""
    indices = []
    for i in request.POST.getlist('pregunta'):
        if i.isdigit() and i not in indices:
            indices.append(i)
    preguntas = []
    for i in indices:
        audio = request.FILES.get(f'audio_{i}')
        enunciado = (request.POST.get(f'enunciado_{i}') or '').strip()[:200]
        correcta_raw = request.POST.get(f'correcta_{i}')
        opciones = []
        for j in range(MAX_OPCIONES):
            imagen = request.FILES.get(f'img_{i}_{j}')
            texto = (request.POST.get(f'txt_{i}_{j}') or '').strip()[:60]
            if imagen or texto:
                if imagen and not _imagen_valida(imagen):
                    return None, "Cada imagen debe pesar máximo 2 MB y ser un archivo de imagen."
                opciones.append({'j': j, 'imagen': imagen, 'texto': texto})
        if not audio and not enunciado and not opciones:
            continue  # fila vacía
        if not audio:
            return None, "Cada pregunta necesita su audio."
        if not _audio_valido(audio):
            return None, "Cada audio debe pesar máximo 3 MB."
        if len(opciones) < 2:
            return None, "Cada pregunta necesita al menos 2 opciones (imagen o texto)."
        try:
            correcta = int(correcta_raw)
        except (TypeError, ValueError):
            correcta = -1
        if correcta not in [o['j'] for o in opciones]:
            return None, "Marca cuál es la opción correcta en cada pregunta."
        preguntas.append({
            'audio': audio, 'enunciado': enunciado,
            'correcta': correcta, 'opciones': opciones,
        })
        if len(preguntas) > MAX_PREGUNTAS:
            return None, f"Máximo {MAX_PREGUNTAS} preguntas por quiz."
    return preguntas, None


def _crear_preguntas(quiz, preguntas, base_orden=0):
    for n, p in enumerate(preguntas, start=base_orden + 1):
        pregunta = PreguntaAudio.objects.create(
            quiz=quiz, orden=n, audio=p['audio'], enunciado=p['enunciado'],
        )
        for k, o in enumerate(p['opciones'], start=1):
            OpcionAudio.objects.create(
                pregunta=pregunta, orden=k, imagen=o['imagen'], texto=o['texto'],
                es_correcta=(o['j'] == p['correcta']),
            )


# ── Docente / Coordinador ────────────────────────────────────────────────────

@login_required
def lista(request):
    _solo_docente_coord(request.user)
    quices = _scope(QuizAudio.objects.all(), request.user).select_related(
        'curso__materia', 'curso__grado'
    ).prefetch_related('preguntas', 'intentos')
    if (getattr(request.user, 'rol', '') or '') == 'docente' and not request.user.is_superuser:
        docente = getattr(request.user, 'docente', None)
        quices = quices.filter(curso__docentes_asignados=docente) if docente else quices.none()
    return render(request, 'quiz_audio/lista.html', {
        'titulo_pagina': 'Quiz de Audio', 'quices': quices,
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

        preguntas, error = _leer_preguntas(request)
        if not titulo or not curso or not tipo:
            messages.error(request, "Completa el título, el curso y la categoría.")
        elif error:
            messages.error(request, error)
        elif preguntas is None or len(preguntas) < MIN_PREGUNTAS:
            messages.error(request, f"Agrega al menos {MIN_PREGUNTAS} preguntas completas.")
        else:
            with transaction.atomic():
                quiz = QuizAudio.objects.create(
                    institucion=curso.institucion, curso=curso, titulo=titulo,
                    instrucciones=instrucciones, tipo_actividad=tipo,
                    nota_maxima=nota_maxima, creado_por=request.user,
                    fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
                )
                _crear_preguntas(quiz, preguntas)
            messages.success(request, "Quiz creado. Revísalo y publícalo para los estudiantes.")
            return redirect('quiz_audio:detalle', pk=quiz.pk)

    return render(request, 'quiz_audio/form.html', {
        'titulo_pagina': 'Nuevo quiz de audio', 'cursos': cursos, 'tipos': tipos,
        'RANGO_OPCIONES': range(MAX_OPCIONES),
    })


@login_required
def detalle(request, pk):
    _solo_docente_coord(request.user)
    quiz = get_object_or_404(
        _scope(QuizAudio.objects.all(), request.user).select_related('curso__materia', 'curso__grado'),
        pk=pk,
    )
    from gestion_academica.models import TipoActividad
    tipos = TipoActividad.objects.filter(institucion=quiz.institucion)
    return render(request, 'quiz_audio/detalle.html', {
        'titulo_pagina': quiz.titulo, 'quiz': quiz,
        'preguntas': quiz.preguntas.prefetch_related('opciones'),
        'MIN_PREGUNTAS': MIN_PREGUNTAS,
        'tipos': tipos,
        'RANGO_OPCIONES': range(MAX_OPCIONES),
    })


@require_POST
@login_required
def eliminar_pregunta(request, pk, pregunta_pk):
    _solo_docente_coord(request.user)
    quiz = get_object_or_404(_scope(QuizAudio.objects.all(), request.user), pk=pk)
    pregunta = get_object_or_404(PreguntaAudio, pk=pregunta_pk, quiz=quiz)
    pregunta.delete()
    messages.success(request, "Pregunta eliminada.")
    return redirect('quiz_audio:detalle', pk=quiz.pk)


@require_POST
@login_required
def editar_datos(request, pk):
    from gestion_academica.models import TipoActividad
    _solo_docente_coord(request.user)
    quiz = get_object_or_404(_scope(QuizAudio.objects.all(), request.user), pk=pk)
    titulo = (request.POST.get('titulo') or '').strip()
    if not titulo:
        messages.error(request, "El título no puede quedar vacío.")
        return redirect('quiz_audio:detalle', pk=quiz.pk)
    quiz.titulo = titulo
    quiz.instrucciones = (request.POST.get('instrucciones') or '').strip()
    try:
        quiz.nota_maxima = Decimal(request.POST.get('nota_maxima') or quiz.nota_maxima)
    except Exception:
        pass
    tipo_id = request.POST.get('tipo_actividad')
    if tipo_id:
        quiz.tipo_actividad = get_object_or_404(TipoActividad, pk=tipo_id, institucion=quiz.institucion)
    quiz.save(update_fields=['titulo', 'instrucciones', 'nota_maxima', 'tipo_actividad'])
    if quiz.actividad_calificable_id:
        act = quiz.actividad_calificable
        act.titulo = quiz.titulo
        act.tipo_actividad = quiz.tipo_actividad
        act.descripcion = quiz.instrucciones or None
        act.save(update_fields=['titulo', 'tipo_actividad', 'descripcion'])
    messages.success(request, "Datos actualizados.")
    return redirect('quiz_audio:detalle', pk=quiz.pk)


@require_POST
@login_required
def agregar_pregunta(request, pk):
    _solo_docente_coord(request.user)
    quiz = get_object_or_404(_scope(QuizAudio.objects.all(), request.user), pk=pk)
    preguntas, error = _leer_preguntas(request)
    if error:
        messages.error(request, error)
    elif not preguntas:
        messages.error(request, "La pregunta está incompleta (audio + al menos 2 opciones y marca la correcta).")
    elif quiz.preguntas.count() + len(preguntas) > MAX_PREGUNTAS:
        messages.error(request, f"Máximo {MAX_PREGUNTAS} preguntas por quiz.")
    else:
        base = quiz.preguntas.count()
        _crear_preguntas(quiz, preguntas, base_orden=base)
        messages.success(request, "Pregunta agregada.")
    return redirect('quiz_audio:detalle', pk=quiz.pk)


@require_POST
@login_required
def editar_pregunta(request, pk, pregunta_pk):
    _solo_docente_coord(request.user)
    quiz = get_object_or_404(_scope(QuizAudio.objects.all(), request.user), pk=pk)
    pregunta = get_object_or_404(PreguntaAudio, pk=pregunta_pk, quiz=quiz)
    pregunta.enunciado = (request.POST.get('enunciado') or '').strip()[:200]
    audio = request.FILES.get('audio')
    if audio:
        if not _audio_valido(audio):
            messages.error(request, "El audio debe pesar máximo 3 MB.")
            return redirect('quiz_audio:detalle', pk=quiz.pk)
        pregunta.audio = audio
    pregunta.save()
    correcta_id = request.POST.get('correcta')
    for op in pregunta.opciones.all():
        op.texto = (request.POST.get(f'optxt_{op.id}') or '').strip()[:60]
        img = request.FILES.get(f'opimg_{op.id}')
        if img:
            if not _imagen_valida(img):
                messages.error(request, "Cada imagen debe pesar máximo 2 MB.")
                return redirect('quiz_audio:detalle', pk=quiz.pk)
            op.imagen = img
        elif request.POST.get(f'opquitar_{op.id}') == 'on':
            op.imagen = None
        op.es_correcta = (str(op.id) == str(correcta_id))
        op.save()
    if not pregunta.opciones.filter(es_correcta=True).exists():
        messages.warning(request, "Ojo: no marcaste ninguna opción como correcta en esa pregunta.")
    else:
        messages.success(request, "Pregunta actualizada.")
    return redirect('quiz_audio:detalle', pk=quiz.pk)


@require_POST
@login_required
def publicar(request, pk):
    _solo_docente_coord(request.user)
    quiz = get_object_or_404(_scope(QuizAudio.objects.all(), request.user), pk=pk)
    if quiz.preguntas.count() < MIN_PREGUNTAS:
        messages.error(request, f"Necesitas al menos {MIN_PREGUNTAS} preguntas para publicar.")
        return redirect('quiz_audio:detalle', pk=quiz.pk)
    from gestion_academica.models import ActividadCalificable
    with transaction.atomic():
        if not quiz.actividad_calificable:
            act = ActividadCalificable.objects.create(
                curso=quiz.curso, tipo_actividad=quiz.tipo_actividad,
                titulo=quiz.titulo, descripcion=quiz.instrucciones or None,
                institucion=quiz.institucion, fecha_publicacion=timezone.localdate(),
            )
            quiz.actividad_calificable = act
        quiz.estado = QuizAudio.Estado.PUBLICADO
        quiz.save(update_fields=['actividad_calificable', 'estado'])
    messages.success(request, "¡Quiz publicado! Ya aparece a los estudiantes del curso.")
    return redirect('quiz_audio:detalle', pk=quiz.pk)


@require_POST
@login_required
def cerrar(request, pk):
    _solo_docente_coord(request.user)
    quiz = get_object_or_404(_scope(QuizAudio.objects.all(), request.user), pk=pk)
    quiz.estado = QuizAudio.Estado.CERRADO
    quiz.fecha_cierre = timezone.now()
    quiz.save(update_fields=['estado', 'fecha_cierre'])
    messages.success(request, "Quiz cerrado.")
    return redirect('quiz_audio:detalle', pk=quiz.pk)


@require_POST
@login_required
def editar_fechas(request, pk):
    _solo_docente_coord(request.user)
    quiz = get_object_or_404(_scope(QuizAudio.objects.all(), request.user), pk=pk)
    quiz.fecha_inicio = _parse_dt(request.POST.get('fecha_inicio'))
    quiz.fecha_fin = _parse_dt(request.POST.get('fecha_fin'))
    quiz.save(update_fields=['fecha_inicio', 'fecha_fin'])
    messages.success(request, "Fechas actualizadas.")
    return redirect('quiz_audio:detalle', pk=quiz.pk)


@require_POST
@login_required
def eliminar(request, pk):
    _solo_docente_coord(request.user)
    quiz = get_object_or_404(_scope(QuizAudio.objects.all(), request.user), pk=pk)
    quiz.delete()
    messages.success(request, "Quiz eliminado.")
    return redirect('quiz_audio:lista')


@login_required
def resultados(request, pk):
    _solo_docente_coord(request.user)
    quiz = get_object_or_404(
        _scope(QuizAudio.objects.all(), request.user).select_related('curso__grado'), pk=pk,
    )
    intentos = quiz.intentos.select_related('estudiante__usuario').order_by(
        '-porcentaje', 'estudiante__usuario__first_name')
    return render(request, 'quiz_audio/resultados.html', {
        'titulo_pagina': f'Resultados: {quiz.titulo}', 'quiz': quiz, 'intentos': intentos,
    })


# ── Estudiante ───────────────────────────────────────────────────────────────

def _estudiante(user):
    return getattr(user, 'estudiante', None)


@login_required
def mis_quices(request):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None or not estudiante.grado_actual_id:
        return render(request, 'quiz_audio/mis_quices.html', {'titulo_pagina': 'Quiz de Audio', 'items': []})

    quices = QuizAudio.objects.filter(
        institucion=estudiante.institucion,
        curso__grado=estudiante.grado_actual,
        estado=QuizAudio.Estado.PUBLICADO,
    ).select_related('curso__materia').order_by('-creado_en')
    hechos = {
        i.quiz_id: i for i in
        IntentoQuizAudio.objects.filter(estudiante=estudiante, quiz__in=quices)
    }
    items = []
    for q in quices:
        disp, msg = q.estado_disponibilidad()
        items.append({'quiz': q, 'intento': hechos.get(q.id), 'disp': disp, 'msg': msg})
    return render(request, 'quiz_audio/mis_quices.html', {
        'titulo_pagina': 'Quiz de Audio', 'items': items,
    })


def _quiz_para_estudiante(pk, estudiante):
    return get_object_or_404(
        QuizAudio, pk=pk, institucion=estudiante.institucion,
        curso__grado=estudiante.grado_actual, estado=QuizAudio.Estado.PUBLICADO,
    )


@login_required
def resolver(request, pk):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None:
        raise PermissionDenied

    quiz = _quiz_para_estudiante(pk, estudiante)
    intento = IntentoQuizAudio.objects.filter(quiz=quiz, estudiante=estudiante).first()
    if intento and intento.completado:
        return redirect('quiz_audio:resultado', pk=quiz.pk)

    disp, msg = quiz.estado_disponibilidad()
    if disp != 'disponible':
        messages.warning(request, msg)
        return redirect('quiz_audio:mis_quices')

    if intento is None:
        intento = IntentoQuizAudio.objects.create(
            quiz=quiz, institucion=quiz.institucion, estudiante=estudiante,
            total=quiz.preguntas.count(),
        )

    # Preguntas SIN marcar cuál opción es correcta (se corrige en el servidor).
    preguntas = []
    for p in quiz.preguntas.prefetch_related('opciones'):
        if str(p.id) in intento.respuestas:
            continue  # ya respondida
        opciones = [{
            'id': o.id,
            'imagen': o.imagen.url if o.imagen else '',
            'texto': o.texto or '',
        } for o in p.opciones.all()]
        preguntas.append({
            'id': p.id, 'audio': p.audio.url if p.audio else '',
            'enunciado': p.enunciado, 'opciones': opciones,
        })

    if not preguntas:
        return redirect('quiz_audio:resultado', pk=quiz.pk)

    return render(request, 'quiz_audio/resolver.html', {
        'titulo_pagina': quiz.titulo, 'quiz': quiz,
        'preguntas_json': preguntas,
        'respondidas': intento.total - len(preguntas) if intento.total else 0,
        'total': quiz.preguntas.count(),
        'url_responder': reverse('quiz_audio:responder', args=[quiz.pk]),
        'url_resultado': reverse('quiz_audio:resultado', args=[quiz.pk]),
    })


@require_POST
@login_required
def responder(request, pk):
    """AJAX: corrige UNA pregunta en el servidor y guarda el avance."""
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None:
        raise PermissionDenied

    quiz = _quiz_para_estudiante(pk, estudiante)
    disp, _m = quiz.estado_disponibilidad()
    if disp != 'disponible':
        return JsonResponse({'error': 'Esta actividad ya no está disponible.'}, status=403)

    try:
        datos = json.loads(request.body or '{}')
        pregunta_id = int(datos.get('pregunta'))
        opcion_id = int(datos.get('opcion'))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Datos inválidos.'}, status=400)

    pregunta = get_object_or_404(PreguntaAudio, pk=pregunta_id, quiz=quiz)
    opcion = get_object_or_404(OpcionAudio, pk=opcion_id, pregunta=pregunta)
    correcta = pregunta.opciones.filter(es_correcta=True).first()

    with transaction.atomic():
        intento = (
            IntentoQuizAudio.objects.select_for_update()
            .filter(quiz=quiz, estudiante=estudiante).first()
        )
        if intento is None:
            intento = IntentoQuizAudio.objects.create(
                quiz=quiz, institucion=quiz.institucion, estudiante=estudiante,
                total=quiz.preguntas.count(),
            )
        if intento.completado:
            return JsonResponse({'error': 'Ya completaste esta actividad.'}, status=403)

        clave = str(pregunta.id)
        if clave not in intento.respuestas:
            es_ok = opcion.es_correcta
            intento.respuestas[clave] = {'op': opcion.id, 'ok': es_ok}
        else:
            es_ok = intento.respuestas[clave]['ok']

        total = quiz.preguntas.count()
        terminado = len(intento.respuestas) >= total
        if terminado and not intento.completado:
            aciertos = sum(1 for v in intento.respuestas.values() if v.get('ok'))
            porcentaje = (Decimal(aciertos) / Decimal(total) * 100).quantize(Decimal('0.01')) if total else Decimal(0)
            puntaje = (porcentaje / 100 * quiz.nota_maxima).quantize(Decimal('0.01'))
            intento.completado = True
            intento.aciertos = aciertos
            intento.total = total
            intento.porcentaje = porcentaje
            intento.puntaje = puntaje
            intento.fin = timezone.now()
            _registrar_calificacion(quiz, estudiante, puntaje, aciertos, total)
        intento.save()

    return JsonResponse({
        'correcto': es_ok,
        'opcion_correcta': correcta.id if correcta else None,
        'terminado': terminado,
    })


def _registrar_calificacion(quiz, estudiante, puntaje, aciertos, total):
    if not quiz.actividad_calificable_id:
        return
    from gestion_academica.models import Calificacion
    Calificacion.objects.update_or_create(
        estudiante=estudiante,
        actividad_calificable=quiz.actividad_calificable,
        institucion=quiz.institucion,
        defaults={
            'valor_numerico': puntaje,
            'observaciones': f"Quiz de audio autocorregido: {aciertos}/{total} correctas.",
        },
    )


@login_required
def resultado(request, pk):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None:
        raise PermissionDenied
    quiz = get_object_or_404(QuizAudio, pk=pk, institucion=estudiante.institucion)
    intento = get_object_or_404(IntentoQuizAudio, quiz=quiz, estudiante=estudiante, completado=True)
    return render(request, 'quiz_audio/resultado.html', {
        'titulo_pagina': f'Resultado: {quiz.titulo}', 'quiz': quiz, 'intento': intento,
    })
