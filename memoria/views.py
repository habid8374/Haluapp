"""Vistas del Juego de Memoria (actividad calificable por curso)."""
import random
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

from .models import IntentoMemoria, JuegoMemoria, ParejaMemoria

MAX_IMAGEN = 2 * 1024 * 1024   # 2 MB
MAX_AUDIO = 3 * 1024 * 1024    # 3 MB
MIN_PAREJAS = 3
MAX_PAREJAS = 20


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


def _imagen_valida(f):
    return f.size <= MAX_IMAGEN and (getattr(f, 'content_type', '') or '').startswith('image/')


def _audio_valido(f):
    ct = getattr(f, 'content_type', '') or ''
    # MediaRecorder graba audio/webm; algunos navegadores lo reportan video/webm.
    return f.size <= MAX_AUDIO and (ct.startswith('audio/') or ct == 'video/webm')


def _leer_parejas(request):
    """Lee las filas indexadas del formulario. Devuelve (parejas, error).
    Cada pareja: dict con texto/imagen/audio de las tarjetas A y B."""
    indices = []
    for i in request.POST.getlist('fila'):
        if i.isdigit() and i not in indices:
            indices.append(i)
    parejas = []
    for i in indices:
        def carta(lado):
            texto = (request.POST.get(f'texto_{lado}_{i}') or '').strip()[:60]
            imagen = request.FILES.get(f'imagen_{lado}_{i}')
            audio = request.FILES.get(f'audio_{lado}_{i}')
            return texto, imagen, audio

        ta, ia, aa = carta('a')
        tb, ib, ab = carta('b')
        if not any([ta, ia, aa, tb, ib, ab]):
            continue  # fila vacía
        if (not ta and not ia) or (not tb and not ib):
            return None, "Cada tarjeta de una pareja necesita al menos una imagen o un texto."
        for img in (ia, ib):
            if img and not _imagen_valida(img):
                return None, "Cada imagen debe pesar máximo 2 MB y ser un archivo de imagen."
        for aud in (aa, ab):
            if aud and not _audio_valido(aud):
                return None, "Cada audio debe pesar máximo 3 MB."
        parejas.append({
            'texto_a': ta, 'imagen_a': ia, 'audio_a': aa,
            'texto_b': tb, 'imagen_b': ib, 'audio_b': ab,
        })
        if len(parejas) > MAX_PAREJAS:
            return None, f"Máximo {MAX_PAREJAS} parejas por juego."
    return parejas, None


# ── Docente / Coordinador ────────────────────────────────────────────────────

@login_required
def lista(request):
    _solo_docente_coord(request.user)
    juegos = _scope(JuegoMemoria.objects.all(), request.user).select_related(
        'curso__materia', 'curso__grado'
    ).prefetch_related('parejas', 'intentos')
    if (getattr(request.user, 'rol', '') or '') == 'docente' and not request.user.is_superuser:
        docente = getattr(request.user, 'docente', None)
        juegos = juegos.filter(curso__docentes_asignados=docente) if docente else juegos.none()
    return render(request, 'memoria/lista.html', {
        'titulo_pagina': 'Juegos de Memoria',
        'juegos': juegos,
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
        modo_nota = request.POST.get('modo_nota')
        if modo_nota not in JuegoMemoria.ModoNota.values:
            modo_nota = JuegoMemoria.ModoNota.COMPLETAR
        try:
            nota_maxima = Decimal(request.POST.get('nota_maxima') or '5')
        except Exception:
            nota_maxima = Decimal('5')

        curso = get_object_or_404(cursos, pk=curso_id) if curso_id else None
        tipo = get_object_or_404(tipos, pk=tipo_id) if tipo_id else None
        fecha_inicio = _parse_dt(request.POST.get('fecha_inicio'))
        fecha_fin = _parse_dt(request.POST.get('fecha_fin'))

        parejas, error = _leer_parejas(request)
        if not titulo or not curso or not tipo:
            messages.error(request, "Completa el título, el curso y la categoría.")
        elif error:
            messages.error(request, error)
        elif parejas is None or len(parejas) < MIN_PAREJAS:
            messages.error(request, f"Agrega al menos {MIN_PAREJAS} parejas completas.")
        else:
            with transaction.atomic():
                juego = JuegoMemoria.objects.create(
                    institucion=curso.institucion, curso=curso, titulo=titulo,
                    instrucciones=instrucciones, tipo_actividad=tipo,
                    nota_maxima=nota_maxima, modo_nota=modo_nota,
                    fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
                    creado_por=request.user,
                )
                for n, p in enumerate(parejas, start=1):
                    ParejaMemoria.objects.create(juego=juego, orden=n, **p)
            messages.success(request, "Juego creado. Revísalo y publícalo para los estudiantes.")
            return redirect('memoria:detalle', pk=juego.pk)

    return render(request, 'memoria/form.html', {
        'titulo_pagina': 'Nuevo juego de memoria',
        'cursos': cursos, 'tipos': tipos,
        'MODOS': JuegoMemoria.ModoNota.choices,
    })


@login_required
def detalle(request, pk):
    _solo_docente_coord(request.user)
    juego = get_object_or_404(
        _scope(JuegoMemoria.objects.all(), request.user).select_related('curso__materia', 'curso__grado'),
        pk=pk,
    )
    from gestion_academica.models import TipoActividad
    tipos = TipoActividad.objects.filter(institucion=juego.institucion)
    return render(request, 'memoria/detalle.html', {
        'titulo_pagina': juego.titulo,
        'juego': juego,
        'parejas': juego.parejas.all(),
        'MIN_PAREJAS': MIN_PAREJAS,
        'tipos': tipos,
        'MODOS': JuegoMemoria.ModoNota.choices,
    })


@require_POST
@login_required
def editar_datos(request, pk):
    from gestion_academica.models import TipoActividad
    _solo_docente_coord(request.user)
    juego = get_object_or_404(_scope(JuegoMemoria.objects.all(), request.user), pk=pk)
    titulo = (request.POST.get('titulo') or '').strip()
    if not titulo:
        messages.error(request, "El título no puede quedar vacío.")
        return redirect('memoria:detalle', pk=juego.pk)
    juego.titulo = titulo
    juego.instrucciones = (request.POST.get('instrucciones') or '').strip()
    modo = request.POST.get('modo_nota')
    if modo in JuegoMemoria.ModoNota.values:
        juego.modo_nota = modo
    try:
        juego.nota_maxima = Decimal(request.POST.get('nota_maxima') or juego.nota_maxima)
    except Exception:
        pass
    tipo_id = request.POST.get('tipo_actividad')
    if tipo_id:
        juego.tipo_actividad = get_object_or_404(TipoActividad, pk=tipo_id, institucion=juego.institucion)
    juego.save(update_fields=['titulo', 'instrucciones', 'modo_nota', 'nota_maxima', 'tipo_actividad'])
    if juego.actividad_calificable_id:
        act = juego.actividad_calificable
        act.titulo = juego.titulo
        act.tipo_actividad = juego.tipo_actividad
        act.descripcion = juego.instrucciones or None
        act.save(update_fields=['titulo', 'tipo_actividad', 'descripcion'])
    messages.success(request, "Datos actualizados.")
    return redirect('memoria:detalle', pk=juego.pk)


@require_POST
@login_required
def editar_pareja(request, pk, pareja_pk):
    _solo_docente_coord(request.user)
    juego = get_object_or_404(_scope(JuegoMemoria.objects.all(), request.user), pk=pk)
    pareja = get_object_or_404(ParejaMemoria, pk=pareja_pk, juego=juego)
    for lado in ('a', 'b'):
        texto = (request.POST.get(f'texto_{lado}') or '').strip()[:60]
        setattr(pareja, f'texto_{lado}', texto)
        imagen = request.FILES.get(f'imagen_{lado}')
        if imagen:
            if not _imagen_valida(imagen):
                messages.error(request, "Cada imagen debe pesar máximo 2 MB.")
                return redirect('memoria:detalle', pk=juego.pk)
            setattr(pareja, f'imagen_{lado}', imagen)
        elif request.POST.get(f'quitar_imagen_{lado}') == 'on':
            setattr(pareja, f'imagen_{lado}', None)
        audio = request.FILES.get(f'audio_{lado}')
        if audio:
            if not _audio_valido(audio):
                messages.error(request, "Cada audio debe pesar máximo 3 MB.")
                return redirect('memoria:detalle', pk=juego.pk)
            setattr(pareja, f'audio_{lado}', audio)
        elif request.POST.get(f'quitar_audio_{lado}') == 'on':
            setattr(pareja, f'audio_{lado}', None)
    # Cada tarjeta de la pareja necesita imagen o texto.
    if (not pareja.texto_a and not pareja.imagen_a) or (not pareja.texto_b and not pareja.imagen_b):
        messages.error(request, "Cada tarjeta de la pareja necesita una imagen o un texto.")
        return redirect('memoria:detalle', pk=juego.pk)
    pareja.save()
    messages.success(request, "Pareja actualizada.")
    return redirect('memoria:detalle', pk=juego.pk)


@require_POST
@login_required
def agregar_pareja(request, pk):
    _solo_docente_coord(request.user)
    juego = get_object_or_404(_scope(JuegoMemoria.objects.all(), request.user), pk=pk)
    parejas, error = _leer_parejas(request)
    if error:
        messages.error(request, error)
    elif not parejas:
        messages.error(request, "La pareja está incompleta: cada tarjeta necesita imagen o texto.")
    elif juego.parejas.count() + len(parejas) > MAX_PAREJAS:
        messages.error(request, f"Máximo {MAX_PAREJAS} parejas por juego.")
    else:
        ultimo = juego.parejas.order_by('-orden').first()
        base = (ultimo.orden if ultimo else 0)
        for n, p in enumerate(parejas, start=1):
            ParejaMemoria.objects.create(juego=juego, orden=base + n, **p)
        messages.success(request, "Pareja agregada.")
    return redirect('memoria:detalle', pk=juego.pk)


@require_POST
@login_required
def eliminar_pareja(request, pk, pareja_pk):
    _solo_docente_coord(request.user)
    juego = get_object_or_404(_scope(JuegoMemoria.objects.all(), request.user), pk=pk)
    pareja = get_object_or_404(ParejaMemoria, pk=pareja_pk, juego=juego)
    pareja.delete()
    messages.success(request, "Pareja eliminada.")
    return redirect('memoria:detalle', pk=juego.pk)


@require_POST
@login_required
def publicar(request, pk):
    _solo_docente_coord(request.user)
    juego = get_object_or_404(_scope(JuegoMemoria.objects.all(), request.user), pk=pk)
    if juego.parejas.count() < MIN_PAREJAS:
        messages.error(request, f"Necesitas al menos {MIN_PAREJAS} parejas para publicar.")
        return redirect('memoria:detalle', pk=juego.pk)
    from gestion_academica.models import ActividadCalificable
    with transaction.atomic():
        if not juego.actividad_calificable:
            act = ActividadCalificable.objects.create(
                curso=juego.curso, tipo_actividad=juego.tipo_actividad,
                titulo=juego.titulo, descripcion=juego.instrucciones or None,
                institucion=juego.institucion, fecha_publicacion=timezone.localdate(),
            )
            juego.actividad_calificable = act
        juego.estado = JuegoMemoria.Estado.PUBLICADO
        juego.save(update_fields=['actividad_calificable', 'estado'])
    messages.success(request, "¡Juego publicado! Ya aparece a los estudiantes del curso.")
    return redirect('memoria:detalle', pk=juego.pk)


@require_POST
@login_required
def cerrar(request, pk):
    _solo_docente_coord(request.user)
    juego = get_object_or_404(_scope(JuegoMemoria.objects.all(), request.user), pk=pk)
    juego.estado = JuegoMemoria.Estado.CERRADO
    juego.fecha_cierre = timezone.now()
    juego.save(update_fields=['estado', 'fecha_cierre'])
    messages.success(request, "Juego cerrado.")
    return redirect('memoria:detalle', pk=juego.pk)


@require_POST
@login_required
def editar_fechas(request, pk):
    _solo_docente_coord(request.user)
    juego = get_object_or_404(_scope(JuegoMemoria.objects.all(), request.user), pk=pk)
    juego.fecha_inicio = _parse_dt(request.POST.get('fecha_inicio'))
    juego.fecha_fin = _parse_dt(request.POST.get('fecha_fin'))
    juego.save(update_fields=['fecha_inicio', 'fecha_fin'])
    messages.success(request, "Fechas actualizadas.")
    return redirect('memoria:detalle', pk=juego.pk)


@require_POST
@login_required
def eliminar(request, pk):
    _solo_docente_coord(request.user)
    juego = get_object_or_404(_scope(JuegoMemoria.objects.all(), request.user), pk=pk)
    juego.delete()
    messages.success(request, "Juego eliminado.")
    return redirect('memoria:lista')


@login_required
def resultados(request, pk):
    _solo_docente_coord(request.user)
    juego = get_object_or_404(
        _scope(JuegoMemoria.objects.all(), request.user).select_related('curso__grado'), pk=pk,
    )
    intentos = juego.intentos.select_related('estudiante__usuario').order_by(
        '-puntaje', 'movimientos')
    return render(request, 'memoria/resultados.html', {
        'titulo_pagina': f'Resultados: {juego.titulo}',
        'juego': juego,
        'intentos': intentos,
    })


# ── Estudiante ───────────────────────────────────────────────────────────────

def _estudiante(user):
    return getattr(user, 'estudiante', None)


@login_required
def mis_juegos(request):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None or not estudiante.grado_actual_id:
        return render(request, 'memoria/mis_juegos.html', {'titulo_pagina': 'Juegos de Memoria', 'items': []})

    juegos = JuegoMemoria.objects.filter(
        institucion=estudiante.institucion,
        curso__grado=estudiante.grado_actual,
        estado=JuegoMemoria.Estado.PUBLICADO,
    ).select_related('curso__materia').order_by('-creado_en')
    hechos = {
        i.juego_id: i for i in
        IntentoMemoria.objects.filter(estudiante=estudiante, juego__in=juegos)
    }
    items = []
    for j in juegos:
        disp, msg = j.estado_disponibilidad()
        items.append({'juego': j, 'intento': hechos.get(j.id), 'disp': disp, 'msg': msg})
    return render(request, 'memoria/mis_juegos.html', {
        'titulo_pagina': 'Juegos de Memoria', 'items': items,
    })


@login_required
def jugar(request, pk):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None:
        raise PermissionDenied

    juego = get_object_or_404(
        JuegoMemoria, pk=pk, institucion=estudiante.institucion,
        curso__grado=estudiante.grado_actual, estado=JuegoMemoria.Estado.PUBLICADO,
    )
    intento = IntentoMemoria.objects.filter(juego=juego, estudiante=estudiante).first()
    if intento and intento.completado:
        return redirect('memoria:resultado', pk=juego.pk)

    disp, msg = juego.estado_disponibilidad()
    if disp != 'disponible':
        messages.warning(request, msg)
        return redirect('memoria:mis_juegos')

    parejas = list(juego.parejas.all())

    if request.method == 'POST':
        total = len(parejas)
        try:
            movimientos = int(request.POST.get('movimientos') or 0)
        except (TypeError, ValueError):
            movimientos = 0
        movimientos = max(total, min(movimientos, 9999))  # nunca menos que el mínimo posible

        if juego.modo_nota == JuegoMemoria.ModoNota.COMPLETAR:
            porcentaje = Decimal(100)
        else:
            # Terminar garantiza 60%; el resto premia la eficiencia.
            # Con hasta 2 volteos por pareja se conserva el 100%.
            eficiencia = min(Decimal(1), Decimal(2 * total) / Decimal(movimientos))
            porcentaje = (Decimal(60) + Decimal(40) * eficiencia).quantize(Decimal('0.01'))
        puntaje = (porcentaje / 100 * juego.nota_maxima).quantize(Decimal('0.01'))

        with transaction.atomic():
            IntentoMemoria.objects.update_or_create(
                juego=juego, estudiante=estudiante,
                defaults={
                    'institucion': juego.institucion, 'completado': True,
                    'movimientos': movimientos, 'parejas_total': total,
                    'porcentaje': porcentaje, 'puntaje': puntaje,
                    'fin': timezone.now(),
                },
            )
            _registrar_calificacion(juego, estudiante, puntaje, movimientos, total)
        messages.success(request, "¡Muy bien! Aquí está tu resultado.")
        return redirect('memoria:resultado', pk=juego.pk)

    # Construir el mazo: 2 tarjetas por pareja, barajadas.
    cartas = []
    for p in parejas:
        for lado in ('a', 'b'):
            imagen = getattr(p, f'imagen_{lado}')
            audio = getattr(p, f'audio_{lado}')
            cartas.append({
                'pareja': p.id,
                'imagen': imagen.url if imagen else '',
                'texto': getattr(p, f'texto_{lado}') or '',
                'audio': audio.url if audio else '',
            })
    random.shuffle(cartas)

    return render(request, 'memoria/jugar.html', {
        'titulo_pagina': juego.titulo,
        'juego': juego,
        'cartas': cartas,
        'total_parejas': len(parejas),
    })


def _registrar_calificacion(juego, estudiante, puntaje, movimientos, total):
    if not juego.actividad_calificable_id:
        return
    from gestion_academica.models import Calificacion
    Calificacion.objects.update_or_create(
        estudiante=estudiante,
        actividad_calificable=juego.actividad_calificable,
        institucion=juego.institucion,
        defaults={
            'valor_numerico': puntaje,
            'observaciones': f"Memoria autocorregida: {total} parejas en {movimientos} intentos.",
        },
    )


@login_required
def resultado(request, pk):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None:
        raise PermissionDenied
    juego = get_object_or_404(JuegoMemoria, pk=pk, institucion=estudiante.institucion)
    intento = get_object_or_404(IntentoMemoria, juego=juego, estudiante=estudiante)
    return render(request, 'memoria/resultado.html', {
        'titulo_pagina': f'Resultado: {juego.titulo}',
        'juego': juego,
        'intento': intento,
    })
