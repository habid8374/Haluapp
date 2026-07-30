# gestion_academica/views/eventos.py
"""Cartelera de eventos institucionales + cumpleaños (calculados, no duplicados)."""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from ..models import Docente, Estudiante, EventoInstitucional


def _institucion(user):
    return getattr(user, 'institucion_asociada', None)


def _es_coordinador_o_admin(user):
    rol = getattr(user, 'rol', '') or ''
    return rol in ('coordinador', 'administrador', 'rector') or user.is_superuser


def _scope(qs, user):
    if user.is_superuser:
        return qs
    inst = _institucion(user)
    return qs.filter(institucion=inst) if inst else qs.none()


def _proxima_ocurrencia_cumple(fecha_nacimiento, hoy):
    """Próxima fecha (este año o el siguiente) en que cae ese mes/día."""
    try:
        candidata = fecha_nacimiento.replace(year=hoy.year)
    except ValueError:
        candidata = fecha_nacimiento.replace(year=hoy.year, day=28)  # 29-feb
    if candidata < hoy:
        try:
            candidata = candidata.replace(year=hoy.year + 1)
        except ValueError:
            candidata = candidata.replace(year=hoy.year + 1, day=28)
    return candidata


def _cumpleanos_proximos(institucion, dias=30):
    """Cumpleaños de estudiantes y docentes activos dentro de los próximos N
    días, calculados al vuelo desde su fecha de nacimiento — nunca se guarda
    un EventoInstitucional por persona."""
    if not institucion:
        return []
    hoy = timezone.localdate()
    limite = hoy + timedelta(days=dias)
    items = []

    estudiantes = Estudiante.objects.filter(
        institucion=institucion, activo=True, fecha_nacimiento__isnull=False,
    ).select_related('usuario')
    for est in estudiantes:
        prox = _proxima_ocurrencia_cumple(est.fecha_nacimiento, hoy)
        if hoy <= prox <= limite:
            items.append({
                'titulo': f"Cumpleaños de {est.usuario.get_full_name() or est.usuario.username}",
                'categoria': 'CUMPLEANOS', 'categoria_display': 'Cumpleaños',
                'fecha': prox, 'descripcion': 'Estudiante',
            })

    docentes = Docente.objects.filter(
        institucion=institucion, fecha_nacimiento__isnull=False,
    ).select_related('usuario')
    for doc in docentes:
        prox = _proxima_ocurrencia_cumple(doc.fecha_nacimiento, hoy)
        if hoy <= prox <= limite:
            items.append({
                'titulo': f"Cumpleaños de {doc.usuario.get_full_name() or doc.usuario.username}",
                'categoria': 'CUMPLEANOS', 'categoria_display': 'Cumpleaños',
                'fecha': prox, 'descripcion': 'Docente',
            })
    return items


@login_required
def cartelera_eventos(request):
    """Cartelera visible para todos los roles — cada quien ve los eventos
    marcados para su rol, más los cumpleaños próximos."""
    institucion = _institucion(request.user)
    rol = getattr(request.user, 'rol', '') or ''

    eventos_qs = EventoInstitucional.objects.filter(institucion=institucion, activo=True) if institucion else EventoInstitucional.objects.none()
    if rol == 'docente':
        eventos_qs = eventos_qs.filter(para_docentes=True)
    elif rol == 'estudiante':
        eventos_qs = eventos_qs.filter(para_estudiantes=True)
    elif rol == 'familiar':
        eventos_qs = eventos_qs.filter(para_familiares=True)
    elif rol in ('coordinador', 'administrador', 'rector'):
        eventos_qs = eventos_qs.filter(para_coordinadores=True)
    # superuser/otros roles: ve todos los activos de su institución (o ninguno si no tiene)

    hoy = timezone.localdate()
    limite = hoy + timedelta(days=90)
    items = []
    for ev in eventos_qs:
        prox = ev.proxima_ocurrencia(desde=hoy)
        if hoy <= prox <= limite:
            items.append({
                'titulo': ev.titulo, 'categoria': ev.categoria,
                'categoria_display': ev.get_categoria_display(),
                'fecha': prox, 'descripcion': ev.descripcion,
                'evento': ev,
            })

    items.extend(_cumpleanos_proximos(institucion, dias=90))
    items.sort(key=lambda x: x['fecha'])

    return render(request, 'gestion_academica/eventos/cartelera.html', {
        'titulo_pagina': 'Cartelera de Eventos',
        'items': items,
        'puede_administrar': _es_coordinador_o_admin(request.user),
    })


@login_required
def lista_eventos_admin(request):
    """Listado de administración (solo coordinador/administrador)."""
    if not _es_coordinador_o_admin(request.user):
        raise PermissionDenied
    eventos = _scope(EventoInstitucional.objects.all(), request.user).order_by('fecha')
    return render(request, 'gestion_academica/eventos/lista_admin.html', {
        'titulo_pagina': 'Administrar Eventos Institucionales',
        'eventos': eventos,
    })


def _guardar_desde_form(request, evento):
    evento.titulo = (request.POST.get('titulo') or '').strip()
    evento.descripcion = (request.POST.get('descripcion') or '').strip()
    evento.categoria = request.POST.get('categoria') or EventoInstitucional.Categoria.INSTITUCIONAL
    fecha = parse_date(request.POST.get('fecha') or '')
    if fecha:
        evento.fecha = fecha
    evento.recurrente_anual = request.POST.get('recurrente_anual') == 'on'
    try:
        evento.dias_aviso_previo = max(0, int(request.POST.get('dias_aviso_previo') or 3))
    except (TypeError, ValueError):
        evento.dias_aviso_previo = 3
    evento.para_docentes = request.POST.get('para_docentes') == 'on'
    evento.para_estudiantes = request.POST.get('para_estudiantes') == 'on'
    evento.para_familiares = request.POST.get('para_familiares') == 'on'
    evento.para_coordinadores = request.POST.get('para_coordinadores') == 'on'
    evento.activo = request.POST.get('activo', 'on') == 'on'
    return evento


@login_required
def crear_evento(request):
    if not _es_coordinador_o_admin(request.user):
        raise PermissionDenied
    institucion = _institucion(request.user)

    if request.method == 'POST':
        if not institucion and not request.user.is_superuser:
            messages.error(request, "Tu usuario no está asociado a ninguna institución.")
            return redirect('gestion_academica:lista_eventos_admin')
        evento = EventoInstitucional(institucion=institucion, creado_por=request.user)
        evento = _guardar_desde_form(request, evento)
        if not evento.titulo or not getattr(evento, 'fecha', None):
            messages.error(request, "El título y la fecha son obligatorios.")
        else:
            evento.save()
            messages.success(request, "Evento creado.")
            return redirect('gestion_academica:lista_eventos_admin')

    return render(request, 'gestion_academica/eventos/form.html', {
        'titulo_pagina': 'Nuevo Evento Institucional',
        'evento': None,
    })


@login_required
def editar_evento(request, pk):
    if not _es_coordinador_o_admin(request.user):
        raise PermissionDenied
    evento = get_object_or_404(_scope(EventoInstitucional.objects.all(), request.user), pk=pk)

    if request.method == 'POST':
        evento = _guardar_desde_form(request, evento)
        if not evento.titulo or not evento.fecha:
            messages.error(request, "El título y la fecha son obligatorios.")
        else:
            evento.save()
            messages.success(request, "Evento actualizado.")
            return redirect('gestion_academica:lista_eventos_admin')

    return render(request, 'gestion_academica/eventos/form.html', {
        'titulo_pagina': 'Editar Evento Institucional',
        'evento': evento,
    })


@login_required
def eliminar_evento(request, pk):
    if not _es_coordinador_o_admin(request.user):
        raise PermissionDenied
    if request.method != 'POST':
        raise PermissionDenied
    evento = get_object_or_404(_scope(EventoInstitucional.objects.all(), request.user), pk=pk)
    evento.delete()
    messages.success(request, "Evento eliminado.")
    return redirect('gestion_academica:lista_eventos_admin')
