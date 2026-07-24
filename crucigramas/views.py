"""Vistas del módulo de Crucigramas (actividad calificable por curso)."""
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from .layout import generar_layout, normalizar
from .models import Crucigrama, IntentoCrucigrama, PalabraCrucigrama

MAX_IMAGEN = 2 * 1024 * 1024  # 2 MB


def _imagen_valida(f):
    return f.size <= MAX_IMAGEN and (getattr(f, 'content_type', '') or '').startswith('image/')


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
            'imagen': p.imagen.url if p.imagen else '',
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
        'titulo_pagina': _('Crucigramas'),
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
        fecha_inicio = _parse_dt(request.POST.get('fecha_inicio'))
        fecha_fin = _parse_dt(request.POST.get('fecha_fin'))

        # Los inputs de archivo vacíos no generan entrada en FILES, así que no
        # se pueden alinear por índice con listas paralelas (getlist). Se usa
        # un índice de fila explícito: respuesta_<i>, pista_<i>, imagen_<i>.
        indices = []
        for i in request.POST.getlist('fila'):
            if i.isdigit() and i not in indices:
                indices.append(i)

        error_imagen = False
        palabras_validas = []
        for i in indices:
            r = (request.POST.get(f'respuesta_{i}') or '').strip()
            p = (request.POST.get(f'pista_{i}') or '').strip()
            img = request.FILES.get(f'imagen_{i}')
            if not r or not p or len(normalizar(r)) < 2:
                continue
            if img and not _imagen_valida(img):
                error_imagen = True
                continue
            palabras_validas.append((r, p, img))

        if not titulo or not curso or not tipo:
            messages.error(request, _("Completa el título, el curso y la categoría."))
        elif error_imagen:
            messages.error(request, _("Cada imagen debe pesar máximo 2 MB y ser un archivo de imagen."))
        elif len(palabras_validas) < 3:
            messages.error(request, _("Agrega al menos 3 palabras con su pista (de 2 letras o más)."))
        else:
            with transaction.atomic():
                cruc = Crucigrama.objects.create(
                    institucion=curso.institucion, curso=curso, titulo=titulo,
                    instrucciones=instrucciones, tipo_actividad=tipo,
                    nota_maxima=nota_maxima, creado_por=request.user,
                    fecha_inicio=fecha_inicio, fecha_fin=fecha_fin,
                )
                for i, (r, p, img) in enumerate(palabras_validas, start=1):
                    PalabraCrucigrama.objects.create(
                        crucigrama=cruc, respuesta=r, pista=p, imagen=img, orden=i,
                    )
            messages.success(request, _("Crucigrama creado. Revísalo y publícalo para que los estudiantes lo resuelvan."))
            return redirect('crucigramas:detalle', pk=cruc.pk)

    return render(request, 'crucigramas/form.html', {
        'titulo_pagina': _('Nuevo crucigrama'),
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
    from gestion_academica.models import TipoActividad
    tipos = TipoActividad.objects.filter(institucion=cruc.institucion)
    return render(request, 'crucigramas/detalle.html', {
        'titulo_pagina': cruc.titulo,
        'crucigrama': cruc,
        'palabras': cruc.palabras.all(),
        'grilla': grilla, 'horizontales': horizontales, 'verticales': verticales,
        'tipos': tipos,
    })


@require_POST
@login_required
def publicar(request, pk):
    _solo_docente_coord(request.user)
    cruc = get_object_or_404(_scope(Crucigrama.objects.all(), request.user), pk=pk)
    palabras = list(cruc.palabras.all())
    if len(palabras) < 3:
        messages.error(request, _("Necesitas al menos 3 palabras para publicar."))
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
    messages.success(request, _("¡Crucigrama publicado! Ya aparece a los estudiantes del curso."))
    return redirect('crucigramas:detalle', pk=cruc.pk)


@require_POST
@login_required
def cerrar(request, pk):
    _solo_docente_coord(request.user)
    cruc = get_object_or_404(_scope(Crucigrama.objects.all(), request.user), pk=pk)
    cruc.estado = Crucigrama.Estado.CERRADO
    cruc.fecha_cierre = timezone.now()
    cruc.save(update_fields=['estado', 'fecha_cierre'])
    messages.success(request, _("Crucigrama cerrado. Los estudiantes ya no pueden resolverlo."))
    return redirect('crucigramas:detalle', pk=cruc.pk)


def _regenerar_layout(cruc):
    """Recalcula la cuadrícula (tras editar palabras en un crucigrama publicado)."""
    palabras = list(cruc.palabras.all())
    if len(palabras) < 3:
        return
    placements, filas, columnas = generar_layout(
        [{'id': p.id, 'respuesta': p.respuesta} for p in palabras]
    )
    by_id = {pl['id']: pl for pl in placements}
    for p in palabras:
        pl = by_id.get(p.id)
        if pl:
            p.fila, p.columna = pl['fila'], pl['columna']
            p.direccion, p.numero = pl['direccion'], pl['numero']
            p.save(update_fields=['fila', 'columna', 'direccion', 'numero'])
    cruc.filas, cruc.columnas = filas, columnas
    cruc.save(update_fields=['filas', 'columnas'])


@require_POST
@login_required
def editar_datos(request, pk):
    _solo_docente_coord(request.user)
    from gestion_academica.models import TipoActividad
    cruc = get_object_or_404(_scope(Crucigrama.objects.all(), request.user), pk=pk)
    titulo = (request.POST.get('titulo') or '').strip()
    if not titulo:
        messages.error(request, _("El título no puede quedar vacío."))
        return redirect('crucigramas:detalle', pk=cruc.pk)
    cruc.titulo = titulo
    cruc.instrucciones = (request.POST.get('instrucciones') or '').strip()
    try:
        cruc.nota_maxima = Decimal(request.POST.get('nota_maxima') or cruc.nota_maxima)
    except Exception:
        pass
    tipo_id = request.POST.get('tipo_actividad')
    if tipo_id:
        cruc.tipo_actividad = get_object_or_404(TipoActividad, pk=tipo_id, institucion=cruc.institucion)
    cruc.save(update_fields=['titulo', 'instrucciones', 'nota_maxima', 'tipo_actividad'])
    if cruc.actividad_calificable_id:
        act = cruc.actividad_calificable
        act.titulo = cruc.titulo
        act.tipo_actividad = cruc.tipo_actividad
        act.descripcion = cruc.instrucciones or None
        act.save(update_fields=['titulo', 'tipo_actividad', 'descripcion'])
    messages.success(request, _("Datos actualizados."))
    return redirect('crucigramas:detalle', pk=cruc.pk)


@require_POST
@login_required
def agregar_palabra(request, pk):
    _solo_docente_coord(request.user)
    cruc = get_object_or_404(_scope(Crucigrama.objects.all(), request.user), pk=pk)
    respuesta = (request.POST.get('respuesta') or '').strip()
    pista = (request.POST.get('pista') or '').strip()
    if not respuesta or not pista or len(normalizar(respuesta)) < 2:
        messages.error(request, _("Escribe la palabra (2 letras o más) y su pista."))
        return redirect('crucigramas:detalle', pk=cruc.pk)
    imagen = request.FILES.get('imagen')
    if imagen and not _imagen_valida(imagen):
        messages.error(request, _("La imagen debe pesar máximo 2 MB y ser un archivo de imagen."))
        return redirect('crucigramas:detalle', pk=cruc.pk)
    ultimo = cruc.palabras.order_by('-orden').first()
    PalabraCrucigrama.objects.create(
        crucigrama=cruc, respuesta=respuesta, pista=pista, imagen=imagen,
        orden=(ultimo.orden + 1) if ultimo else 1,
    )
    if cruc.estado == Crucigrama.Estado.PUBLICADO:
        _regenerar_layout(cruc)
    messages.success(request, _("Palabra agregada."))
    return redirect('crucigramas:detalle', pk=cruc.pk)


@require_POST
@login_required
def editar_palabra(request, pk, palabra_pk):
    _solo_docente_coord(request.user)
    cruc = get_object_or_404(_scope(Crucigrama.objects.all(), request.user), pk=pk)
    palabra = get_object_or_404(PalabraCrucigrama, pk=palabra_pk, crucigrama=cruc)
    respuesta = (request.POST.get('respuesta') or '').strip()
    pista = (request.POST.get('pista') or '').strip()
    if not respuesta or not pista or len(normalizar(respuesta)) < 2:
        messages.error(request, _("Escribe la palabra (2 letras o más) y su pista."))
        return redirect('crucigramas:detalle', pk=cruc.pk)
    imagen = request.FILES.get('imagen')
    if imagen:
        if not _imagen_valida(imagen):
            messages.error(request, _("La imagen debe pesar máximo 2 MB y ser un archivo de imagen."))
            return redirect('crucigramas:detalle', pk=cruc.pk)
        palabra.imagen = imagen
    elif request.POST.get('quitar_imagen') == 'on':
        palabra.imagen = None
    palabra.respuesta = respuesta
    palabra.pista = pista
    palabra.save()
    if cruc.estado == Crucigrama.Estado.PUBLICADO:
        _regenerar_layout(cruc)
    messages.success(request, _("Palabra actualizada."))
    return redirect('crucigramas:detalle', pk=cruc.pk)


@require_POST
@login_required
def eliminar_palabra(request, pk, palabra_pk):
    _solo_docente_coord(request.user)
    cruc = get_object_or_404(_scope(Crucigrama.objects.all(), request.user), pk=pk)
    palabra = get_object_or_404(PalabraCrucigrama, pk=palabra_pk, crucigrama=cruc)
    palabra.delete()
    if cruc.estado == Crucigrama.Estado.PUBLICADO:
        _regenerar_layout(cruc)
    messages.success(request, _("Palabra eliminada."))
    return redirect('crucigramas:detalle', pk=cruc.pk)


@require_POST
@login_required
def editar_fechas(request, pk):
    _solo_docente_coord(request.user)
    cruc = get_object_or_404(_scope(Crucigrama.objects.all(), request.user), pk=pk)
    cruc.fecha_inicio = _parse_dt(request.POST.get('fecha_inicio'))
    cruc.fecha_fin = _parse_dt(request.POST.get('fecha_fin'))
    cruc.save(update_fields=['fecha_inicio', 'fecha_fin'])
    messages.success(request, _("Fechas actualizadas."))
    return redirect('crucigramas:detalle', pk=cruc.pk)


@require_POST
@login_required
def eliminar(request, pk):
    _solo_docente_coord(request.user)
    cruc = get_object_or_404(_scope(Crucigrama.objects.all(), request.user), pk=pk)
    cruc.delete()
    messages.success(request, _("Crucigrama eliminado."))
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
        'titulo_pagina': _('Resultados: %(cruc_titulo)s') % {'cruc_titulo': cruc.titulo},
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
            'titulo_pagina': _('Crucigramas'), 'items': [],
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
    items = []
    for c in crucigramas:
        disp, msg = c.estado_disponibilidad()
        items.append({'crucigrama': c, 'intento': hechos.get(c.id), 'disp': disp, 'msg': msg})
    return render(request, 'crucigramas/mis_crucigramas.html', {
        'titulo_pagina': _('Crucigramas'),
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

    disp, msg = cruc.estado_disponibilidad()
    if disp != 'disponible':
        messages.warning(request, msg)
        return redirect('crucigramas:mis_crucigramas')

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
        messages.success(request, _("¡Enviado! Aquí está tu resultado."))
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
        'titulo_pagina': _('Resultado: %(cruc_titulo)s') % {'cruc_titulo': cruc.titulo},
        'crucigrama': cruc,
        'intento': intento,
    })
