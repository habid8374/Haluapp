"""Vistas del módulo de Crucigramas (actividad calificable por curso)."""
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .layout import generar_layout, normalizar
from .models import Crucigrama, IntentoCrucigrama, PalabraCrucigrama


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
    rol = getattr(user, 'rol', '') or ''
    if rol == 'docente':
        docente = getattr(user, 'docente', None)
        qs = qs.filter(docentes_asignados=docente) if docente else qs.none()
    return qs.order_by('periodo_academico', 'grado', 'materia')


def _grid_data(cruc, con_letras=False):
    """Construye la grilla 2D y las listas de pistas para plantillas/JS."""
    palabras = list(cruc.palabras.all())
    numero_por_celda = {}
    activos = {}
    celdas_por_palabra = []
    for p in palabras:
        if p.fila is None or p.direccion is None:
            continue
        w = normalizar(p.respuesta)
        celdas = []
        for k in range(len(w)):
            rc = (p.fila, p.columna + k) if p.direccion == 'H' else (p.fila + k, p.columna)
            celdas.append(rc)
            activos[rc] = w[k]
        if p.numero:
            numero_por_celda[(p.fila, p.columna)] = p.numero
        celdas_por_palabra.append({
            'id': p.id, 'numero': p.numero, 'direccion': p.direccion,
            'pista': p.pista, 'longitud': len(w),
            'celdas': [[r, c] for (r, c) in celdas],
        })

    grilla = []
    for r in range(cruc.filas):
        fila = []
        for c in range(cruc.columnas):
            if (r, c) in activos:
                fila.append({
                    'r': r, 'c': c,
                    'numero': numero_por_celda.get((r, c)),
                    'letra': activos[(r, c)] if con_letras else '',
                })
            else:
                fila.append(None)
        grilla.append(fila)

    horizontales = sorted([cp for cp in celdas_por_palabra if cp['direccion'] == 'H'],
                          key=lambda x: x['numero'] or 0)
    verticales = sorted([cp for cp in celdas_por_palabra if cp['direccion'] == 'V'],
                        key=lambda x: x['numero'] or 0)
    return grilla, celdas_por_palabra, horizontales, verticales


# ── Docente / Coordinador ────────────────────────────────────────────────────

@login_required
def lista(request):
    _solo_docente_coord(request.user)
    crucigramas = _scope(Crucigrama.objects.all(), request.user).select_related(
        'curso__materia', 'curso__grado'
    ).prefetch_related('palabras', 'intentos')
    rol = getattr(request.user, 'rol', '') or ''
    if rol == 'docente' and not request.user.is_superuser:
        docente = getattr(request.user, 'docente', None)
        crucigramas = crucigramas.filter(curso__docentes_asignados=docente) if docente else crucigramas.none()
    return render(request, 'crucigramas/lista.html', {
        'titulo_pagina': 'Crucigramas',
        'crucigramas': crucigramas,
    })


@login_required
def crear(request):
    _solo_docente_coord(request.user)
    from gestion_academica.models import Curso, TipoActividad
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

        respuestas = request.POST.getlist('respuesta')
        pistas = request.POST.getlist('pista')
        palabras_validas = [
            (r.strip(), p.strip()) for r, p in zip(respuestas, pistas)
            if r.strip() and p.strip() and len(normalizar(r)) >= 2
        ]

        if not titulo or not curso or not tipo:
            messages.error(request, "Completa el título, el curso y la categoría.")
        elif len(palabras_validas) < 3:
            messages.error(request, "Agrega al menos 3 palabras con su pista (de 2 letras o más).")
        else:
            with transaction.atomic():
                cruc = Crucigrama.objects.create(
                    institucion=curso.institucion, curso=curso, titulo=titulo,
                    instrucciones=instrucciones, tipo_actividad=tipo,
                    nota_maxima=nota_maxima, creado_por=request.user,
                )
                PalabraCrucigrama.objects.bulk_create([
                    PalabraCrucigrama(crucigrama=cruc, respuesta=r, pista=p, orden=i)
                    for i, (r, p) in enumerate(palabras_validas, start=1)
                ])
            messages.success(request, "Crucigrama creado. Revísalo y publícalo para que los estudiantes lo resuelvan.")
            return redirect('crucigramas:detalle', pk=cruc.pk)

    return render(request, 'crucigramas/form.html', {
        'titulo_pagina': 'Nuevo crucigrama',
        'cursos': cursos, 'tipos': tipos, 'crucigrama': None,
    })


@login_required
def detalle(request, pk):
    _solo_docente_coord(request.user)
    cruc = get_object_or_404(
        _scope(Crucigrama.objects.all(), request.user).select_related('curso__materia', 'curso__grado'),
        pk=pk,
    )
    grilla = celdas = horizontales = verticales = None
    if cruc.estado != Crucigrama.Estado.BORRADOR:
        grilla, celdas, horizontales, verticales = _grid_data(cruc, con_letras=True)
    return render(request, 'crucigramas/detalle.html', {
        'titulo_pagina': cruc.titulo,
        'crucigrama': cruc,
        'palabras': cruc.palabras.all(),
        'grilla': grilla, 'horizontales': horizontales, 'verticales': verticales,
    })


@require_POST
@login_required
def publicar(request, pk):
    _solo_docente_coord(request.user)
    cruc = get_object_or_404(_scope(Crucigrama.objects.all(), request.user), pk=pk)
    palabras = list(cruc.palabras.all())
    if len(palabras) < 3:
        messages.error(request, "Necesitas al menos 3 palabras para publicar.")
        return redirect('crucigramas:detalle', pk=cruc.pk)

    from gestion_academica.models import ActividadCalificable
    placements, filas, columnas = generar_layout(
        [{'id': p.id, 'respuesta': p.respuesta} for p in palabras]
    )
    by_id = {pl['id']: pl for pl in placements}
    with transaction.atomic():
        for p in palabras:
            pl = by_id.get(p.id)
            if pl:
                p.fila, p.columna = pl['fila'], pl['columna']
                p.direccion, p.numero = pl['direccion'], pl['numero']
                p.save(update_fields=['fila', 'columna', 'direccion', 'numero'])
        cruc.filas, cruc.columnas = filas, columnas
        if not cruc.actividad_calificable:
            act = ActividadCalificable.objects.create(
                curso=cruc.curso, tipo_actividad=cruc.tipo_actividad,
                titulo=cruc.titulo, descripcion=cruc.instrucciones or None,
                institucion=cruc.institucion, fecha_publicacion=timezone.localdate(),
            )
            cruc.actividad_calificable = act
        cruc.estado = Crucigrama.Estado.PUBLICADO
        cruc.save(update_fields=['filas', 'columnas', 'actividad_calificable', 'estado'])
    messages.success(request, "¡Crucigrama publicado! Ya aparece a los estudiantes del curso.")
    return redirect('crucigramas:detalle', pk=cruc.pk)


@require_POST
@login_required
def cerrar(request, pk):
    _solo_docente_coord(request.user)
    cruc = get_object_or_404(_scope(Crucigrama.objects.all(), request.user), pk=pk)
    cruc.estado = Crucigrama.Estado.CERRADO
    cruc.fecha_cierre = timezone.now()
    cruc.save(update_fields=['estado', 'fecha_cierre'])
    messages.success(request, "Crucigrama cerrado. Los estudiantes ya no pueden resolverlo.")
    return redirect('crucigramas:detalle', pk=cruc.pk)


@require_POST
@login_required
def eliminar(request, pk):
    _solo_docente_coord(request.user)
    cruc = get_object_or_404(_scope(Crucigrama.objects.all(), request.user), pk=pk)
    cruc.delete()
    messages.success(request, "Crucigrama eliminado.")
    return redirect('crucigramas:lista')


@login_required
def resultados(request, pk):
    _solo_docente_coord(request.user)
    cruc = get_object_or_404(
        _scope(Crucigrama.objects.all(), request.user).select_related('curso__grado'),
        pk=pk,
    )
    intentos = cruc.intentos.select_related('estudiante__usuario').order_by('-porcentaje', 'estudiante__usuario__first_name')
    return render(request, 'crucigramas/resultados.html', {
        'titulo_pagina': f'Resultados: {cruc.titulo}',
        'crucigrama': cruc,
        'intentos': intentos,
    })


# ── Estudiante ───────────────────────────────────────────────────────────────

def _estudiante(user):
    return getattr(user, 'estudiante', None)


@login_required
def mis_crucigramas(request):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None or not estudiante.grado_actual_id:
        return render(request, 'crucigramas/mis_crucigramas.html', {
            'titulo_pagina': 'Crucigramas', 'items': [],
        })

    crucigramas = Crucigrama.objects.filter(
        institucion=estudiante.institucion,
        curso__grado=estudiante.grado_actual,
        estado=Crucigrama.Estado.PUBLICADO,
    ).select_related('curso__materia').order_by('-creado_en')

    hechos = {
        i.crucigrama_id: i for i in
        IntentoCrucigrama.objects.filter(estudiante=estudiante, crucigrama__in=crucigramas)
    }
    items = [{'crucigrama': c, 'intento': hechos.get(c.id)} for c in crucigramas]
    return render(request, 'crucigramas/mis_crucigramas.html', {
        'titulo_pagina': 'Crucigramas',
        'items': items,
    })


@login_required
def resolver(request, pk):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None:
        raise PermissionDenied

    cruc = get_object_or_404(
        Crucigrama, pk=pk, institucion=estudiante.institucion,
        curso__grado=estudiante.grado_actual, estado=Crucigrama.Estado.PUBLICADO,
    )

    intento = IntentoCrucigrama.objects.filter(crucigrama=cruc, estudiante=estudiante).first()
    if intento and intento.completado:
        return redirect('crucigramas:resultado', pk=cruc.pk)

    if request.method == 'POST':
        palabras = list(cruc.palabras.all())
        total = len(palabras)
        aciertos = 0
        respuestas = {}
        for p in palabras:
            dada = normalizar(request.POST.get(f'palabra_{p.id}', ''))
            respuestas[str(p.id)] = dada
            if dada and dada == normalizar(p.respuesta):
                aciertos += 1
        porcentaje = (Decimal(aciertos) / Decimal(total) * 100) if total else Decimal(0)
        puntaje = (porcentaje / 100 * cruc.nota_maxima).quantize(Decimal('0.01'))

        with transaction.atomic():
            intento, _ = IntentoCrucigrama.objects.update_or_create(
                crucigrama=cruc, estudiante=estudiante,
                defaults={
                    'institucion': cruc.institucion, 'completado': True,
                    'porcentaje': porcentaje.quantize(Decimal('0.01')),
                    'puntaje': puntaje, 'aciertos': aciertos, 'total': total,
                    'respuestas': respuestas, 'fin': timezone.now(),
                },
            )
            _registrar_calificacion(cruc, estudiante, puntaje, aciertos, total)
        messages.success(request, "¡Enviado! Aquí está tu resultado.")
        return redirect('crucigramas:resultado', pk=cruc.pk)

    grilla, celdas, horizontales, verticales = _grid_data(cruc, con_letras=False)
    return render(request, 'crucigramas/resolver.html', {
        'titulo_pagina': cruc.titulo,
        'crucigrama': cruc,
        'grilla': grilla, 'celdas_json': celdas,
        'horizontales': horizontales, 'verticales': verticales,
    })


def _registrar_calificacion(cruc, estudiante, puntaje, aciertos, total):
    """Vuelca la nota del crucigrama al libro de notas."""
    if not cruc.actividad_calificable_id:
        return
    from gestion_academica.models import Calificacion
    Calificacion.objects.update_or_create(
        estudiante=estudiante,
        actividad_calificable=cruc.actividad_calificable,
        institucion=cruc.institucion,
        defaults={
            'valor_numerico': puntaje,
            'observaciones': f"Crucigrama autocorregido: {aciertos}/{total} correctas.",
        },
    )


@login_required
def resultado(request, pk):
    if not _es_estudiante(request.user):
        raise PermissionDenied
    estudiante = _estudiante(request.user)
    if estudiante is None:
        raise PermissionDenied
    cruc = get_object_or_404(Crucigrama, pk=pk, institucion=estudiante.institucion)
    intento = get_object_or_404(IntentoCrucigrama, crucigrama=cruc, estudiante=estudiante)
    return render(request, 'crucigramas/resultado.html', {
        'titulo_pagina': f'Resultado: {cruc.titulo}',
        'crucigrama': cruc,
        'intento': intento,
    })
