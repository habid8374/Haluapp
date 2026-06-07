"""
recursos_educativos/views.py
=============================
Vistas del módulo de Recursos Educativos 3D.

Multi-institución: TODOS los querysets filtran por request.user.institucion_asociada.

Roles manejados:
  - Docente  → crear actividad, ver entregas, ajustar nota
  - Estudiante → abrir galería, abrir studio, progreso
"""
import decimal
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone

from gestion_academica.models import (
    ActividadCalificable,
    Calificacion,
    Curso,
    Docente,
    Estudiante,
    TipoActividad,
)

from .models import EntregaRecurso3D, RecursoEducativo3D


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_institucion(request):
    return getattr(request.user, 'institucion_asociada', None)


def _push_ws(group_name: str, *, kind: str, title: str, message: str,
             url: str = '', severity: str = 'info') -> None:
    """Notificación WS en tiempo real — falla silenciosamente."""
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
        pass


def _get_tipo_recurso_3d(institucion):
    """Obtiene o crea el TipoActividad 'Recurso 3D' para la institución."""
    tipo, _ = TipoActividad.objects.get_or_create(
        nombre='Recurso 3D',
        institucion=institucion,
        defaults={
            'descripcion': 'Actividad interactiva con el visor 3D del Cuerpo Humano.',
            'orden': 99,
        },
    )
    return tipo


# ─────────────────────────────────────────────────────────────────────────────
# Vistas del DOCENTE
# ─────────────────────────────────────────────────────────────────────────────

@login_required
def lista_recursos_docente(request):
    """
    Lista todas las actividades 3D creadas por el docente en su institución.
    """
    institucion = _get_institucion(request)
    if not institucion:
        messages.error(request, 'Tu cuenta no está asociada a ninguna institución.')
        return redirect('gestion_academica:inicio_academico')

    try:
        docente = Docente.objects.get(usuario=request.user, institucion=institucion)
    except Docente.DoesNotExist:
        messages.error(request, 'No tienes un perfil de docente en esta institución.')
        return redirect('gestion_academica:inicio_academico')

    recursos = (
        RecursoEducativo3D.objects
        .filter(
            institucion=institucion,
            actividad__curso__docentes_asignados=docente,
        )
        .select_related('actividad__curso__materia', 'actividad__curso__grado')
        .order_by('-actividad__fecha_publicacion')
    )

    # Enriquecer con conteo de entregas
    for recurso in recursos:
        recurso.total_entregas   = recurso.entregas.filter(institucion=institucion).count()
        recurso.entregas_completas = recurso.entregas.filter(institucion=institucion, completado=True).count()

    return render(request, 'recursos_educativos/lista_docente.html', {
        'recursos': recursos,
        'docente': docente,
        'titulo_pagina': 'Recursos Educativos 3D',
    })


@login_required
def crear_recurso_3d(request):
    """
    GET  → formulario para crear una actividad 3D.
    POST → crea ActividadCalificable + RecursoEducativo3D y notifica estudiantes.
    """
    institucion = _get_institucion(request)
    if not institucion:
        messages.error(request, 'Tu cuenta no está asociada a ninguna institución.')
        return redirect('gestion_academica:inicio_academico')

    try:
        docente = Docente.objects.get(usuario=request.user, institucion=institucion)
    except Docente.DoesNotExist:
        messages.error(request, 'No tienes un perfil de docente en esta institución.')
        return redirect('gestion_academica:inicio_academico')

    # Cursos del docente en esta institución
    cursos = Curso.objects.filter(
        docentes_asignados=docente,
        institucion=institucion,
    ).select_related('materia', 'grado')

    if request.method == 'POST':
        # ── Validación básica ──────────────────────────────────────
        curso_id       = request.POST.get('curso')
        titulo         = request.POST.get('titulo', '').strip()
        descripcion    = request.POST.get('descripcion', '').strip()
        modo           = request.POST.get('modo', RecursoEducativo3D.MODO_AMBOS)
        valor_maximo   = request.POST.get('valor_maximo', '5.00')
        fecha_limite   = request.POST.get('fecha_entrega_limite') or None

        errores = []
        if not curso_id:
            errores.append('Debes seleccionar un curso.')
        if not titulo:
            errores.append('El título es obligatorio.')
        if modo not in dict(RecursoEducativo3D.MODO_CHOICES):
            errores.append('Modo inválido.')

        try:
            valor_maximo = decimal.Decimal(valor_maximo)
            if valor_maximo <= 0:
                raise ValueError
        except (decimal.InvalidOperation, ValueError):
            errores.append('El valor máximo debe ser un número positivo.')

        if errores:
            for e in errores:
                messages.error(request, e)
            return render(request, 'recursos_educativos/crear_actividad.html', {
                'cursos': cursos,
                'modos': RecursoEducativo3D.MODO_CHOICES,
                'titulo_pagina': 'Crear Recurso 3D',
                'post_data': request.POST,
            })

        # ── Obtener curso y validar pertenencia ───────────────────
        try:
            curso = cursos.get(pk=curso_id)
        except Curso.DoesNotExist:
            messages.error(request, 'Curso no válido.')
            return redirect('recursos_educativos:crear')

        # ── Crear ActividadCalificable + RecursoEducativo3D ───────
        tipo = _get_tipo_recurso_3d(institucion)

        actividad = ActividadCalificable.objects.create(
            curso=curso,
            tipo_actividad=tipo,
            titulo=titulo,
            descripcion=descripcion,
            fecha_entrega_limite=fecha_limite or None,
            institucion=institucion,
        )

        recurso = RecursoEducativo3D.objects.create(
            actividad=actividad,
            modo=modo,
            valor_maximo=valor_maximo,
            institucion=institucion,
        )

        # ── Notificar estudiantes del grado vía WS ────────────────
        url_galeria = f'/academico/recursos/{recurso.pk}/galeria/'
        url_studio  = f'/academico/recursos/{recurso.pk}/studio/'
        url_actividad = url_studio if recurso.tiene_studio() else url_galeria

        estudiantes_grado = Estudiante.objects.filter(
            grado_actual=curso.grado,
            institucion=institucion,
            activo=True,
        )
        for est in estudiantes_grado:
            from gestion_academica.models import Notificacion
            Notificacion.objects.create(
                destinatario=est.usuario,
                mensaje=f'Nueva actividad 3D: "{titulo}" en {curso.materia.nombre_materia}.',
                enlace=url_actividad,
                institucion=institucion,
            )
            _push_ws(
                f'user_{est.usuario.pk}',
                kind='recurso_3d',
                title='🧠 Nueva actividad 3D disponible',
                message=f'{titulo} · {curso.materia.nombre_materia}',
                url=url_actividad,
                severity='info',
            )

        messages.success(request, f'Actividad 3D "{titulo}" creada correctamente.')
        return redirect('recursos_educativos:lista')

    # ── GET ────────────────────────────────────────────────────────
    return render(request, 'recursos_educativos/crear_actividad.html', {
        'cursos': cursos,
        'modos': RecursoEducativo3D.MODO_CHOICES,
        'titulo_pagina': 'Crear Recurso 3D',
        'post_data': {},
    })


@login_required
def ver_entregas_recurso(request, pk):
    """
    GET  → tabla de entregas de estudiantes para esta actividad.
    POST → el docente ajusta la nota manualmente.
    """
    institucion = _get_institucion(request)

    try:
        docente = Docente.objects.get(usuario=request.user, institucion=institucion)
    except Docente.DoesNotExist:
        messages.error(request, 'Acceso no autorizado.')
        return redirect('recursos_educativos:lista')

    recurso = get_object_or_404(
        RecursoEducativo3D,
        pk=pk,
        institucion=institucion,
        actividad__curso__docentes_asignados=docente,
    )

    if request.method == 'POST':
        # Ajuste manual de nota por el docente
        estudiante_id = request.POST.get('estudiante_id')
        nueva_nota    = request.POST.get('nota', '').strip()

        try:
            estudiante = Estudiante.objects.get(pk=estudiante_id, institucion=institucion)
            nota_decimal = decimal.Decimal(nueva_nota)
            if nota_decimal < 0 or nota_decimal > recurso.valor_maximo:
                raise ValueError('Nota fuera de rango.')

            Calificacion.objects.update_or_create(
                estudiante=estudiante,
                actividad_calificable=recurso.actividad,
                institucion=institucion,
                defaults={
                    'valor_numerico': nota_decimal,
                    'registrada_por': docente,
                    'observaciones': 'Nota ajustada manualmente por el docente.',
                },
            )
            messages.success(request, f'Nota actualizada para {estudiante.usuario.get_full_name()}.')
        except (Estudiante.DoesNotExist, decimal.InvalidOperation, ValueError) as e:
            messages.error(request, f'Error al guardar la nota: {e}')

        return redirect('recursos_educativos:entregas', pk=pk)

    # ── GET — construir tabla de entregas ─────────────────────────
    # Todos los estudiantes del grado del curso
    estudiantes_grado = Estudiante.objects.filter(
        grado_actual=recurso.actividad.curso.grado,
        institucion=institucion,
        activo=True,
    ).select_related('usuario').order_by('usuario__last_name', 'usuario__first_name')

    # Entregas existentes como dict {estudiante_pk: entrega}
    entregas_dict = {
        e.estudiante_id: e
        for e in EntregaRecurso3D.objects.filter(
            recurso=recurso,
            institucion=institucion,
        ).select_related('estudiante__usuario')
    }

    # Calificaciones existentes como dict {estudiante_pk: calificacion}
    califs_dict = {
        c.estudiante_id: c
        for c in Calificacion.objects.filter(
            actividad_calificable=recurso.actividad,
            institucion=institucion,
        )
    }

    filas = []
    for est in estudiantes_grado:
        filas.append({
            'estudiante': est,
            'entrega': entregas_dict.get(est.pk),
            'calificacion': califs_dict.get(est.pk),
        })

    return render(request, 'recursos_educativos/ver_entregas.html', {
        'recurso': recurso,
        'filas': filas,
        'titulo_pagina': f'Entregas — {recurso.actividad.titulo}',
    })


# ─────────────────────────────────────────────────────────────────────────────
# Vistas del ESTUDIANTE
# ─────────────────────────────────────────────────────────────────────────────

def _get_estudiante_o_403(request, institucion):
    """Retorna el Estudiante o None si el usuario no es estudiante."""
    try:
        return Estudiante.objects.get(usuario=request.user, institucion=institucion)
    except Estudiante.DoesNotExist:
        return None


@login_required
def galeria_directa(request):
    """Galería 3D directa para docentes — sin actividad, solo para proyectar en clase."""
    institucion = _get_institucion(request)
    try:
        Docente.objects.get(usuario=request.user, institucion=institucion)
    except Docente.DoesNotExist:
        messages.error(request, 'Solo los docentes pueden acceder a este recurso.')
        return redirect('gestion_academica:inicio_academico')

    return render(request, 'recursos_educativos/visor_galeria.html', {
        'titulo_pagina': 'Galería 3D — Cuerpo Humano',
        'actividad': None,
        'recurso': None,
    })


@login_required
def abrir_visor_galeria(request, pk):
    """Renderiza el visor de Galería 3D — solo accesible para docentes."""
    institucion = _get_institucion(request)
    recurso = get_object_or_404(RecursoEducativo3D, pk=pk, institucion=institucion)

    # Solo docentes pueden abrir la galería (para proyección en clase)
    try:
        Docente.objects.get(usuario=request.user, institucion=institucion)
    except Docente.DoesNotExist:
        messages.error(request, 'El visor de Galería 3D es solo para docentes.')
        return redirect('gestion_academica:inicio_academico')

    if not recurso.tiene_galeria():
        messages.error(request, 'Esta actividad no incluye el modo Galería.')
        return redirect('recursos_educativos:lista')

    return render(request, 'recursos_educativos/visor_galeria.html', {
        'recurso': recurso,
        'actividad': recurso.actividad,
        'titulo_pagina': recurso.actividad.titulo,
    })


@login_required
def abrir_visor_studio(request, pk):
    """Renderiza el Studio 3D para el estudiante."""
    institucion = _get_institucion(request)
    recurso = get_object_or_404(RecursoEducativo3D, pk=pk, institucion=institucion)

    if not recurso.tiene_studio():
        messages.error(request, 'Esta actividad no incluye el modo Studio.')
        return redirect('gestion_academica:dashboard_estudiante')

    estudiante = _get_estudiante_o_403(request, institucion)
    if not estudiante:
        messages.error(request, 'No tienes un perfil de estudiante en esta institución.')
        return redirect('gestion_academica:inicio_academico')

    entrega, _ = EntregaRecurso3D.objects.get_or_create(
        recurso=recurso,
        estudiante=estudiante,
        institucion=institucion,
    )

    return render(request, 'recursos_educativos/visor_studio.html', {
        'recurso': recurso,
        'actividad': recurso.actividad,
        'entrega': entrega,
        'titulo_pagina': f'Studio 3D — {recurso.actividad.titulo}',
    })


# ─────────────────────────────────────────────────────────────────────────────
# API interna — llamada desde studio.js
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def api_registrar_progreso(request, pk):
    """
    Recibe JSON { "piezas_colocadas": int } desde studio.js.
    Actualiza la entrega del estudiante y auto-califica si completa las 13 piezas.
    Retorna JSON { ok, completado, piezas, nota }.
    Multi-institución: filtra por institucion_asociada del usuario.
    """
    institucion = _get_institucion(request)
    if not institucion:
        return JsonResponse({'ok': False, 'error': 'Sin institución asociada.'}, status=403)

    estudiante = _get_estudiante_o_403(request, institucion)
    if not estudiante:
        return JsonResponse({'ok': False, 'error': 'No eres estudiante.'}, status=403)

    recurso = get_object_or_404(RecursoEducativo3D, pk=pk, institucion=institucion)

    try:
        body = json.loads(request.body)
        piezas = int(body.get('piezas_colocadas', 0))
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Datos inválidos.'}, status=400)

    entrega, _ = EntregaRecurso3D.objects.get_or_create(
        recurso=recurso,
        estudiante=estudiante,
        institucion=institucion,
    )

    primera_completacion = entrega.registrar_progreso(piezas)

    nota = None
    if entrega.completado:
        nota = str(recurso.calcular_nota(entrega.piezas_colocadas))

        if primera_completacion:
            # Notificar al estudiante vía WS
            _push_ws(
                f'user_{request.user.pk}',
                kind='studio_completado',
                title='🎉 ¡Cuerpo armado!',
                message=f'Completaste el Studio de "{recurso.actividad.titulo}". Nota: {nota}',
                severity='success',
            )

    return JsonResponse({
        'ok': True,
        'completado': entrega.completado,
        'piezas': entrega.piezas_colocadas,
        'nota': nota,
    })
