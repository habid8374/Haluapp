"""Halu STEAM — Fase 2: Proyectos (ABP) e Insignias/microcredenciales.

Un ProyectoSTEAM se enlaza 1 a 1 a una ActividadCalificable: el título, curso
y categoría de evaluación se capturan una sola vez al crear el proyecto, y a
partir de ahí la calificación pasa por el Libro de Notas de siempre (que ya
filtra por énfasis) — esta vista nunca escribe una Calificacion directamente.

Todo lo que lista estudiantes (participantes) respeta el mismo aislamiento
por énfasis que el resto de la plataforma: si el curso es un taller scoped a
un énfasis, solo se pueden agregar estudiantes de ese mismo énfasis.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from ..forms import (
    EvidenciaProyectoForm, HitoProyectoForm, InsigniaForm,
    OtorgarInsigniaForm, ParticipanteProyectoForm, ProyectoSTEAMForm,
)
from ..models import (
    ActividadCalificable, EvidenciaProyecto, HitoProyecto, Insignia,
    InsigniaObtenida, ParticipanteProyecto, ProyectoSTEAM,
)
from ._main import get_filtered_queryset


def _es_coordinador_o_admin(user):
    rol = getattr(user, 'rol', '') or ''
    return rol in ('coordinador', 'administrador', 'admin_institucion', 'rector') or user.is_superuser


def _proyectos_visibles_para(user):
    """Coordinación ve todos los proyectos de su institución; un docente solo
    los de los cursos donde está asignado."""
    qs = get_filtered_queryset(ProyectoSTEAM, user, ProyectoSTEAM.objects.select_related('curso', 'curso__grado', 'curso__materia', 'actividad_calificable'))
    if user.is_superuser or _es_coordinador_o_admin(user):
        return qs
    if hasattr(user, 'docente'):
        return qs.filter(curso__docentes_asignados=user.docente)
    return ProyectoSTEAM.objects.none()


def _puede_gestionar_proyecto(user, proyecto):
    if user.is_superuser or _es_coordinador_o_admin(user):
        return True
    return hasattr(user, 'docente') and proyecto.curso.docentes_asignados.filter(pk=user.docente.pk).exists()


class ProyectoSTEAMListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ProyectoSTEAM
    template_name = 'gestion_academica/proyecto_steam_lista.html'
    context_object_name = 'proyectos'
    permission_required = 'gestion_academica.view_proyectosteam'

    def get_queryset(self):
        return _proyectos_visibles_para(self.request.user).order_by('-creado_en')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = _("Proyectos STEAM")
        return context


@login_required
@permission_required('gestion_academica.add_proyectosteam', raise_exception=True)
def crear_proyecto_steam(request):
    if request.method == 'POST':
        form = ProyectoSTEAMForm(request.POST, request=request)
        if form.is_valid():
            curso = form.cleaned_data['curso']
            tipo_actividad = form.cleaned_data['tipo_actividad']
            with transaction.atomic():
                actividad = ActividadCalificable.objects.create(
                    curso=curso,
                    tipo_actividad=tipo_actividad,
                    titulo=form.cleaned_data['titulo'],
                    descripcion=form.cleaned_data.get('reto', ''),
                    fecha_publicacion=form.cleaned_data.get('fecha_inicio') or timezone.localdate(),
                    fecha_entrega_limite=form.cleaned_data.get('fecha_entrega'),
                    institucion=curso.institucion,
                )
                proyecto = form.save(commit=False)
                proyecto.institucion = curso.institucion
                proyecto.actividad_calificable = actividad
                proyecto.creado_por = request.user
                proyecto.save()
            messages.success(request, _("Proyecto STEAM '%(titulo)s' creado. Ya puedes agregar hitos y equipo.") % {'titulo': proyecto.titulo})
            return redirect('gestion_academica:detalle_proyecto_steam', pk=proyecto.pk)
    else:
        form = ProyectoSTEAMForm(request=request)
    return render(request, 'gestion_academica/proyecto_steam_formulario.html', {
        'form': form, 'titulo_pagina': _("Nuevo Proyecto STEAM"),
    })


@login_required
@permission_required('gestion_academica.change_proyectosteam', raise_exception=True)
def editar_proyecto_steam(request, pk):
    proyecto = get_object_or_404(_proyectos_visibles_para(request.user), pk=pk)
    if not _puede_gestionar_proyecto(request.user, proyecto):
        messages.error(request, _("No tienes permiso para editar este proyecto."))
        return redirect('gestion_academica:lista_proyectos_steam')
    if request.method == 'POST':
        form = ProyectoSTEAMForm(request.POST, instance=proyecto, request=request)
        if form.is_valid():
            with transaction.atomic():
                proyecto = form.save()
                if proyecto.actividad_calificable_id:
                    actividad = proyecto.actividad_calificable
                    actividad.curso = form.cleaned_data['curso']
                    actividad.tipo_actividad = form.cleaned_data['tipo_actividad']
                    actividad.titulo = form.cleaned_data['titulo']
                    actividad.descripcion = form.cleaned_data.get('reto', '')
                    actividad.fecha_entrega_limite = form.cleaned_data.get('fecha_entrega')
                    actividad.save()
            messages.success(request, _("Proyecto actualizado."))
            return redirect('gestion_academica:detalle_proyecto_steam', pk=proyecto.pk)
    else:
        form = ProyectoSTEAMForm(instance=proyecto, request=request)
    return render(request, 'gestion_academica/proyecto_steam_formulario.html', {
        'form': form, 'titulo_pagina': _("Editar Proyecto STEAM"), 'proyecto': proyecto,
    })


@login_required
@permission_required('gestion_academica.delete_proyectosteam', raise_exception=True)
def eliminar_proyecto_steam(request, pk):
    proyecto = get_object_or_404(_proyectos_visibles_para(request.user), pk=pk)
    if not _puede_gestionar_proyecto(request.user, proyecto):
        messages.error(request, _("No tienes permiso para eliminar este proyecto."))
        return redirect('gestion_academica:lista_proyectos_steam')
    if request.method == 'POST':
        titulo = proyecto.titulo
        proyecto.delete()
        messages.success(request, _("Proyecto '%(titulo)s' eliminado.") % {'titulo': titulo})
        return redirect('gestion_academica:lista_proyectos_steam')
    return render(request, 'gestion_academica/proyecto_steam_confirmar_eliminar.html', {
        'proyecto': proyecto, 'titulo_pagina': _("Eliminar Proyecto STEAM"),
    })


@login_required
@permission_required('gestion_academica.view_proyectosteam', raise_exception=True)
def detalle_proyecto_steam(request, pk):
    proyecto = get_object_or_404(
        _proyectos_visibles_para(request.user).prefetch_related('hitos', 'participantes__estudiante__usuario', 'evidencias'),
        pk=pk,
    )
    puede_gestionar = _puede_gestionar_proyecto(request.user, proyecto)

    hito_form = HitoProyectoForm()
    participante_form = ParticipanteProyectoForm(proyecto=proyecto)
    evidencia_form = EvidenciaProyectoForm()
    otorgar_form = OtorgarInsigniaForm(institucion=proyecto.institucion)

    if request.method == 'POST':
        if not puede_gestionar:
            messages.error(request, _("No tienes permiso para modificar este proyecto."))
            return redirect('gestion_academica:detalle_proyecto_steam', pk=proyecto.pk)

        accion = request.POST.get('accion')

        if accion == 'agregar_hito':
            hito_form = HitoProyectoForm(request.POST)
            if hito_form.is_valid():
                hito = hito_form.save(commit=False)
                hito.proyecto = proyecto
                hito.save()
                messages.success(request, _("Hito agregado."))
                return redirect('gestion_academica:detalle_proyecto_steam', pk=proyecto.pk)

        elif accion == 'agregar_participante':
            participante_form = ParticipanteProyectoForm(request.POST, proyecto=proyecto)
            if participante_form.is_valid():
                participante = participante_form.save(commit=False)
                participante.proyecto = proyecto
                participante.save()
                messages.success(request, _("Estudiante agregado al equipo."))
                return redirect('gestion_academica:detalle_proyecto_steam', pk=proyecto.pk)

        elif accion == 'agregar_evidencia':
            evidencia_form = EvidenciaProyectoForm(request.POST)
            if evidencia_form.is_valid():
                url_valida, error = _validar_url_evidencia(evidencia_form.cleaned_data['url'])
                if not url_valida:
                    evidencia_form.add_error('url', error)
                else:
                    evidencia = evidencia_form.save(commit=False)
                    evidencia.proyecto = proyecto
                    evidencia.subido_por = request.user
                    evidencia.save()
                    messages.success(request, _("Evidencia agregada."))
                    return redirect('gestion_academica:detalle_proyecto_steam', pk=proyecto.pk)

        elif accion == 'otorgar_insignia':
            estudiante_pk = request.POST.get('estudiante_id')
            participante = proyecto.participantes.filter(estudiante_id=estudiante_pk).first()
            otorgar_form = OtorgarInsigniaForm(request.POST, institucion=proyecto.institucion)
            if participante and otorgar_form.is_valid():
                insignia = otorgar_form.cleaned_data['insignia']
                ya_otorgada = InsigniaObtenida.objects.filter(
                    insignia=insignia, estudiante=participante.estudiante, proyecto=proyecto,
                ).exists()
                if ya_otorgada:
                    messages.warning(request, _("Ese estudiante ya tiene esa insignia en este proyecto."))
                else:
                    InsigniaObtenida.objects.create(
                        institucion=proyecto.institucion,
                        insignia=insignia,
                        estudiante=participante.estudiante,
                        proyecto=proyecto,
                        otorgada_por=request.user,
                        nota=otorgar_form.cleaned_data.get('nota', ''),
                    )
                    messages.success(request, _("Insignia '%(insignia)s' otorgada a %(estudiante)s.") % {
                        'insignia': insignia.nombre, 'estudiante': participante.estudiante,
                    })
                return redirect('gestion_academica:detalle_proyecto_steam', pk=proyecto.pk)

    context = {
        'proyecto': proyecto,
        'puede_gestionar': puede_gestionar,
        'hito_form': hito_form,
        'participante_form': participante_form,
        'evidencia_form': evidencia_form,
        'otorgar_form': otorgar_form,
        'insignias_por_estudiante': {
            est_id: list(nombres) for est_id, nombres in _insignias_por_estudiante(proyecto).items()
        },
        'titulo_pagina': proyecto.titulo,
    }
    return render(request, 'gestion_academica/proyecto_steam_detalle.html', context)


def _insignias_por_estudiante(proyecto):
    mapa = {}
    for io in InsigniaObtenida.objects.filter(proyecto=proyecto).select_related('insignia'):
        mapa.setdefault(io.estudiante_id, []).append(io.insignia.nombre)
    return mapa


def _validar_url_evidencia(url):
    """Mismo criterio de seguridad que BancoPregunta.imagen_url: solo
    http/https y sin apuntar a una IP privada/interna (SSRF)."""
    from urllib.parse import urlparse
    import ipaddress
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return False, _("El enlace debe comenzar con http:// o https://")
    hostname = parsed.hostname or ''
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            return False, _("Ese enlace no es válido.")
    except ValueError:
        pass  # Es un dominio, no una IP — permitido
    return True, None


@require_POST
@login_required
def toggle_hito_proyecto(request, pk):
    hito = get_object_or_404(HitoProyecto.objects.select_related('proyecto'), pk=pk)
    if not _puede_gestionar_proyecto(request.user, hito.proyecto):
        return JsonResponse({'ok': False, 'error': 'permiso'}, status=403)
    hito.completado = not hito.completado
    hito.save(update_fields=['completado'])
    return JsonResponse({'ok': True, 'completado': hito.completado, 'porcentaje': hito.proyecto.porcentaje_hitos_completados})


@require_POST
@login_required
def eliminar_hito_proyecto(request, pk):
    hito = get_object_or_404(HitoProyecto.objects.select_related('proyecto'), pk=pk)
    if _puede_gestionar_proyecto(request.user, hito.proyecto):
        proyecto_pk = hito.proyecto_id
        hito.delete()
        messages.success(request, _("Hito eliminado."))
        return redirect('gestion_academica:detalle_proyecto_steam', pk=proyecto_pk)
    messages.error(request, _("No tienes permiso para esta acción."))
    return redirect('gestion_academica:lista_proyectos_steam')


@require_POST
@login_required
def eliminar_participante_proyecto(request, pk):
    participante = get_object_or_404(ParticipanteProyecto.objects.select_related('proyecto'), pk=pk)
    if _puede_gestionar_proyecto(request.user, participante.proyecto):
        proyecto_pk = participante.proyecto_id
        participante.delete()
        messages.success(request, _("Estudiante removido del equipo."))
        return redirect('gestion_academica:detalle_proyecto_steam', pk=proyecto_pk)
    messages.error(request, _("No tienes permiso para esta acción."))
    return redirect('gestion_academica:lista_proyectos_steam')


@require_POST
@login_required
def eliminar_evidencia_proyecto(request, pk):
    evidencia = get_object_or_404(EvidenciaProyecto.objects.select_related('proyecto'), pk=pk)
    if _puede_gestionar_proyecto(request.user, evidencia.proyecto):
        proyecto_pk = evidencia.proyecto_id
        evidencia.delete()
        messages.success(request, _("Evidencia eliminada."))
        return redirect('gestion_academica:detalle_proyecto_steam', pk=proyecto_pk)
    messages.error(request, _("No tienes permiso para esta acción."))
    return redirect('gestion_academica:lista_proyectos_steam')


# ─── Insignias (catálogo) ────────────────────────────────────────────────────

class InsigniaListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Insignia
    template_name = 'gestion_academica/insignia_lista.html'
    context_object_name = 'insignia_list'
    permission_required = 'gestion_academica.view_insignia'

    def get_queryset(self):
        base_queryset = super().get_queryset().order_by('nombre')
        return get_filtered_queryset(self.model, self.request.user, base_queryset)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = _("Insignias")
        return context


class InsigniaCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Insignia
    form_class = InsigniaForm
    template_name = 'gestion_academica/insignia_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_insignias')
    permission_required = 'gestion_academica.add_insignia'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = _("Nueva Insignia")
        return context

    def form_valid(self, form):
        if not self.request.user.is_superuser:
            form.instance.institucion = self.request.user.institucion_asociada
        messages.success(self.request, _("Insignia '%(nombre)s' creada.") % {'nombre': form.cleaned_data['nombre']})
        return super().form_valid(form)


class InsigniaUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Insignia
    form_class = InsigniaForm
    template_name = 'gestion_academica/insignia_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_insignias')
    permission_required = 'gestion_academica.change_insignia'

    def get_queryset(self):
        return get_filtered_queryset(self.model, self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = _("Editar Insignia")
        return context

    def form_valid(self, form):
        messages.success(self.request, _("Insignia actualizada."))
        return super().form_valid(form)


class InsigniaDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Insignia
    template_name = 'gestion_academica/insignia_confirmar_eliminar.html'
    success_url = reverse_lazy('gestion_academica:lista_insignias')
    context_object_name = 'insignia'
    permission_required = 'gestion_academica.delete_insignia'

    def get_queryset(self):
        return get_filtered_queryset(self.model, self.request.user)

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        messages.success(request, _("Insignia '%(nombre)s' eliminada.") % {'nombre': obj.nombre})
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = _("Confirmar Eliminación de Insignia")
        return context


# ─── Portafolio del estudiante ───────────────────────────────────────────────

@login_required
def mi_portafolio_steam(request):
    """Vista del estudiante: sus proyectos STEAM, insignias y evidencia."""
    if not hasattr(request.user, 'estudiante'):
        messages.error(request, _("Esta pantalla es solo para estudiantes."))
        return redirect('gestion_academica:inicio_academico')

    estudiante = request.user.estudiante
    participaciones = (
        ParticipanteProyecto.objects
        .filter(estudiante=estudiante)
        .select_related('proyecto', 'proyecto__curso', 'proyecto__curso__materia')
        .prefetch_related('proyecto__evidencias')
        .order_by('-proyecto__creado_en')
    )
    insignias = (
        InsigniaObtenida.objects
        .filter(estudiante=estudiante)
        .select_related('insignia', 'proyecto')
        .order_by('-fecha_obtenida')
    )
    context = {
        'estudiante': estudiante,
        'participaciones': participaciones,
        'insignias': insignias,
        'titulo_pagina': _("Mi Portafolio STEAM"),
    }
    return render(request, 'gestion_academica/mi_portafolio_steam.html', context)
