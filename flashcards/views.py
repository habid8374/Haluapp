"""Vistas del módulo Flash Cards (actividad calificable por curso)."""
import json
import unicodedata
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

from .models import IntentoFlashcard, MazoFlashcard, TarjetaFlashcard

MAX_IMAGEN = 2 * 1024 * 1024   # 2 MB
MAX_AUDIO = 3 * 1024 * 1024    # 3 MB
MIN_TARJETAS = 3
MAX_TARJETAS = 30


def _normalizar(texto):
    """Mayúsculas, sin tildes (conserva Ñ), solo letras/números/espacios simples."""
    texto = (texto or '').strip().upper()
    salida = []
    for ch in texto:
        if ch == 'Ñ':
            salida.append('Ñ')
            continue
        base = ''.join(c for c in unicodedata.normalize('NFD', ch)
                       if unicodedata.category(c) != 'Mn')
        if base.isalnum() or base.isspace():
            salida.append(base)
    return ' '.join(''.join(salida).split())


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


def _leer_tarjetas(request):
    """Lee filas indexadas del formulario. Devuelve (tarjetas, error)."""
    indices = []
    for i in request.POST.getlist('fila'):
        if i.isdigit() and i not in indices:
            indices.append(i)
    tarjetas = []
    for i in indices:
        pista = (request.POST.get(f'pista_{i}') or '').strip()[:300]
        respuesta = (request.POST.get(f'respuesta_{i}') or '').strip()[:80]
        imagen = request.FILES.get(f'imagen_{i}')
        audio = request.FILES.get(f'audio_{i}')
        if not any([pista, respuesta, imagen, audio]):
            continue  # fila vacía
        if not respuesta:
            return None, "Cada tarjeta necesita su respuesta correcta."
        if not pista and not imagen:
            return None, "Cada tarjeta necesita una imagen o una descripción/pista."
        if imagen and not _imagen_valida(imagen):
            return None, "Cada imagen debe pesar máximo 2 MB y ser un archivo de imagen."
        if audio and not _audio_valido(audio):
            return None, "Cada audio debe pesar máximo 3 MB."
        tarjetas.append({'pista': pista, 'respuesta': respuesta, 'imagen': imagen, 'audio': audio})
        if len(tarjetas) > MAX_TARJETAS:
            return None, f"Máximo {MAX_TARJETAS} tarjetas por mazo."
    return tarjetas, None


# ── Docente / Coordinador ────────────────────────────────────────────────────

@login_required
def lista(request):
    _solo_docente_coord(request.user)
    mazos = _scope(MazoFlashcard.objects.all(), request.user).select_related(
        'curso__materia', 'curso__grado'
    ).prefetch_related('tarjetas', 'intentos')
    if (getattr(request.user, 'rol', '') or '') == 'docente' and not request.user.is_superuser:
        docente = getattr(request.user, 'docente', None)
        mazos = mazos.filter(curso__docentes_asignados=docente) if docente else mazos.none()
    return render(request, 'flashcards/lista.html', {
        'titulo_pagina': 'Flash Cards',
        'mazos': mazos,
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

        tarjetas, error = _leer_tarjetas(request)
        if not titulo or not curso or not tipo:
            messages.error(request, "Completa el título, el curso y la categoría.")
        elif error:
            messages.error(request, error)
        elif tarjetas is None or len(tarjetas) < MIN_TARJETAS:
            messages.error(request, f"Agrega al menos {MIN_TARJETAS} tarjetas completas.")
        else:
            with transaction.atomic():
                mazo = MazoFlashcard.objects.create(
                    institucion=curso.institucion, curso=curso, titulo=titulo,
                    instrucciones=instrucciones, tipo_actividad=tipo,
                    nota_maxima=nota_maxima, creado_por=request.user,
                    fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
                )
                for n, t in enumerate(tarjetas, start=1):
                    TarjetaFlashcard.objects.create(mazo=mazo, orden=n, **t)
            messages.success(request, "Mazo creado. Revísalo y publícalo para los estudiantes.")
            return redirect('flashcards:detalle', pk=mazo.pk)

    return render(request, 'flashcards/form.html', {
        'titulo_pagina': 'Nuevo mazo de flash cards',
        'cursos': cursos, 'tipos': tipos,
    })


@login_required
def detalle(request, pk):
    _solo_docente_coord(request.user)
    mazo = get_object_or_404(
        _scope(MazoFlashcard.objects.all(), request.user).select_related('curso__materia', 'curso__grado'),
        pk=pk,
    )
    from gestion_academica.models import TipoActividad
    tipos = TipoActividad.objects.filter(institucion=mazo.institucion)
    return render(request, 'flashcards/detalle.html', {
        'titulo_pagina': mazo.titulo,
        'mazo': mazo,
        'tarjetas': mazo.tarjetas.all(),
        'MIN_TARJETAS': MIN_TARJETAS,
        'tipos': tipos,
    })


@require_POST
@login_required
def editar_datos(request, pk):
    from gestion_academica.models import TipoActividad
    _solo_docente_coord(request.user)
    mazo = get_object_or_404(_scope(MazoFlashcard.objects.all(), request.user), pk=pk)
    titulo = (request.POST.get('titulo') or '').strip()
    if not titulo:
        messages.error(request, "El título no puede quedar vacío.")
        return redirect('flashcards:detalle', pk=mazo.pk)
    mazo.titulo = titulo
    mazo.instrucciones = (request.POST.get('instrucciones') or '').strip()
    try:
        mazo.nota_maxima = Decimal(request.POST.get('nota_maxima') or mazo.nota_maxima)
    except Exception:
        pass
    tipo_id = request.POST.get('tipo_actividad')
    if tipo_id:
        mazo.tipo_actividad = get_object_or_404(TipoActividad, pk=tipo_id, institucion=mazo.institucion)
    mazo.save(update_fields=['titulo', 'instrucciones', 'nota_maxima', 'tipo_actividad'])
    if mazo.actividad_calificable_id:
        act = mazo.actividad_calificable
        act.titulo = mazo.titulo
        act.tipo_actividad = mazo.tipo_actividad
        act.descripcion = mazo.instrucciones or None
        act.save(update_fields=['titulo', 'tipo_actividad', 'descripcion'])
    messages.success(request, "Datos actualizados.")
    return redirect('flashcards:detalle', pk=mazo.pk)


@require_POST
@login_required
def editar_tarjeta(request, pk, tarjeta_pk):
    _solo_docente_coord(request.user)
    mazo = get_object_or_404(_scope(MazoFlashcard.objects.all(), request.user), pk=pk)
    tarjeta = get_object_or_404(TarjetaFlashcard, pk=tarjeta_pk, mazo=mazo)
    respuesta = (request.POST.get('respuesta') or '').strip()[:80]
    pista = (request.POST.get('pista') or '').strip()[:300]
    if not respuesta:
        messages.error(request, "La respuesta no puede quedar vacía.")
        return redirect('flashcards:detalle', pk=mazo.pk)
    imagen = request.FILES.get('imagen')
    if imagen and not _imagen_valida(imagen):
        messages.error(request, "La imagen debe pesar máximo 2 MB y ser un archivo de imagen.")
        return redirect('flashcards:detalle', pk=mazo.pk)
    audio = request.FILES.get('audio')
    if audio and not _audio_valido(audio):
        messages.error(request, "El audio debe pesar máximo 3 MB.")
        return redirect('flashcards:detalle', pk=mazo.pk)
    tarjeta.respuesta = respuesta
    tarjeta.pista = pista
    if imagen:
        tarjeta.imagen = imagen
    elif request.POST.get('quitar_imagen') == 'on':
        tarjeta.imagen = None
    if audio:
        tarjeta.audio = audio
    elif request.POST.get('quitar_audio') == 'on':
        tarjeta.audio = None
    if not tarjeta.pista and not tarjeta.imagen:
        messages.error(request, "Cada tarjeta necesita una imagen o una descripción/pista.")
        return redirect('flashcards:detalle', pk=mazo.pk)
    tarjeta.save()
    messages.success(request, "Tarjeta actualizada.")
    return redirect('flashcards:detalle', pk=mazo.pk)


@require_POST
@login_required
def agregar_tarjeta(request, pk):
    _solo_docente_coord(request.user)
    mazo = get_object_or_404(_scope(MazoFlashcard.objects.all(), request.user), pk=pk)
    tarjetas, error = _leer_tarjetas(request)
    if error:
        messages.error(request, error)
    elif not tarjetas:
        messages.error(request, "La tarjeta está incompleta: necesita respuesta y una imagen o pista.")
    elif mazo.tarjetas.count() + len(tarjetas) > MAX_TARJETAS:
        messages.error(request, f"Máximo {MAX_TARJETAS} tarjetas por mazo.")
    else:
        ultimo = mazo.tarjetas.order_by('-orden').first()
        base = (ultimo.orden if ultimo else 0)
        for n, t in enumerate(tarjetas, start=1):
            TarjetaFlashcard.objects.create(mazo=mazo, orden=base + n, **t)
        messages.success(request, "Tarjeta agregada.")
    return redirect('flashcards:detalle', pk=mazo.pk)


@require_POST
@login_required
def eliminar_tarjeta(request, pk, tarjeta_pk):
    _solo_docente_coord(request.user)
    mazo = get_object_or_404(_scope(MazoFlashcard.objects.all(), request.user), pk=pk)
    tarjeta = get_object_or_404(TarjetaFlashcard, pk=tarjeta_pk, mazo=mazo)
    tarjeta.delete()
    messages.success(request, "Tarjeta eliminada.")
    return redirect('flashcards:detalle', pk=mazo.pk)


@require_POST
@login_required
def publicar(request, pk):
    _solo_docente_coord(request.user)
    mazo = get_object_or_404(_scope(MazoFlashcard.objects.all(), request.user), pk=pk)
    if mazo.tarjetas.count() < MIN_TARJETAS:
        messages.error(request, f"Necesitas al menos {MIN_TARJETAS} tarjetas para publicar.")
        return redirect('flashcards:detalle', pk=mazo.pk)
    from gestion_academica.models import ActividadCalificable
    with transaction.atomic():
        if not mazo.actividad_calificable:
            act = ActividadCalificable.objects.create(
                curso=mazo.curso, tipo_actividad=mazo.tipo_actividad,
                titulo=mazo.titulo, descripcion=mazo.instrucciones or None,
                institucion=mazo.institucion, fecha_publicacion=timezone.localdate(),
            )
            mazo.actividad_calificable = act
        mazo.estado = MazoFlashcard.Estado.PUBLICADO
        mazo.save(update_fields=['actividad_calificable', 'estado'])
    messages.success(request, "¡Mazo publicado! Ya aparece a los estudiantes del curso.")
    return redirect('flashcards:detalle', pk=mazo.pk)


@require_POST
@login_required
def cerrar(request, pk):
    _solo_docente_coord(request.user)
    mazo = get_object_or_404(_scope(MazoFlashcard.objects.all(), request.user), pk=pk)
    mazo.estado = MazoFlashcard.Estado.CERRADO
    mazo.fecha_cierre = timezone.now()
    mazo.save(update_fields=['estado', 'fecha_cierre'])
    messages.success(request, "Mazo cerrado.")
    return redirect('flashcards:detalle', pk=mazo.pk)


@require_POST
@login_required
def editar_fechas(request, pk):
    _solo_docente_coord(request.user)
    mazo = get_object_or_404(_scope(MazoFlashcard.objects.all(), request.user), pk=pk)
    mazo.fecha_inicio = _parse_dt(request.POST.get('fecha_inicio'))
    mazo.fecha_fin = _parse_dt(request.POST.get('fecha_fin'))
    mazo.save(update_fields=['fecha_inicio', 'fecha_fin'])
    messages.success(request, "Fechas actualizadas.")
    return redirect('flashcards:detalle', pk=mazo.pk)


@require_POST
@login_required
def eliminar(request, pk):
    _solo_docente_coord(request.user)
    mazo = get_object_or_404(_scope(MazoFlashcard.objects.all(), request.user), pk=pk)
    mazo.delete()
    messages.success(request, "Mazo eliminado.")
    return redirect('flashcards:lista')


@login_required
def resultados(request, pk):
    _solo_docente_coord(request.user)
    mazo = get_object_or_404(
        _scope(MazoFlashcard.objects.all(), request.user).select_related('curso__grado'), pk=pk,
    )
    intentos = mazo.intentos.select_related('estudiante__usuario').order_by(
        '-porcentaje', 'estudiante__usuario__first_name')
    return render(request, 'flashcards/resultados.html', {
        'titulo_pagina': f'Resultados: {mazo.titulo}',
        'mazo': mazo,
        'intentos': intentos,
    })


# ── Estudiante ───────────────────────────────────────────────────────────────

def _estudiante(user):
    return getattr(user, 'estudiante', None)


@login_required
def mis_mazos(request):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None or not estudiante.grado_actual_id:
        return render(request, 'flashcards/mis_mazos.html', {'titulo_pagina': 'Flash Cards', 'items': []})

    mazos = MazoFlashcard.objects.filter(
        institucion=estudiante.institucion,
        curso__grado=estudiante.grado_actual,
        estado=MazoFlashcard.Estado.PUBLICADO,
    ).select_related('curso__materia').order_by('-creado_en')
    hechos = {
        i.mazo_id: i for i in
        IntentoFlashcard.objects.filter(estudiante=estudiante, mazo__in=mazos)
    }
    items = []
    for m in mazos:
        disp, msg = m.estado_disponibilidad()
        items.append({'mazo': m, 'intento': hechos.get(m.id), 'disp': disp, 'msg': msg})
    return render(request, 'flashcards/mis_mazos.html', {
        'titulo_pagina': 'Flash Cards', 'items': items,
    })


def _mazo_para_estudiante(pk, estudiante):
    return get_object_or_404(
        MazoFlashcard, pk=pk, institucion=estudiante.institucion,
        curso__grado=estudiante.grado_actual, estado=MazoFlashcard.Estado.PUBLICADO,
    )


@login_required
def resolver(request, pk):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None:
        raise PermissionDenied

    mazo = _mazo_para_estudiante(pk, estudiante)
    intento = IntentoFlashcard.objects.filter(mazo=mazo, estudiante=estudiante).first()
    if intento and intento.completado:
        return redirect('flashcards:resultado', pk=mazo.pk)

    disp, msg = mazo.estado_disponibilidad()
    if disp != 'disponible':
        messages.warning(request, msg)
        return redirect('flashcards:mis_mazos')

    if intento is None:
        intento = IntentoFlashcard.objects.create(
            mazo=mazo, institucion=mazo.institucion, estudiante=estudiante,
            total=mazo.tarjetas.count(),
        )

    # Las tarjetas van SIN la respuesta correcta (se corrige en el servidor).
    tarjetas = []
    for t in mazo.tarjetas.all():
        previo = intento.respuestas.get(str(t.id))
        tarjetas.append({
            'id': t.id,
            'imagen': t.imagen.url if t.imagen else '',
            'pista': t.pista,
            'audio': t.audio.url if t.audio else '',
            'respondida': previo is not None,
            'ok': previo.get('ok') if previo else None,
        })

    return render(request, 'flashcards/resolver.html', {
        'titulo_pagina': mazo.titulo,
        'mazo': mazo,
        'tarjetas_json': tarjetas,
        'total': len(tarjetas),
        'url_responder': reverse('flashcards:responder', args=[mazo.pk]),
        'url_resultado': reverse('flashcards:resultado', args=[mazo.pk]),
    })


@require_POST
@login_required
def responder(request, pk):
    """Endpoint AJAX: corrige UNA tarjeta en el servidor y guarda el avance."""
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None:
        raise PermissionDenied

    mazo = _mazo_para_estudiante(pk, estudiante)
    disp, _msg = mazo.estado_disponibilidad()
    if disp != 'disponible':
        return JsonResponse({'error': 'El plazo de esta actividad ya no está disponible.'}, status=403)

    try:
        datos = json.loads(request.body or '{}')
        tarjeta_id = int(datos.get('tarjeta'))
        texto = str(datos.get('respuesta') or '')[:120]
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Datos inválidos.'}, status=400)

    tarjeta = get_object_or_404(TarjetaFlashcard, pk=tarjeta_id, mazo=mazo)

    with transaction.atomic():
        intento = (
            IntentoFlashcard.objects.select_for_update()
            .filter(mazo=mazo, estudiante=estudiante).first()
        )
        if intento is None:
            intento = IntentoFlashcard.objects.create(
                mazo=mazo, institucion=mazo.institucion, estudiante=estudiante,
                total=mazo.tarjetas.count(),
            )
        if intento.completado:
            return JsonResponse({'error': 'Ya completaste esta actividad.'}, status=403)

        clave = str(tarjeta.id)
        previo = intento.respuestas.get(clave)
        if previo is None:
            correcto = _normalizar(texto) != '' and _normalizar(texto) == _normalizar(tarjeta.respuesta)
            intento.respuestas[clave] = {'r': texto, 'ok': correcto}
        else:
            correcto = previo['ok']  # ya respondida: no se cambia (1 oportunidad por tarjeta)

        total = mazo.tarjetas.count()
        terminado = len(intento.respuestas) >= total
        if terminado and not intento.completado:
            aciertos = sum(1 for v in intento.respuestas.values() if v.get('ok'))
            porcentaje = (Decimal(aciertos) / Decimal(total) * 100).quantize(Decimal('0.01')) if total else Decimal(0)
            puntaje = (porcentaje / 100 * mazo.nota_maxima).quantize(Decimal('0.01'))
            intento.completado = True
            intento.aciertos = aciertos
            intento.total = total
            intento.porcentaje = porcentaje
            intento.puntaje = puntaje
            intento.fin = timezone.now()
            _registrar_calificacion(mazo, estudiante, puntaje, aciertos, total)
        intento.save()

    return JsonResponse({
        'correcto': correcto,
        'respuesta_correcta': tarjeta.respuesta,
        'terminado': terminado,
    })


def _registrar_calificacion(mazo, estudiante, puntaje, aciertos, total):
    if not mazo.actividad_calificable_id:
        return
    from gestion_academica.models import Calificacion
    Calificacion.objects.update_or_create(
        estudiante=estudiante,
        actividad_calificable=mazo.actividad_calificable,
        institucion=mazo.institucion,
        defaults={
            'valor_numerico': puntaje,
            'observaciones': f"Flash cards autocorregidas: {aciertos}/{total} correctas.",
        },
    )


@login_required
def resultado(request, pk):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None:
        raise PermissionDenied
    mazo = get_object_or_404(MazoFlashcard, pk=pk, institucion=estudiante.institucion)
    intento = get_object_or_404(IntentoFlashcard, mazo=mazo, estudiante=estudiante, completado=True)
    return render(request, 'flashcards/resultado.html', {
        'titulo_pagina': f'Resultado: {mazo.titulo}',
        'mazo': mazo,
        'intento': intento,
    })
