"""Vistas del módulo de Sopa de Letras (actividad calificable por curso)."""
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

from .layout import generar_sopa, normalizar
from .models import IntentoSopa, PalabraSopa, Sopa


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


def _grid_view(sopa, con_solucion=False):
    """Devuelve la cuadrícula como lista de filas de celdas {ch, sol}."""
    solucion = set()
    if con_solucion:
        for p in sopa.palabras.all():
            if p.fila is None:
                continue
            L = len(normalizar(p.texto))
            for i in range(L):
                solucion.add((p.fila + p.df * i, p.columna + p.dc * i))
    filas = []
    for r, row in enumerate(sopa.grid):
        celdas = [{'r': r, 'c': c, 'ch': ch, 'sol': (r, c) in solucion}
                  for c, ch in enumerate(row)]
        filas.append(celdas)
    return filas


def _palabra_de_seleccion(grid, sel, size):
    """Extrae la palabra que forma una selección (r1,c1)->(r2,c2) en la grilla."""
    try:
        r1, c1 = int(sel['r1']), int(sel['c1'])
        r2, c2 = int(sel['r2']), int(sel['c2'])
    except (KeyError, TypeError, ValueError):
        return None
    for v in (r1, c1, r2, c2):
        if v < 0 or v >= size:
            return None
    dr, dc = r2 - r1, c2 - c1
    if dr == 0 and dc == 0:
        return None
    adr, adc = abs(dr), abs(dc)
    if not (dr == 0 or dc == 0 or adr == adc):  # solo recta u horizontal/vertical/diagonal
        return None
    pasos = max(adr, adc)
    sr = (dr > 0) - (dr < 0)
    sc = (dc > 0) - (dc < 0)
    letras = ''
    for i in range(pasos + 1):
        rr, cc = r1 + sr * i, c1 + sc * i
        letras += grid[rr][cc]
    return letras


# ── Docente / Coordinador ────────────────────────────────────────────────────

@login_required
def lista(request):
    _solo_docente_coord(request.user)
    sopas = _scope(Sopa.objects.all(), request.user).select_related(
        'curso__materia', 'curso__grado'
    ).prefetch_related('palabras', 'intentos')
    if (getattr(request.user, 'rol', '') or '') == 'docente' and not request.user.is_superuser:
        docente = getattr(request.user, 'docente', None)
        sopas = sopas.filter(curso__docentes_asignados=docente) if docente else sopas.none()
    return render(request, 'sopa_letras/lista.html', {
        'titulo_pagina': 'Sopas de letras',
        'sopas': sopas,
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

        textos = request.POST.getlist('palabra')
        palabras_validas = [t.strip() for t in textos if t.strip() and len(normalizar(t)) >= 2]

        if not titulo or not curso or not tipo:
            messages.error(request, "Completa el título, el curso y la categoría.")
        elif len(palabras_validas) < 3:
            messages.error(request, "Agrega al menos 3 palabras (de 2 letras o más, sin espacios).")
        else:
            with transaction.atomic():
                sopa = Sopa.objects.create(
                    institucion=curso.institucion, curso=curso, titulo=titulo,
                    instrucciones=instrucciones, tipo_actividad=tipo,
                    nota_maxima=nota_maxima, creado_por=request.user,
                    fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
                )
                PalabraSopa.objects.bulk_create([
                    PalabraSopa(sopa=sopa, texto=t, orden=i)
                    for i, t in enumerate(palabras_validas, start=1)
                ])
            messages.success(request, "Sopa creada. Revísala y publícala para los estudiantes.")
            return redirect('sopa_letras:detalle', pk=sopa.pk)

    return render(request, 'sopa_letras/form.html', {
        'titulo_pagina': 'Nueva sopa de letras',
        'cursos': cursos, 'tipos': tipos,
    })


@login_required
def detalle(request, pk):
    _solo_docente_coord(request.user)
    sopa = get_object_or_404(
        _scope(Sopa.objects.all(), request.user).select_related('curso__materia', 'curso__grado'),
        pk=pk,
    )
    grilla = None
    if sopa.estado != Sopa.Estado.BORRADOR and sopa.grid:
        grilla = _grid_view(sopa, con_solucion=True)
    return render(request, 'sopa_letras/detalle.html', {
        'titulo_pagina': sopa.titulo,
        'sopa': sopa,
        'palabras': sopa.palabras.all(),
        'grilla': grilla,
    })


@require_POST
@login_required
def publicar(request, pk):
    _solo_docente_coord(request.user)
    sopa = get_object_or_404(_scope(Sopa.objects.all(), request.user), pk=pk)
    palabras = list(sopa.palabras.all())
    if len(palabras) < 3:
        messages.error(request, "Necesitas al menos 3 palabras para publicar.")
        return redirect('sopa_letras:detalle', pk=sopa.pk)

    from gestion_academica.models import ActividadCalificable
    grid, placements, tamano = generar_sopa(
        [{'id': p.id, 'texto': p.texto} for p in palabras]
    )
    if not grid:
        messages.error(request, "No se pudo generar la sopa. Prueba con palabras más cortas o menos palabras.")
        return redirect('sopa_letras:detalle', pk=sopa.pk)

    by_id = {pl['id']: pl for pl in placements}
    with transaction.atomic():
        for p in palabras:
            pl = by_id.get(p.id)
            if pl:
                p.fila, p.columna, p.df, p.dc = pl['fila'], pl['columna'], pl['df'], pl['dc']
                p.save(update_fields=['fila', 'columna', 'df', 'dc'])
        sopa.grid = grid
        sopa.tamano = tamano
        if not sopa.actividad_calificable:
            act = ActividadCalificable.objects.create(
                curso=sopa.curso, tipo_actividad=sopa.tipo_actividad,
                titulo=sopa.titulo, descripcion=sopa.instrucciones or None,
                institucion=sopa.institucion, fecha_publicacion=timezone.localdate(),
            )
            sopa.actividad_calificable = act
        sopa.estado = Sopa.Estado.PUBLICADO
        sopa.save(update_fields=['grid', 'tamano', 'actividad_calificable', 'estado'])
    messages.success(request, "¡Sopa publicada! Ya aparece a los estudiantes del curso.")
    return redirect('sopa_letras:detalle', pk=sopa.pk)


@require_POST
@login_required
def cerrar(request, pk):
    _solo_docente_coord(request.user)
    sopa = get_object_or_404(_scope(Sopa.objects.all(), request.user), pk=pk)
    sopa.estado = Sopa.Estado.CERRADO
    sopa.fecha_cierre = timezone.now()
    sopa.save(update_fields=['estado', 'fecha_cierre'])
    messages.success(request, "Sopa cerrada.")
    return redirect('sopa_letras:detalle', pk=sopa.pk)


@require_POST
@login_required
def editar_fechas(request, pk):
    _solo_docente_coord(request.user)
    sopa = get_object_or_404(_scope(Sopa.objects.all(), request.user), pk=pk)
    sopa.fecha_inicio = _parse_dt(request.POST.get('fecha_inicio'))
    sopa.fecha_fin = _parse_dt(request.POST.get('fecha_fin'))
    sopa.save(update_fields=['fecha_inicio', 'fecha_fin'])
    messages.success(request, "Fechas actualizadas.")
    return redirect('sopa_letras:detalle', pk=sopa.pk)


@require_POST
@login_required
def eliminar(request, pk):
    _solo_docente_coord(request.user)
    sopa = get_object_or_404(_scope(Sopa.objects.all(), request.user), pk=pk)
    sopa.delete()
    messages.success(request, "Sopa eliminada.")
    return redirect('sopa_letras:lista')


@login_required
def resultados(request, pk):
    _solo_docente_coord(request.user)
    sopa = get_object_or_404(
        _scope(Sopa.objects.all(), request.user).select_related('curso__grado'), pk=pk,
    )
    intentos = sopa.intentos.select_related('estudiante__usuario').order_by(
        '-porcentaje', 'estudiante__usuario__first_name')
    return render(request, 'sopa_letras/resultados.html', {
        'titulo_pagina': f'Resultados: {sopa.titulo}',
        'sopa': sopa,
        'intentos': intentos,
    })


# ── Estudiante ───────────────────────────────────────────────────────────────

def _estudiante(user):
    return getattr(user, 'estudiante', None)


@login_required
def mis_sopas(request):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None or not estudiante.grado_actual_id:
        return render(request, 'sopa_letras/mis_sopas.html', {'titulo_pagina': 'Sopas de letras', 'items': []})

    sopas = Sopa.objects.filter(
        institucion=estudiante.institucion,
        curso__grado=estudiante.grado_actual,
        estado=Sopa.Estado.PUBLICADO,
    ).select_related('curso__materia').order_by('-creado_en')
    hechos = {
        i.sopa_id: i for i in
        IntentoSopa.objects.filter(estudiante=estudiante, sopa__in=sopas)
    }
    items = []
    for s in sopas:
        disp, msg = s.estado_disponibilidad()
        items.append({'sopa': s, 'intento': hechos.get(s.id), 'disp': disp, 'msg': msg})
    return render(request, 'sopa_letras/mis_sopas.html', {
        'titulo_pagina': 'Sopas de letras', 'items': items,
    })


@login_required
def resolver(request, pk):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None:
        raise PermissionDenied

    sopa = get_object_or_404(
        Sopa, pk=pk, institucion=estudiante.institucion,
        curso__grado=estudiante.grado_actual, estado=Sopa.Estado.PUBLICADO,
    )
    intento = IntentoSopa.objects.filter(sopa=sopa, estudiante=estudiante).first()
    if intento and intento.completado:
        return redirect('sopa_letras:resultado', pk=sopa.pk)

    disp, msg = sopa.estado_disponibilidad()
    if disp != 'disponible':
        messages.warning(request, msg)
        return redirect('sopa_letras:mis_sopas')

    if request.method == 'POST':
        try:
            selecciones = json.loads(request.POST.get('selecciones') or '[]')
        except (ValueError, TypeError):
            selecciones = []
        if not isinstance(selecciones, list):
            selecciones = []
        selecciones = selecciones[:200]  # cota de seguridad

        objetivo = {normalizar(p.texto) for p in sopa.palabras.all()}
        total = len(objetivo)
        encontradas = set()
        for sel in selecciones:
            if not isinstance(sel, dict):
                continue
            letras = _palabra_de_seleccion(sopa.grid, sel, sopa.tamano)
            if not letras:
                continue
            w = normalizar(letras)
            for cand in (w, w[::-1]):
                if cand in objetivo:
                    encontradas.add(cand)
                    break

        n = len(encontradas & objetivo)
        porcentaje = (Decimal(n) / Decimal(total) * 100) if total else Decimal(0)
        puntaje = (porcentaje / 100 * sopa.nota_maxima).quantize(Decimal('0.01'))

        with transaction.atomic():
            IntentoSopa.objects.update_or_create(
                sopa=sopa, estudiante=estudiante,
                defaults={
                    'institucion': sopa.institucion, 'completado': True,
                    'encontradas': n, 'total': total,
                    'porcentaje': porcentaje.quantize(Decimal('0.01')),
                    'puntaje': puntaje, 'selecciones': selecciones,
                    'fin': timezone.now(),
                },
            )
            _registrar_calificacion(sopa, estudiante, puntaje, n, total)
        messages.success(request, "¡Enviado! Aquí está tu resultado.")
        return redirect('sopa_letras:resultado', pk=sopa.pk)

    grilla = _grid_view(sopa, con_solucion=False)
    pares = [{'texto': p.texto, 'norm': normalizar(p.texto)} for p in sopa.palabras.all()]
    return render(request, 'sopa_letras/resolver.html', {
        'titulo_pagina': sopa.titulo,
        'sopa': sopa,
        'grilla': grilla,
        'palabras': pares,
        'palabras_norm': [p['norm'] for p in pares],
    })


def _registrar_calificacion(sopa, estudiante, puntaje, encontradas, total):
    if not sopa.actividad_calificable_id:
        return
    from gestion_academica.models import Calificacion
    Calificacion.objects.update_or_create(
        estudiante=estudiante,
        actividad_calificable=sopa.actividad_calificable,
        institucion=sopa.institucion,
        defaults={
            'valor_numerico': puntaje,
            'observaciones': f"Sopa de letras autocorregida: {encontradas}/{total} palabras.",
        },
    )


@login_required
def resultado(request, pk):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None:
        raise PermissionDenied
    sopa = get_object_or_404(Sopa, pk=pk, institucion=estudiante.institucion)
    intento = get_object_or_404(IntentoSopa, sopa=sopa, estudiante=estudiante)
    return render(request, 'sopa_letras/resultado.html', {
        'titulo_pagina': f'Resultado: {sopa.titulo}',
        'sopa': sopa,
        'intento': intento,
    })
