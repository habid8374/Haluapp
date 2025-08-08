# gestion_academica/views.py

# Importaciones estándar de Django
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.template.loader import get_template
from django.http import HttpResponse
from xhtml2pdf import pisa
from django.core.mail import EmailMessage
from django.db.models import Q, Avg
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.auth import get_user_model

# Modelos de la aplicación
from .models import (
    Usuario, Grado, Estudiante, Docente, Familiar,
    Materia, PeriodoAcademico, Curso, DirectorCurso,
    EsquemaCalificacion, TipoActividad, ActividadCalificable, Calificacion,
    PlanCurricular, Deber, EntregaDeber, MencionReconocimiento, ArchivoPlanAcademico,
    ConfiguracionInstitucion, TipoConceptoPago, ConceptoPago, PagoRegistrado,
    CuentaPorCobrarEstudiante, InstitucionEducativa,
    Noticia # Asegúrate de importar Noticia
)
from django.utils import timezone
import datetime

# Formularios de la aplicación
from .forms import (
    GradoForm,
    EstudianteForm, UsuarioEstudianteForm, UsuarioEstudianteUpdateForm,
    DocenteForm, UsuarioDocenteForm, UsuarioDocenteUpdateForm,
    MateriaForm,
    PeriodoAcademicoForm,
    CuentaPorCobrarEstudianteForm,
    CursoForm,
    DirectorCursoForm,
    EsquemaCalificacionForm,
    TipoActividadForm,
    ActividadCalificableForm,
    CalificacionForm,
    DeberForm,
    EntregaDeberForm,
    PlanCurricularForm,
    MencionReconocimientoForm,
    PagoRegistradoForm,
    ArchivoPlanAcademicoForm,
    TipoConceptoPagoForm,
    ConceptoPagoForm,
    PagoForm,
    RegistroInicialForm,
    NoticiaForm, # Asegúrate que NoticiaForm esté importado
)

# Para cálculos en vistas
from django.db.models import Sum, Avg, F, ExpressionWrapper, DecimalField, Prefetch

@permission_required('gestion_academica.ver_cuentas_por_cobrar', raise_exception=True)
def lista_cuentas_por_cobrar(request):
    cuentas = CuentaPorCobrarEstudiante.objects.select_related('estudiante', 'concepto_pago').all()
    return render(request, 'gestion_academica/finanzas/cuentas_por_cobrar.html', {'cuentas': cuentas})

# Vista de inicio
@login_required
def inicio_academico(request):
    user = request.user
    rol = user.rol if hasattr(user, 'rol') else 'Desconocido'
    
    if user.is_superuser or (hasattr(user, 'rol') and user.rol == 'administrativo'):
        pass 
    elif hasattr(user, 'rol'):
        if user.rol == 'estudiante':
            return redirect('gestion_academica:mis_cursos_calificaciones')
        elif user.rol == 'docente':
            return redirect('gestion_academica:docente_seleccionar_curso_libro_notas') 
        elif user.rol == 'familiar':
            return redirect('gestion_academica:portal_familiar_inicio')
    
    context = {
        'nombre_usuario': user.username,
        'rol_usuario': rol,
        'mensaje': 'Bienvenido al Módulo Académico.'
    }
    return render(request, 'gestion_academica/inicio_academico.html', context)

@login_required
@permission_required('gestion_academica.view_cuentaporcobrarestudiante', raise_exception=True)
def cuentas_por_estudiante(request):
    cuentas = CuentaPorCobrarEstudiante.objects.select_related('estudiante').all()

    for cuenta in cuentas:
        cuenta.saldo_restante = (cuenta.monto_asignado or 0) - (cuenta.monto_pagado or 0)
        
    context = {'cuentas': cuentas}
    return render(request, 'gestion_academica/finanzas/mis_cuentas.html', context)

@login_required
@permission_required('gestion_academica.add_pagoregistrado', raise_exception=True)
def registrar_pago(request, cuenta_id):
    cuenta = get_object_or_404(CuentaPorCobrarEstudiante, id=cuenta_id)
    
    if request.method == 'POST':
        form = PagoForm(request.POST, cuenta=cuenta)
        if form.is_valid():
            pago = form.save(commit=False)
            pago.cuenta = cuenta
            pago.usuario_registro = request.user  # Guarda quién registró el pago
            pago.save()

            if cuenta.concepto_pago.nombre.lower().startswith("mensualidad"):
               siguiente_mes = cuenta.fecha_vencimiento_especifica.month + 1
               if siguiente_mes <= 11:  # Hasta noviembre
                   from .models import ConceptoPago
                   concepto_mensualidad = ConceptoPago.objects.filter(nombre__icontains="mensualidad", automatico=True).first()
                   if concepto_mensualidad:
                      nueva_fecha = cuenta.fecha_vencimiento_especifica.replace(month=siguiente_mes)
                      ya_existe = CuentaPorCobrarEstudiante.objects.filter(
                          estudiante=cuenta.estudiante,
                          concepto_pago=concepto_mensualidad,
                          fecha_vencimiento_especifica=nueva_fecha
                      ).exists()
                      if not ya_existe:
                         CuentaPorCobrarEstudiante.objects.create(
                             estudiante=cuenta.estudiante,
                             concepto_pago=concepto_mensualidad,
                             monto_asignado=concepto_mensualidad.valor,
                             fecha_vencimiento_especifica=nueva_fecha
                         )
            
            # Actualizar saldo pendiente
            cuenta.valor_restante -= pago.monto_pagado
            cuenta.save()
            
            messages.success(request, 'Pago registrado exitosamente.')
            return redirect('gestion_academica:mis_cuentas')  # O a donde quieras redirigir
        else:
            messages.error(request, 'Hubo un error al registrar el pago. Revisa los datos.')
    else:
        form = PagoForm(cuenta=cuenta)

    context = {
        'cuenta': cuenta,
        'form': form
    }
    return render(request, 'gestion_academica/finanzas/registrar_pago.html', context)            
        
    # --- Vistas para Grados ---
class GradoListView(LoginRequiredMixin, ListView):
    model = Grado
    template_name = 'gestion_academica/grado_lista.html'
    context_object_name = 'grados'

class GradoCreateView(LoginRequiredMixin, CreateView):
    model = Grado
    form_class = GradoForm
    template_name = 'gestion_academica/grado_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_grados')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Crear Nuevo Grado"
        return context
    def form_valid(self, form):
        messages.success(self.request, "Grado creado exitosamente.")
        return super().form_valid(form)

class GradoUpdateView(LoginRequiredMixin, UpdateView):
    model = Grado
    form_class = GradoForm
    template_name = 'gestion_academica/grado_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_grados')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Editar Grado"
        return context
    def form_valid(self, form):
        messages.success(self.request, "Grado actualizado exitosamente.")
        return super().form_valid(form)

class GradoDeleteView(LoginRequiredMixin, DeleteView):
    model = Grado
    template_name = 'gestion_academica/grado_confirmar_eliminar.html'
    success_url = reverse_lazy('gestion_academica:lista_grados')
    context_object_name = 'grado'
    def delete(self, request, *args, **kwargs):
        grado_eliminado = self.get_object()
        messages.success(request, f"El grado '{grado_eliminado.nombre}' ha sido eliminado exitosamente.")
        return super().delete(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Confirmar Eliminación de Grado"
        return context

# --- Vistas para Estudiantes (Gestión por Admin/Docente) ---
class EstudianteListView(LoginRequiredMixin, ListView):
    model = Estudiante
    template_name = 'gestion_academica/estudiante_lista.html'
    context_object_name = 'estudiantes'
    paginate_by = 10
    queryset = Estudiante.objects.select_related('usuario', 'grado_actual').order_by('usuario__last_name', 'usuario__first_name')

class EstudianteDetailView(LoginRequiredMixin, DetailView):
    model = Estudiante
    template_name = 'gestion_academica/estudiante_detalle.html'
    context_object_name = 'estudiante'
    queryset = Estudiante.objects.select_related('usuario', 'grado_actual').all()

@login_required
def crear_estudiante(request):
    if request.method == 'POST':
        usuario_form = UsuarioEstudianteForm(request.POST, prefix="usr")
        estudiante_form = EstudianteForm(request.POST, request.FILES or None, prefix="est")
        if usuario_form.is_valid() and estudiante_form.is_valid():
            usuario = usuario_form.save()
            estudiante = estudiante_form.save(commit=False)
            estudiante.usuario = usuario
            estudiante.save()
            messages.success(request, f"Estudiante '{usuario.username}' creado exitosamente.")
            return redirect('gestion_academica:lista_estudiantes')
        else:
            messages.error(request, "Por favor corrige los errores en el formulario.")
    else:
        usuario_form = UsuarioEstudianteForm(prefix="usr")
        estudiante_form = EstudianteForm(prefix="est")
    context = {'usuario_form': usuario_form, 'estudiante_form': estudiante_form, 'titulo': 'Registrar Nuevo Estudiante'}
    return render(request, 'gestion_academica/estudiante_formulario.html', context)

@login_required
def editar_estudiante(request, pk):
    estudiante = get_object_or_404(Estudiante, pk=pk)
    usuario = estudiante.usuario
    if request.method == 'POST':
        usuario_form = UsuarioEstudianteUpdateForm(request.POST, instance=usuario, prefix="usr")
        estudiante_form = EstudianteForm(request.POST, request.FILES or None, instance=estudiante, prefix="est")
        if usuario_form.is_valid() and estudiante_form.is_valid():
            usuario_form.save()
            estudiante_form.save()
            messages.success(request, f"Datos del estudiante '{usuario.username}' actualizados exitosamente.")
            return redirect('gestion_academica:lista_estudiantes')
        else:
            messages.error(request, "Por favor corrige los errores en el formulario.")
    else:
        usuario_form = UsuarioEstudianteUpdateForm(instance=usuario, prefix="usr")
        estudiante_form = EstudianteForm(instance=estudiante, prefix="est")
    context = {'usuario_form': usuario_form, 'estudiante_form': estudiante_form, 'titulo': f'Editar Estudiante: {usuario.get_full_name() or usuario.username}', 'estudiante_obj': estudiante}
    return render(request, 'gestion_academica/estudiante_formulario.html', context)

@login_required # O quitar si quieres que sea pública
def calendario_academico_view(request):
    # Por ahora, esta vista solo renderizará una plantilla estática.
    # Más adelante, podrías pasar aquí eventos desde un modelo de Calendario.
    context = {
        'titulo_pagina': "Calendario Académico Institucional",
        # 'eventos_del_mes': [], # Ejemplo si tuvieras eventos
    }
    return render(request, 'gestion_academica/calendario_academico.html', context)

# --- VISTA PARA AYUDA Y SOPORTE (PÁGINA SIMPLE) ---
@login_required # O quitar si quieres que sea pública
def ayuda_soporte_view(request):
    # Por ahora, esta vista solo renderizará una plantilla estática.
    context = {
        'titulo_pagina': "Centro de Ayuda y Soporte",
        # 'preguntas_frecuentes': [], # Ejemplo
        # 'contacto_email': "soporte@institucion.edu",
        # 'contacto_telefono': "123-4567890",
    }
    return render(request, 'gestion_academica/ayuda_soporte.html', context)    

class EstudianteDeleteView(LoginRequiredMixin, DeleteView):
    model = Estudiante
    template_name = 'gestion_academica/estudiante_confirmar_eliminar.html'
    success_url = reverse_lazy('gestion_academica:lista_estudiantes')
    context_object_name = 'estudiante'
    def delete(self, request, *args, **kwargs):
        estudiante_obj = self.get_object()
        nombre_completo = estudiante_obj.usuario.get_full_name() or estudiante_obj.usuario.username
        messages.success(request, f"El estudiante '{nombre_completo}' y su cuenta de usuario han sido eliminados.")
        return super().delete(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Confirmar Eliminación de Estudiante"
        return context

# --- Vistas para Docentes (Gestión por Admin) ---
class DocenteListView(LoginRequiredMixin, ListView):
    model = Docente
    template_name = 'gestion_academica/docente_lista.html'
    context_object_name = 'docentes'
    paginate_by = 10
    queryset = Docente.objects.select_related('usuario').order_by('usuario__last_name', 'usuario__first_name')

class DocenteDetailView(LoginRequiredMixin, DetailView):
    model = Docente
    template_name = 'gestion_academica/docente_detalle.html'
    context_object_name = 'docente'
    queryset = Docente.objects.select_related('usuario').all()

@login_required
def crear_docente(request):
    if request.method == 'POST':
        usuario_form = UsuarioDocenteForm(request.POST, prefix="usr")
        docente_form = DocenteForm(request.POST, request.FILES or None, prefix="doc")
        if usuario_form.is_valid() and docente_form.is_valid():
            usuario = usuario_form.save()
            docente = docente_form.save(commit=False)
            docente.usuario = usuario
            docente.save()
            messages.success(request, f"Docente '{usuario.username}' creado exitosamente.")
            return redirect('gestion_academica:lista_docentes')
        else:
            messages.error(request, "Por favor corrige los errores en el formulario.")
    else:
        usuario_form = UsuarioDocenteForm(prefix="usr")
        docente_form = DocenteForm(prefix="doc")
    context = {'usuario_form': usuario_form, 'docente_form': docente_form, 'titulo': 'Registrar Nuevo Docente'}
    return render(request, 'gestion_academica/docente_formulario.html', context)

@login_required
def editar_docente(request, pk):
    docente = get_object_or_404(Docente, pk=pk)
    usuario = docente.usuario
    if request.method == 'POST':
        usuario_form = UsuarioDocenteUpdateForm(request.POST, instance=usuario, prefix="usr")
        docente_form = DocenteForm(request.POST, request.FILES or None, instance=docente, prefix="doc")
        if usuario_form.is_valid() and docente_form.is_valid():
            usuario_form.save()
            docente_form.save()
            messages.success(request, f"Datos del docente '{usuario.username}' actualizados exitosamente.")
            return redirect('gestion_academica:lista_docentes')
        else:
            messages.error(request, "Por favor corrige los errores en el formulario.")
    else:
        usuario_form = UsuarioDocenteUpdateForm(instance=usuario, prefix="usr")
        docente_form = DocenteForm(instance=docente, prefix="doc")
    context = {'usuario_form': usuario_form, 'docente_form': docente_form, 'titulo': f'Editar Docente: {usuario.get_full_name() or usuario.username}', 'docente_obj': docente}
    return render(request, 'gestion_academica/docente_formulario.html', context)

class DocenteDeleteView(LoginRequiredMixin, DeleteView):
    model = Docente
    template_name = 'gestion_academica/docente_confirmar_eliminar.html'
    success_url = reverse_lazy('gestion_academica:lista_docentes')
    context_object_name = 'docente'
    def delete(self, request, *args, **kwargs):
        docente_obj = self.get_object()
        nombre_completo = docente_obj.usuario.get_full_name() or docente_obj.usuario.username
        messages.success(request, f"El docente '{nombre_completo}' y su cuenta de usuario han sido eliminados.")
        return super().delete(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Confirmar Eliminación de Docente"
        return context

# --- Vistas para Materias ---
class MateriaListView(LoginRequiredMixin, ListView):
    model = Materia
    template_name = 'gestion_academica/materia_lista.html'
    context_object_name = 'materias'
    paginate_by = 15
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Listado de Materias"
        return context

class MateriaCreateView(LoginRequiredMixin, CreateView):
    model = Materia
    form_class = MateriaForm
    template_name = 'gestion_academica/materia_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_materias')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Crear Nueva Materia"
        return context
    def form_valid(self, form):
        messages.success(self.request, f"Materia '{form.cleaned_data['nombre_materia']}' creada exitosamente.")
        return super().form_valid(form)

class MateriaUpdateView(LoginRequiredMixin, UpdateView):
    model = Materia
    form_class = MateriaForm
    template_name = 'gestion_academica/materia_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_materias')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Editar Materia"
        return context
    def form_valid(self, form):
        messages.success(self.request, f"Materia '{form.cleaned_data['nombre_materia']}' actualizada exitosamente.")
        return super().form_valid(form)

class MateriaDeleteView(LoginRequiredMixin, DeleteView):
    model = Materia
    template_name = 'gestion_academica/materia_confirmar_eliminar.html'
    success_url = reverse_lazy('gestion_academica:lista_materias')
    context_object_name = 'materia'
    def delete(self, request, *args, **kwargs):
        materia_eliminada = self.get_object()
        messages.success(request, f"La materia '{materia_eliminada.nombre_materia}' ha sido eliminada exitosamente.")
        return super().delete(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Confirmar Eliminación de Materia"
        return context

# --- Vistas para Periodos Académicos ---
class PeriodoAcademicoListView(LoginRequiredMixin, ListView):
    model = PeriodoAcademico
    template_name = 'gestion_academica/periodo_lista.html'
    context_object_name = 'periodos'
    paginate_by = 10
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Listado de Periodos Académicos"
        return context

class PeriodoAcademicoCreateView(LoginRequiredMixin, CreateView):
    model = PeriodoAcademico
    form_class = PeriodoAcademicoForm
    template_name = 'gestion_academica/periodo_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_periodos')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Crear Nuevo Periodo Académico"
        return context
    def form_valid(self, form):
        if form.cleaned_data.get('activo'):
            PeriodoAcademico.objects.filter(activo=True).update(activo=False)
        messages.success(self.request, f"Periodo Académico '{form.cleaned_data['nombre']}' creado exitosamente.")
        return super().form_valid(form)

class PeriodoAcademicoUpdateView(LoginRequiredMixin, UpdateView):
    model = PeriodoAcademico
    form_class = PeriodoAcademicoForm
    template_name = 'gestion_academica/periodo_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_periodos')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Editar Periodo Académico"
        return context
    def form_valid(self, form):
        if form.cleaned_data.get('activo'):
            PeriodoAcademico.objects.exclude(pk=self.object.pk).filter(activo=True).update(activo=False)
        messages.success(self.request, f"Periodo Académico '{form.cleaned_data['nombre']}' actualizado exitosamente.")
        return super().form_valid(form)

class PeriodoAcademicoDeleteView(LoginRequiredMixin, DeleteView):
    model = PeriodoAcademico
    template_name = 'gestion_academica/periodo_confirmar_eliminar.html'
    success_url = reverse_lazy('gestion_academica:lista_periodos')
    context_object_name = 'periodo'
    def delete(self, request, *args, **kwargs):
        periodo_eliminado = self.get_object()
        messages.success(request, f"El Periodo Académico '{periodo_eliminado.nombre}' ha sido eliminado exitosamente.")
        return super().delete(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Confirmar Eliminación de Periodo Académico"
        return context

# --- Vistas para Cursos ---
class CursoListView(LoginRequiredMixin, ListView):
    model = Curso
    template_name = 'gestion_academica/curso_lista.html'
    context_object_name = 'cursos'
    paginate_by = 10
    def get_queryset(self):
        return Curso.objects.select_related('materia', 'grado', 'periodo_academico').prefetch_related('docentes_asignados__usuario').all().order_by(
            '-periodo_academico__año_escolar', '-periodo_academico__fecha_inicio', 'grado__nombre', 'materia__nombre_materia'
        )
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Listado de Cursos"
        return context

class CursoDetailView(LoginRequiredMixin, DetailView):
    model = Curso
    template_name = 'gestion_academica/curso_detalle.html'
    context_object_name = 'curso'
    def get_queryset(self):
        return super().get_queryset().select_related('materia', 'grado', 'periodo_academico').prefetch_related('docentes_asignados__usuario')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f"Detalle del Curso: {self.object}"
        return context

class CursoCreateView(LoginRequiredMixin, CreateView):
    model = Curso
    form_class = CursoForm
    template_name = 'gestion_academica/curso_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_cursos')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Crear Nuevo Curso"
        return context
    def form_valid(self, form):
        messages.success(self.request, f"Curso '{form.instance}' creado exitosamente.")
        return super().form_valid(form)

class CursoUpdateView(LoginRequiredMixin, UpdateView):
    model = Curso
    form_class = CursoForm
    template_name = 'gestion_academica/curso_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_cursos')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Editar Curso"
        return context
    def form_valid(self, form):
        messages.success(self.request, f"Curso '{form.instance}' actualizado exitosamente.")
        return super().form_valid(form)

class CursoDeleteView(LoginRequiredMixin, DeleteView):
    model = Curso
    template_name = 'gestion_academica/curso_confirmar_eliminar.html'
    success_url = reverse_lazy('gestion_academica:lista_cursos')
    context_object_name = 'curso'
    def delete(self, request, *args, **kwargs):
        curso_eliminado = self.get_object()
        messages.success(request, f"El curso '{curso_eliminado}' ha sido eliminado exitosamente.")
        return super().delete(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Confirmar Eliminación de Curso"
        return context

# --- Vistas para Directores de Curso ---
class DirectorCursoListView(LoginRequiredMixin, ListView):
    model = DirectorCurso
    template_name = 'gestion_academica/director_curso_lista.html'
    context_object_name = 'directores_curso'
    paginate_by = 10
    def get_queryset(self):
        return DirectorCurso.objects.select_related(
            'docente__usuario', 'grado', 'periodo_academico'
        ).order_by(
            '-periodo_academico__año_escolar', '-periodo_academico__fecha_inicio', 'grado__nombre'
        )
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Listado de Directores de Curso"
        return context

class DirectorCursoCreateView(LoginRequiredMixin, CreateView):
    model = DirectorCurso
    form_class = DirectorCursoForm
    template_name = 'gestion_academica/director_curso_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_directores_curso')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Asignar Nuevo Director de Curso"
        return context
    def form_valid(self, form):
        messages.success(self.request, f"Director de curso asignado exitosamente.")
        return super().form_valid(form)

class DirectorCursoUpdateView(LoginRequiredMixin, UpdateView):
    model = DirectorCurso
    form_class = DirectorCursoForm
    template_name = 'gestion_academica/director_curso_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_directores_curso')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Editar Asignación de Director de Curso"
        return context
    def form_valid(self, form):
        messages.success(self.request, "Asignación de director de curso actualizada exitosamente.")
        return super().form_valid(form)

class DirectorCursoDeleteView(LoginRequiredMixin, DeleteView):
    model = DirectorCurso
    template_name = 'gestion_academica/director_curso_confirmar_eliminar.html'
    success_url = reverse_lazy('gestion_academica:lista_directores_curso')
    context_object_name = 'director_curso'
    def delete(self, request, *args, **kwargs):
        director_eliminado = self.get_object()
        messages.success(request, f"La asignación del director '{director_eliminado.docente}' para el grado '{director_eliminado.grado}' ha sido eliminada.")
        return super().delete(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Confirmar Eliminación de Asignación"
        return context

# --- Vistas para Esquemas de Calificación ---
class EsquemaCalificacionListView(LoginRequiredMixin, ListView):
    model = EsquemaCalificacion
    template_name = 'gestion_academica/esquema_calificacion_lista.html'
    context_object_name = 'esquemas'
    paginate_by = 10
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Esquemas de Calificación"
        return context

class EsquemaCalificacionCreateView(LoginRequiredMixin, CreateView):
    model = EsquemaCalificacion
    form_class = EsquemaCalificacionForm
    template_name = 'gestion_academica/esquema_calificacion_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_esquemas_calificacion')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Crear Nuevo Esquema de Calificación"
        return context
    def form_valid(self, form):
        messages.success(self.request, f"Esquema '{form.cleaned_data['nombre']}' creado exitosamente.")
        return super().form_valid(form)

class EsquemaCalificacionUpdateView(LoginRequiredMixin, UpdateView):
    model = EsquemaCalificacion
    form_class = EsquemaCalificacionForm
    template_name = 'gestion_academica/esquema_calificacion_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_esquemas_calificacion')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Editar Esquema de Calificación"
        return context
    def form_valid(self, form):
        messages.success(self.request, f"Esquema '{form.cleaned_data['nombre']}' actualizado exitosamente.")
        return super().form_valid(form)

class EsquemaCalificacionDeleteView(LoginRequiredMixin, DeleteView):
    model = EsquemaCalificacion
    template_name = 'gestion_academica/esquema_calificacion_confirmar_eliminar.html'
    success_url = reverse_lazy('gestion_academica:lista_esquemas_calificacion')
    context_object_name = 'esquema'
    def delete(self, request, *args, **kwargs):
        esquema_eliminado = self.get_object()
        messages.success(request, f"El esquema '{esquema_eliminado.nombre}' ha sido eliminado.")
        return super().delete(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Confirmar Eliminación de Esquema"
        return context

# --- Vistas para Tipos de Actividad ---
class TipoActividadListView(LoginRequiredMixin, ListView):
    model = TipoActividad
    template_name = 'gestion_academica/tipo_actividad_lista.html'
    context_object_name = 'tipos_actividad'
    paginate_by = 10
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Tipos de Actividad Evaluativa"
        return context

class TipoActividadCreateView(LoginRequiredMixin, CreateView):
    model = TipoActividad
    form_class = TipoActividadForm
    template_name = 'gestion_academica/tipo_actividad_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_tipos_actividad')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Crear Nuevo Tipo de Actividad"
        return context
    def form_valid(self, form):
        messages.success(self.request, f"Tipo de actividad '{form.cleaned_data['nombre']}' creado exitosamente.")
        return super().form_valid(form)

class TipoActividadUpdateView(LoginRequiredMixin, UpdateView):
    model = TipoActividad
    form_class = TipoActividadForm
    template_name = 'gestion_academica/tipo_actividad_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_tipos_actividad')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Editar Tipo de Actividad"
        return context
    def form_valid(self, form):
        messages.success(self.request, f"Tipo de actividad '{form.cleaned_data['nombre']}' actualizado exitosamente.")
        return super().form_valid(form)

class TipoActividadDeleteView(LoginRequiredMixin, DeleteView):
    model = TipoActividad
    template_name = 'gestion_academica/tipo_actividad_confirmar_eliminar.html'
    success_url = reverse_lazy('gestion_academica:lista_tipos_actividad')
    context_object_name = 'tipo_actividad'
    def delete(self, request, *args, **kwargs):
        tipo_eliminado = self.get_object()
        messages.success(request, f"El tipo de actividad '{tipo_eliminado.nombre}' ha sido eliminado.")
        return super().delete(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Confirmar Eliminación de Tipo de Actividad"
        return context

# --- Vistas para Actividades Calificables ---
class ActividadCalificableListView(LoginRequiredMixin, ListView):
    model = ActividadCalificable
    template_name = 'gestion_academica/actividad_calificable_lista.html'
    context_object_name = 'actividades'
    paginate_by = 10
    def get_queryset(self):
        return ActividadCalificable.objects.select_related(
            'curso__materia', 'curso__grado', 'curso__periodo_academico', 'tipo_actividad'
        ).order_by('-curso__periodo_academico__año_escolar', '-curso__periodo_academico__fecha_inicio', 'curso__grado', 'curso__materia', '-fecha_publicacion')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Listado de Actividades Calificables"
        return context

class ActividadCalificableDetailView(LoginRequiredMixin, DetailView):
    model = ActividadCalificable
    template_name = 'gestion_academica/actividad_calificable_detalle.html'
    context_object_name = 'actividad'
    def get_queryset(self):
        return super().get_queryset().select_related(
            'curso__materia', 'curso__grado', 'curso__periodo_academico', 'tipo_actividad'
        )
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f"Detalle: {self.object.titulo}"
        return context

class ActividadCalificableCreateView(LoginRequiredMixin, CreateView):
    model = ActividadCalificable
    form_class = ActividadCalificableForm
    template_name = 'gestion_academica/actividad_calificable_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_actividades_calificables')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Crear Nueva Actividad Calificable"
        return context
    def form_valid(self, form):
        messages.success(self.request, f"Actividad '{form.cleaned_data['titulo']}' creada exitosamente.")
        return super().form_valid(form)

class ActividadCalificableUpdateView(LoginRequiredMixin, UpdateView):
    model = ActividadCalificable
    form_class = ActividadCalificableForm
    template_name = 'gestion_academica/actividad_calificable_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_actividades_calificables')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Editar Actividad Calificable"
        return context
    def form_valid(self, form):
        messages.success(self.request, f"Actividad '{form.cleaned_data['titulo']}' actualizada exitosamente.")
        return super().form_valid(form)

class ActividadCalificableDeleteView(LoginRequiredMixin, DeleteView):
    model = ActividadCalificable
    template_name = 'gestion_academica/actividad_calificable_confirmar_eliminar.html'
    success_url = reverse_lazy('gestion_academica:lista_actividades_calificables')
    context_object_name = 'actividad'
    def delete(self, request, *args, **kwargs):
        actividad_eliminada = self.get_object()
        messages.success(request, f"La actividad '{actividad_eliminada.titulo}' ha sido eliminada.")
        return super().delete(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Confirmar Eliminación de Actividad"
        return context

# --- Vistas para Deberes (Tareas) ---
class DeberListView(LoginRequiredMixin, ListView):
    model = Deber
    template_name = 'gestion_academica/deber_lista.html'
    context_object_name = 'deberes'
    paginate_by = 10
    def get_queryset(self):
        return Deber.objects.select_related(
            'curso__materia', 'curso__grado', 'curso__periodo_academico'
        ).order_by('-curso__periodo_academico__año_escolar', 'curso__grado', 'curso__materia', '-fecha_entrega')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Listado de Deberes / Tareas"
        return context

class DeberDetailView(LoginRequiredMixin, DetailView):
    model = Deber
    template_name = 'gestion_academica/deber_detalle.html'
    context_object_name = 'deber'
    def get_queryset(self):
        return super().get_queryset().select_related(
            'curso__materia', 'curso__grado', 'curso__periodo_academico'
        )
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f"Detalle del Deber: {self.object.titulo}"
        return context

class DeberCreateView(LoginRequiredMixin, CreateView):
    model = Deber
    form_class = DeberForm
    template_name = 'gestion_academica/deber_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_deberes')
    def form_valid(self, form):
        messages.success(self.request, f"Deber '{form.cleaned_data['titulo']}' creado exitosamente.")
        return super().form_valid(form)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Crear Nuevo Deber / Tarea"
        return context

class DeberUpdateView(LoginRequiredMixin, UpdateView):
    model = Deber
    form_class = DeberForm
    template_name = 'gestion_academica/deber_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_deberes')
    def form_valid(self, form):
        messages.success(self.request, f"Deber '{form.cleaned_data['titulo']}' actualizado exitosamente.")
        return super().form_valid(form)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Editar Deber / Tarea"
        return context

class DeberDeleteView(LoginRequiredMixin, DeleteView):
    model = Deber
    template_name = 'gestion_academica/deber_confirmar_eliminar.html'
    success_url = reverse_lazy('gestion_academica:lista_deberes')
    context_object_name = 'deber'
    def delete(self, request, *args, **kwargs):
        deber_eliminado = self.get_object()
        messages.success(request, f"El deber '{deber_eliminado.titulo}' ha sido eliminado.")
        return super().delete(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Confirmar Eliminación de Deber"
        return context

# --- Vistas para Estudiantes - Visualización de Calificaciones ---
@login_required
def mis_cursos_y_calificaciones_resumen(request):
    try:
        estudiante_actual = request.user.estudiante
    except Estudiante.DoesNotExist:
        messages.error(request, "Tu perfil de estudiante no está configurado correctamente.")
        return redirect('gestion_academica:inicio_academico')
    if not estudiante_actual.grado_actual:
        messages.info(request, "Aún no estás asignado a un grado.")
        context = {'titulo_pagina': "Mis Cursos y Calificaciones", 'cursos': [], 'periodo_activo': None, 'estudiante': estudiante_actual}
        return render(request, 'gestion_academica/estudiante_mis_cursos_calificaciones.html', context)
    periodo_activo = PeriodoAcademico.objects.filter(activo=True).first()
    if not periodo_activo:
        messages.warning(request, "No hay un periodo académico activo definido en el sistema.")
        cursos_del_estudiante = Curso.objects.none()
    else:
        cursos_del_estudiante = Curso.objects.filter(
            grado=estudiante_actual.grado_actual,
            periodo_academico=periodo_activo
        ).select_related('materia', 'grado', 'periodo_academico').prefetch_related('docentes_asignados__usuario').order_by('materia__nombre_materia')
    context = {'titulo_pagina': "Mis Cursos y Calificaciones", 'cursos': cursos_del_estudiante, 'periodo_activo': periodo_activo, 'estudiante': estudiante_actual}
    return render(request, 'gestion_academica/estudiante_mis_cursos_calificaciones.html', context)

@login_required
def detalle_mis_calificaciones_por_curso(request, curso_pk):
    try:
        estudiante_actual = request.user.estudiante
    except Estudiante.DoesNotExist:
        messages.error(request, "Tu perfil de estudiante no está configurado correctamente.")
        return redirect('gestion_academica:inicio_academico')
    curso = get_object_or_404(Curso.objects.select_related('materia', 'grado', 'periodo_academico'), pk=curso_pk)
    if estudiante_actual.grado_actual != curso.grado:
        messages.error(request, "No tienes permiso para ver las calificaciones de este curso.")
        return redirect('gestion_academica:mis_cursos_calificaciones')
    actividades_del_curso = ActividadCalificable.objects.filter(curso=curso).order_by('fecha_publicacion', 'titulo')
    calificaciones_del_estudiante = Calificacion.objects.filter(estudiante=estudiante_actual, actividad_calificable__in=actividades_del_curso).select_related('actividad_calificable')
    calificaciones_por_actividad = {cal.actividad_calificable_id: cal for cal in calificaciones_del_estudiante}
    actividades_con_calificacion = [{'actividad': act, 'calificacion': calificaciones_por_actividad.get(act.pk)} for act in actividades_del_curso]
    context = {'titulo_pagina': f"Mis Calificaciones en: {curso.materia.nombre_materia}", 'curso': curso, 'actividades_con_calificacion': actividades_con_calificacion, 'estudiante': estudiante_actual}
    return render(request, 'gestion_academica/estudiante_detalle_calificaciones_curso.html', context)

# --- Vistas para Estudiantes - Entrega de Deberes ---
@login_required
def mis_deberes_lista(request):
    try:
        estudiante_actual = request.user.estudiante
    except Estudiante.DoesNotExist:
        messages.error(request, "Tu perfil de estudiante no está configurado correctamente.")
        return redirect('gestion_academica:inicio_academico')
    if not estudiante_actual.grado_actual:
        messages.info(request, "Aún no estás asignado a un grado, por lo que no tienes deberes asignados.")
        context = {'titulo_pagina': "Mis Deberes", 'deberes_con_estado_entrega': []}
        return render(request, 'gestion_academica/estudiante_mis_deberes_lista.html', context)
    periodo_activo = PeriodoAcademico.objects.filter(activo=True).first()
    if not periodo_activo:
        messages.warning(request, "No hay un periodo académico activo. No se pueden mostrar deberes.")
        context = {'titulo_pagina': "Mis Deberes", 'deberes_con_estado_entrega': []}
        return render(request, 'gestion_academica/estudiante_mis_deberes_lista.html', context)
    cursos_del_estudiante = Curso.objects.filter(grado=estudiante_actual.grado_actual, periodo_academico=periodo_activo)
    deberes_asignados = Deber.objects.filter(curso__in=cursos_del_estudiante).select_related('curso__materia', 'curso__grado').order_by('-fecha_entrega')
    entregas_realizadas_ids = EntregaDeber.objects.filter(estudiante=estudiante_actual, deber__in=deberes_asignados).values_list('deber_id', flat=True)
    deberes_con_estado_entrega = [{'deber': deber, 'entregado': deber.id in entregas_realizadas_ids} for deber in deberes_asignados]
    context = {'titulo_pagina': "Mis Deberes / Tareas Asignadas", 'deberes_con_estado_entrega': deberes_con_estado_entrega, 'periodo_activo': periodo_activo}
    return render(request, 'gestion_academica/estudiante_mis_deberes_lista.html', context)

@login_required
def realizar_entrega_deber(request, deber_pk):
    try:
        estudiante_actual = request.user.estudiante
    except Estudiante.DoesNotExist:
        messages.error(request, "Tu perfil de estudiante no está configurado correctamente.")
        return redirect('gestion_academica:inicio_academico')
    deber = get_object_or_404(Deber.objects.select_related('curso__grado'), pk=deber_pk)
    if estudiante_actual.grado_actual != deber.curso.grado:
        messages.error(request, "No tienes permiso para realizar una entrega para este deber.")
        return redirect('gestion_academica:mis_deberes_lista')
    entrega_obj, created = EntregaDeber.objects.get_or_create(deber=deber, estudiante=estudiante_actual)
    esta_vencido = timezone.now().date() > deber.fecha_entrega
    if esta_vencido and created :
        messages.warning(request, f"La fecha límite de entrega para el deber '{deber.titulo}' ya ha pasado. No puedes realizar una nueva entrega.")
        return redirect('gestion_academica:mis_deberes_lista')
    if request.method == 'POST':
        form = EntregaDeberForm(request.POST, request.FILES, instance=entrega_obj)
        if form.is_valid():
            entrega_guardada = form.save(commit=False)
            entrega_guardada.deber = deber 
            entrega_guardada.estudiante = estudiante_actual
            if not created:
                entrega_guardada.fecha_entrega_real = timezone.now()
            entrega_guardada.save()
            messages.success(request, f"Entrega para el deber '{deber.titulo}' guardada exitosamente.")
            return redirect('gestion_academica:mis_deberes_lista')
        else:
            messages.error(request, "Error al guardar la entrega. Por favor, revisa el formulario.")
    else:
        form = EntregaDeberForm(instance=entrega_obj)
    context = {'form': form, 'deber': deber, 'entrega_existente': entrega_obj if not created else None, 'titulo_formulario': f"{'Actualizar' if not created else 'Realizar'} Entrega para: {deber.titulo}", 'esta_vencido_para_nueva_entrega': esta_vencido and created}
    return render(request, 'gestion_academica/estudiante_realizar_entrega_deber.html', context)

# --- Vistas para Registro de Calificaciones ---
@login_required
def listar_estudiantes_para_calificar(request, actividad_pk):
    actividad = get_object_or_404(ActividadCalificable.objects.select_related('curso__grado', 'curso__materia', 'curso__periodo_academico'), pk=actividad_pk)
    estudiantes_del_grado = Estudiante.objects.filter(grado_actual=actividad.curso.grado).select_related('usuario').order_by('usuario__last_name', 'usuario__first_name')
    calificaciones_existentes = Calificacion.objects.filter(actividad_calificable=actividad).select_related('estudiante')
    calificaciones_por_estudiante = {cal.estudiante_id: cal for cal in calificaciones_existentes}
    estudiantes_con_calificacion = [{'estudiante': est, 'calificacion': calificaciones_por_estudiante.get(est.pk)} for est in estudiantes_del_grado]
    context = {'actividad': actividad, 'estudiantes_con_calificacion': estudiantes_con_calificacion, 'titulo_pagina': f"Calificar: {actividad.titulo}"}
    return render(request, 'gestion_academica/actividad_calificar_estudiantes.html', context)

@login_required
def registrar_editar_calificacion(request, actividad_pk, estudiante_pk):
    actividad = get_object_or_404(ActividadCalificable, pk=actividad_pk)
    estudiante = get_object_or_404(Estudiante, pk=estudiante_pk)
    calificacion_obj, created = Calificacion.objects.get_or_create(
        actividad_calificable=actividad,
        estudiante=estudiante,
        defaults={'registrada_por': request.user.docente if hasattr(request.user, 'docente') else None}
    )
    if request.method == 'POST':
        form = CalificacionForm(request.POST, instance=calificacion_obj)
        if form.is_valid():
            calificacion_guardada = form.save(commit=False)
            calificacion_guardada.actividad_calificable = actividad
            calificacion_guardada.estudiante = estudiante
            if hasattr(request.user, 'docente'):
                 calificacion_guardada.registrada_por = request.user.docente
            calificacion_guardada.save()
            messages.success(request, f"Calificación para {estudiante.usuario.get_full_name()} en '{actividad.titulo}' guardada exitosamente.")
            return redirect('gestion_academica:listar_estudiantes_para_calificar', actividad_pk=actividad.pk)
        else:
            messages.error(request, "Error al guardar la calificación. Por favor, revisa el formulario.")
    else:
        form = CalificacionForm(instance=calificacion_obj)
    context = {'form': form, 'actividad': actividad, 'estudiante': estudiante, 'titulo_formulario': f"Calificar a {estudiante.usuario.get_full_name()} en '{actividad.titulo}'"}
    return render(request, 'gestion_academica/calificacion_formulario.html', context)

# --- Vistas para Planes Curriculares ---
class PlanCurricularListView(LoginRequiredMixin, ListView):
    model = PlanCurricular
    template_name = 'gestion_academica/plan_curricular_lista.html'
    context_object_name = 'planes'
    paginate_by = 10
    def get_queryset(self):
        return PlanCurricular.objects.select_related(
            'grado_asociado', 'materia_asociada', 'periodo_academico_asociado', 'creado_por'
        ).order_by('-fecha_publicacion', 'nombre')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Planes Curriculares"
        return context

class PlanCurricularDetailView(LoginRequiredMixin, DetailView):
    model = PlanCurricular
    template_name = 'gestion_academica/plan_curricular_detalle.html'
    context_object_name = 'plan'
    def get_queryset(self):
        return super().get_queryset().select_related(
            'grado_asociado', 'materia_asociada', 'periodo_academico_asociado', 'creado_por'
        )
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = f"Detalle: {self.object.nombre}"
        return context

class PlanCurricularCreateView(LoginRequiredMixin, CreateView):
    model = PlanCurricular
    form_class = PlanCurricularForm
    template_name = 'gestion_academica/plan_curricular_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_planes_curriculares')
    def form_valid(self, form):
        form.instance.creado_por = self.request.user
        messages.success(self.request, f"Plan Curricular '{form.cleaned_data['nombre']}' creado exitosamente.")
        return super().form_valid(form)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Crear Nuevo Plan Curricular"
        return context

class PlanCurricularUpdateView(LoginRequiredMixin, UpdateView):
    model = PlanCurricular
    form_class = PlanCurricularForm
    template_name = 'gestion_academica/plan_curricular_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_planes_curriculares')
    def form_valid(self, form):
        messages.success(self.request, f"Plan Curricular '{form.cleaned_data['nombre']}' actualizado exitosamente.")
        return super().form_valid(form)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Editar Plan Curricular"
        return context

class PlanCurricularDeleteView(LoginRequiredMixin, DeleteView):
    model = PlanCurricular
    template_name = 'gestion_academica/plan_curricular_confirmar_eliminar.html'
    success_url = reverse_lazy('gestion_academica:lista_planes_curriculares')
    context_object_name = 'plan'
    def delete(self, request, *args, **kwargs):
        plan_eliminado = self.get_object()
        messages.success(request, f"El Plan Curricular '{plan_eliminado.nombre}' ha sido eliminado.")
        return super().delete(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Confirmar Eliminación de Plan Curricular"
        return context

# --- Vistas para Menciones y Reconocimientos ---
class MencionReconocimientoListView(LoginRequiredMixin, ListView):
    model = MencionReconocimiento
    template_name = 'gestion_academica/mencion_lista.html'
    context_object_name = 'menciones'
    paginate_by = 10
    def get_queryset(self):
        return MencionReconocimiento.objects.select_related(
            'estudiante__usuario', 'curso__materia', 'periodo', 'otorgado_por__usuario'
        ).order_by('-fecha_otorgamiento', 'estudiante__usuario__last_name')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Menciones y Reconocimientos"
        return context

class MencionReconocimientoCreateView(LoginRequiredMixin, CreateView):
    model = MencionReconocimiento
    form_class = MencionReconocimientoForm
    template_name = 'gestion_academica/mencion_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_menciones')
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    def form_valid(self, form):
        if not form.cleaned_data.get('otorgado_por') and hasattr(self.request.user, 'docente'):
            form.instance.otorgado_por = self.request.user.docente
        messages.success(self.request, f"Mención/Reconocimiento para '{form.cleaned_data['estudiante']}' creado exitosamente.")
        return super().form_valid(form)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Registrar Nueva Mención o Reconocimiento"
        return context

class MencionReconocimientoUpdateView(LoginRequiredMixin, UpdateView):
    model = MencionReconocimiento
    form_class = MencionReconocimientoForm
    template_name = 'gestion_academica/mencion_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_menciones')
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    def form_valid(self, form):
        messages.success(self.request, f"Mención/Reconocimiento para '{form.cleaned_data['estudiante']}' actualizado exitosamente.")
        return super().form_valid(form)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Editar Mención o Reconocimiento"
        return context

class MencionReconocimientoDeleteView(LoginRequiredMixin, DeleteView):
    model = MencionReconocimiento
    template_name = 'gestion_academica/mencion_confirmar_eliminar.html'
    success_url = reverse_lazy('gestion_academica:lista_menciones')
    context_object_name = 'mencion'
    def delete(self, request, *args, **kwargs):
        mencion_eliminada = self.get_object()
        messages.success(request, f"La mención/reconocimiento para '{mencion_eliminada.estudiante}' ha sido eliminada.")
        return super().delete(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Confirmar Eliminación de Mención/Reconocimiento"
        return context

# --- Vistas para Archivos de Planes Académicos y Materiales ---
class ArchivoPlanAcademicoListView(LoginRequiredMixin, ListView):
    model = ArchivoPlanAcademico
    template_name = 'gestion_academica/archivo_plan_lista.html'
    context_object_name = 'archivos'
    paginate_by = 10
    def get_queryset(self):
        return ArchivoPlanAcademico.objects.select_related(
            'curso_asociado__materia', 'curso_asociado__grado', 
            'materia_asociada', 'subido_por'
        ).order_by('-fecha_subida')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Materiales y Planes Académicos"
        return context

class ArchivoPlanAcademicoCreateView(LoginRequiredMixin, CreateView):
    model = ArchivoPlanAcademico
    form_class = ArchivoPlanAcademicoForm
    template_name = 'gestion_academica/archivo_plan_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_archivos_plan')
    def form_valid(self, form):
        form.instance.subido_por = self.request.user
        messages.success(self.request, f"Archivo '{form.cleaned_data['nombre_archivo_descriptivo']}' subido exitosamente.")
        return super().form_valid(form)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Subir Nuevo Archivo/Material"
        return context

class ArchivoPlanAcademicoUpdateView(LoginRequiredMixin, UpdateView):
    model = ArchivoPlanAcademico
    form_class = ArchivoPlanAcademicoForm
    template_name = 'gestion_academica/archivo_plan_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_archivos_plan')
    def form_valid(self, form):
        messages.success(self.request, f"Archivo '{form.cleaned_data['nombre_archivo_descriptivo']}' actualizado exitosamente.")
        return super().form_valid(form)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Editar Archivo/Material"
        return context

class ArchivoPlanAcademicoDeleteView(LoginRequiredMixin, DeleteView):
    model = ArchivoPlanAcademico
    template_name = 'gestion_academica/archivo_plan_confirmar_eliminar.html'
    success_url = reverse_lazy('gestion_academica:lista_archivos_plan')
    context_object_name = 'archivo_plan'
    def delete(self, request, *args, **kwargs):
        archivo_eliminado = self.get_object()
        nombre_archivo = archivo_eliminado.nombre_archivo_descriptivo
        messages.success(request, f"El archivo '{nombre_archivo}' ha sido eliminado.")
        return super().delete(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Confirmar Eliminación de Archivo"
        return context

# --- Vistas para Estudiantes - Mi Boletín ---
@login_required
def mi_boletin_periodo_actual(request):
    try:
        estudiante_actual = request.user.estudiante
    except Estudiante.DoesNotExist:
        messages.error(request, "Tu perfil de estudiante no está configurado correctamente.")
        return redirect('gestion_academica:inicio_academico')

    if not estudiante_actual.grado_actual:
        messages.info(request, "Aún no estás asignado a un grado, por lo que no se puede generar tu boletín.")
        context = {'titulo_pagina': "Mi Boletín de Calificaciones", 'estudiante': estudiante_actual, 'periodo_activo': None, 'cursos_con_detalle': []}
        return render(request, 'gestion_academica/estudiante_mi_boletin.html', context)

    periodo_activo = PeriodoAcademico.objects.filter(activo=True).first()
    if not periodo_activo:
        messages.warning(request, "No hay un periodo académico activo definido en el sistema para generar el boletín.")
        context = {'titulo_pagina': "Mi Boletín de Calificaciones", 'estudiante': estudiante_actual, 'periodo_activo': None, 'cursos_con_detalle': []}
        return render(request, 'gestion_academica/estudiante_mi_boletin.html', context)

    cursos_del_estudiante = Curso.objects.filter(
        grado=estudiante_actual.grado_actual,
        periodo_academico=periodo_activo
    ).select_related('materia', 'grado', 'periodo_academico').prefetch_related('docentes_asignados__usuario').order_by('materia__nombre_materia')

    cursos_con_detalle = []
    promedio_general_periodo_numerador = 0
    promedio_general_periodo_denominador = 0

    for curso_iter in cursos_del_estudiante:
        actividades_del_curso = ActividadCalificable.objects.filter(curso=curso_iter).order_by('fecha_publicacion', 'titulo')
        calificaciones_del_estudiante = Calificacion.objects.filter(
            estudiante=estudiante_actual,
            actividad_calificable__in=actividades_del_curso,
            valor_numerico__isnull=False
        ).select_related('actividad_calificable')
        
        calificaciones_por_actividad = {cal.actividad_calificable_id: cal for cal in calificaciones_del_estudiante}
        actividades_para_boletin = []
        suma_notas_ponderadas_curso = 0
        suma_porcentajes_curso = 0

        for act in actividades_del_curso:
            calificacion_actual = calificaciones_por_actividad.get(act.pk)
            if calificacion_actual and calificacion_actual.valor_numerico is not None and act.porcentaje_en_periodo is not None:
                suma_notas_ponderadas_curso += (calificacion_actual.valor_numerico * act.porcentaje_en_periodo)
                suma_porcentajes_curso += act.porcentaje_en_periodo
            actividades_para_boletin.append({'actividad': act, 'calificacion': calificacion_actual})
        
        nota_final_curso = None
        if suma_porcentajes_curso > 0:
            nota_final_curso = suma_notas_ponderadas_curso / suma_porcentajes_curso
            promedio_general_periodo_numerador += nota_final_curso
            promedio_general_periodo_denominador += 1
        cursos_con_detalle.append({'curso': curso_iter, 'actividades_con_calificacion': actividades_para_boletin, 'nota_final_curso': nota_final_curso})

    promedio_general_calculado = None
    if promedio_general_periodo_denominador > 0:
        promedio_general_calculado = promedio_general_periodo_numerador / promedio_general_periodo_denominador

    context = {
        'titulo_pagina': f"Mi Boletín - {periodo_activo.nombre}",
        'estudiante': estudiante_actual,
        'periodo_activo': periodo_activo,
        'cursos_con_detalle': cursos_con_detalle,
        'promedio_general_periodo': promedio_general_calculado
    }
    return render(request, 'gestion_academica/estudiante_mi_boletin.html', context)

# --- Vistas para Portal de Familiares ---
@login_required
def portal_familiar_inicio(request):
    familiar_actual = None
    if hasattr(request.user, 'familiar_profile'): 
        familiar_actual = request.user.familiar_profile
    elif hasattr(request.user, 'familiar'): 
        familiar_actual = request.user.familiar
    else:
        try: 
            familiar_actual = Familiar.objects.get(usuario=request.user)
        except Familiar.DoesNotExist:
            messages.error(request, "Acceso denegado o perfil de familiar no configurado.")
            return redirect('gestion_academica:inicio_academico')
        
    estudiantes_a_cargo = familiar_actual.estudiantes_asociados.select_related('usuario', 'grado_actual').order_by('usuario__last_name', 'usuario__first_name')

    context = {
        'titulo_pagina': "Portal de Familiares",
        'familiar': familiar_actual,
        'estudiantes_a_cargo': estudiantes_a_cargo,
    }
    return render(request, 'gestion_academica/familiar_portal_inicio.html', context)

@login_required
def familiar_ver_calificaciones_estudiante(request, estudiante_pk):
    familiar_actual = None
    if hasattr(request.user, 'familiar_profile'):
        familiar_actual = request.user.familiar_profile
    elif hasattr(request.user, 'familiar'):
        familiar_actual = request.user.familiar
    else:
        try:
            familiar_actual = Familiar.objects.get(usuario=request.user)
        except Familiar.DoesNotExist:
            messages.error(request, "Acceso denegado.")
            return redirect('gestion_academica:inicio_academico')
        
    estudiante = get_object_or_404(Estudiante.objects.select_related('usuario', 'grado_actual'), pk=estudiante_pk)

    if not familiar_actual.estudiantes_asociados.filter(pk=estudiante.pk).exists():
        messages.error(request, "No tienes permiso para ver la información de este estudiante.")
        return redirect('gestion_academica:portal_familiar_inicio')
    
    periodo_activo = PeriodoAcademico.objects.filter(activo=True).first()
    cursos_del_estudiante = []
    if estudiante.grado_actual and periodo_activo:
        cursos_del_estudiante = Curso.objects.filter(
            grado=estudiante.grado_actual,
            periodo_academico=periodo_activo
        ).select_related('materia', 'grado', 'periodo_academico').prefetch_related('docentes_asignados__usuario').order_by('materia__nombre_materia')

    context = {
        'titulo_pagina': f"Calificaciones de {estudiante.usuario.get_full_name()}",
        'estudiante_seleccionado': estudiante,
        'cursos': cursos_del_estudiante,
        'periodo_activo': periodo_activo,
        'es_vista_familiar': True,
        'estudiante': estudiante, 
    }
    return render(request, 'gestion_academica/estudiante_mis_cursos_calificaciones.html', context)

@login_required
def familiar_ver_detalle_calificaciones_curso_estudiante(request, estudiante_pk, curso_pk):
    familiar_actual = None
    if hasattr(request.user, 'familiar_profile'):
        familiar_actual = request.user.familiar_profile
    elif hasattr(request.user, 'familiar'):
        familiar_actual = request.user.familiar
    else:
        try:
            familiar_actual = Familiar.objects.get(usuario=request.user)
        except Familiar.DoesNotExist:
            messages.error(request, "Acceso denegado.")
            return redirect('gestion_academica:inicio_academico')

    estudiante = get_object_or_404(Estudiante.objects.select_related('usuario', 'grado_actual'), pk=estudiante_pk)
    curso = get_object_or_404(Curso.objects.select_related('materia', 'grado', 'periodo_academico'), pk=curso_pk)

    if not familiar_actual.estudiantes_asociados.filter(pk=estudiante.pk).exists() or \
       (estudiante.grado_actual and estudiante.grado_actual != curso.grado):
        messages.error(request, "No tienes permiso para ver esta información o el estudiante no pertenece a este curso.")
        return redirect('gestion_academica:portal_familiar_inicio')

    actividades_del_curso = ActividadCalificable.objects.filter(curso=curso).order_by('fecha_publicacion', 'titulo')
    calificaciones_del_estudiante = Calificacion.objects.filter(
        estudiante=estudiante,
        actividad_calificable__in=actividades_del_curso
    ).select_related('actividad_calificable')
    calificaciones_por_actividad = {cal.actividad_calificable_id: cal for cal in calificaciones_del_estudiante}
    actividades_con_calificacion = []
    for act in actividades_del_curso:
        actividades_con_calificacion.append({
            'actividad': act,
            'calificacion': calificaciones_por_actividad.get(act.pk)
        })
    
    context = {
        'titulo_pagina': f"Calificaciones de {estudiante.usuario.get_full_name()} en {curso.materia.nombre_materia}",
        'curso': curso,
        'actividades_con_calificacion': actividades_con_calificacion,
        'estudiante': estudiante, 
        'es_vista_familiar': True,
    }
    return render(request, 'gestion_academica/estudiante_detalle_calificaciones_curso.html', context)

@login_required
def familiar_ver_boletin_estudiante(request, estudiante_pk):
    familiar_actual = None
    if hasattr(request.user, 'familiar_profile'):
        familiar_actual = request.user.familiar_profile
    elif hasattr(request.user, 'familiar'):
        familiar_actual = request.user.familiar
    else:
        try:
            familiar_actual = Familiar.objects.get(usuario=request.user)
        except Familiar.DoesNotExist:
            messages.error(request, "Acceso denegado.")
            return redirect('gestion_academica:inicio_academico')
        
    estudiante_seleccionado = get_object_or_404(Estudiante.objects.select_related('usuario', 'grado_actual'), pk=estudiante_pk)

    if not familiar_actual.estudiantes_asociados.filter(pk=estudiante_seleccionado.pk).exists():
        messages.error(request, "No tienes permiso para ver el boletín de este estudiante.")
        return redirect('gestion_academica:portal_familiar_inicio')

    periodo_activo = PeriodoAcademico.objects.filter(activo=True).first()
    cursos_con_detalle = []
    promedio_general_periodo = None
    
    if estudiante_seleccionado.grado_actual and periodo_activo:
        cursos_del_estudiante = Curso.objects.filter(
            grado=estudiante_seleccionado.grado_actual,
            periodo_academico=periodo_activo
        ).select_related('materia', 'grado', 'periodo_academico').prefetch_related('docentes_asignados__usuario').order_by('materia__nombre_materia')

        suma_ponderada_total = 0
        suma_porcentajes_total = 0

        for curso_iter in cursos_del_estudiante:
            actividades_del_curso = ActividadCalificable.objects.filter(curso=curso_iter).order_by('fecha_publicacion', 'titulo')
            calificaciones_del_estudiante = Calificacion.objects.filter(
                estudiante=estudiante_seleccionado,
                actividad_calificable__in=actividades_del_curso,
                valor_numerico__isnull=False
            ).select_related('actividad_calificable')
            
            calificaciones_por_actividad = {cal.actividad_calificable_id: cal for cal in calificaciones_del_estudiante}
            actividades_para_boletin = []
            suma_notas_ponderadas_curso = 0
            suma_porcentajes_curso = 0

            for act in actividades_del_curso:
                calificacion_actual = calificaciones_por_actividad.get(act.pk)
                if calificacion_actual and calificacion_actual.valor_numerico is not None and act.porcentaje_en_periodo is not None:
                    suma_notas_ponderadas_curso += (calificacion_actual.valor_numerico * act.porcentaje_en_periodo)
                    suma_porcentajes_curso += act.porcentaje_en_periodo
                actividades_para_boletin.append({'actividad': act, 'calificacion': calificacion_actual})
            
            nota_final_curso = None
            if suma_porcentajes_curso > 0:
                nota_final_curso = suma_notas_ponderadas_curso / suma_porcentajes_curso
                promedio_general_periodo_numerador += nota_final_curso
                promedio_general_periodo_denominador += 1
            cursos_con_detalle.append({'curso': curso_iter, 'actividades_con_calificacion': actividades_para_boletin, 'nota_final_curso': nota_final_curso})

        if promedio_general_periodo_denominador > 0:
            promedio_general_periodo = promedio_general_periodo_numerador / promedio_general_periodo_denominador
    
    context = {
        'titulo_pagina': f"Boletín de {estudiante_seleccionado.usuario.get_full_name()}",
        'estudiante': estudiante_seleccionado,
        'periodo_activo': periodo_activo,
        'cursos_con_detalle': cursos_con_detalle,
        'promedio_general_periodo': promedio_general_periodo,
        'es_vista_familiar': True,
    }
    return render(request, 'gestion_academica/estudiante_mi_boletin.html', context)

@login_required
def familiar_ver_deberes_estudiante(request, estudiante_pk):
    familiar_actual = None
    if hasattr(request.user, 'familiar_profile'):
        familiar_actual = request.user.familiar_profile
    elif hasattr(request.user, 'familiar'):
        familiar_actual = request.user.familiar
    else:
        try:
            familiar_actual = Familiar.objects.get(usuario=request.user)
        except Familiar.DoesNotExist:
            messages.error(request, "Acceso denegado.")
            return redirect('gestion_academica:inicio_academico')
        
    estudiante_seleccionado = get_object_or_404(Estudiante.objects.select_related('usuario', 'grado_actual'), pk=estudiante_pk)

    if not familiar_actual.estudiantes_asociados.filter(pk=estudiante_seleccionado.pk).exists():
        messages.error(request, "No tienes permiso para ver los deberes de este estudiante.")
        return redirect('gestion_academica:portal_familiar_inicio')

    periodo_activo = PeriodoAcademico.objects.filter(activo=True).first()
    deberes_con_estado_entrega = []

    if estudiante_seleccionado.grado_actual and periodo_activo:
        cursos_del_estudiante = Curso.objects.filter(
            grado=estudiante_seleccionado.grado_actual,
            periodo_academico=periodo_activo
        )
        deberes_asignados = Deber.objects.filter(
            curso__in=cursos_del_estudiante
        ).select_related('curso__materia', 'curso__grado').order_by('-fecha_entrega')
        entregas_realizadas_ids = EntregaDeber.objects.filter(
            estudiante=estudiante_seleccionado,
            deber__in=deberes_asignados
        ).values_list('deber_id', flat=True)
        for deber in deberes_asignados:
            deberes_con_estado_entrega.append({
                'deber': deber,
                'entregado': deber.id in entregas_realizadas_ids,
                'puede_entregar': False 
            })
    
    context = {
        'titulo_pagina': f"Deberes de {estudiante_seleccionado.usuario.get_full_name()}",
        'deberes_con_estado_entrega': deberes_con_estado_entrega,
        'periodo_activo': periodo_activo,
        'estudiante_seleccionado': estudiante_seleccionado,
        'es_vista_familiar': True,
    }
    return render(request, 'gestion_academica/estudiante_mis_deberes_lista.html', context)

# --- Vistas para Docentes - Libro de Notas ---
@login_required
def docente_seleccionar_curso_libro_notas(request):
    if not hasattr(request.user, 'docente'):
        messages.error(request, "Acceso denegado. Esta sección es solo para docentes.")
        return redirect('gestion_academica:inicio_academico')

    docente_actual = request.user.docente
    periodo_activo = PeriodoAcademico.objects.filter(activo=True).first()

    if not periodo_activo:
        messages.warning(request, "No hay un periodo académico activo definido en el sistema.")
        cursos_asignados = Curso.objects.none()
    else:
        cursos_asignados = Curso.objects.filter(
            docentes_asignados=docente_actual,
            periodo_academico=periodo_activo
        ).select_related('materia', 'grado', 'periodo_academico').order_by('grado__nombre', 'materia__nombre_materia')

    context = {
        'titulo_pagina': "Seleccionar Curso - Libro de Notas",
        'cursos_asignados': cursos_asignados,
        'periodo_activo': periodo_activo,
    }
    return render(request, 'gestion_academica/docente_seleccionar_curso_libro_notas.html', context)

@login_required
def docente_libro_de_notas_por_curso(request, curso_pk):
    if not hasattr(request.user, 'docente'):
        messages.error(request, "Acceso denegado. Esta sección es solo para docentes.")
        return redirect('gestion_academica:inicio_academico')

    curso = get_object_or_404(
        Curso.objects.select_related('materia', 'grado', 'periodo_academico'), 
        pk=curso_pk
    )

    if not curso.docentes_asignados.filter(pk=request.user.docente.pk).exists():
        messages.error(request, "No tienes permiso para ver el libro de notas de este curso.")
        return redirect('gestion_academica:docente_seleccionar_curso_libro_notas')

    estudiantes_del_curso = Estudiante.objects.filter(
        grado_actual=curso.grado
    ).select_related('usuario').order_by('usuario__last_name', 'usuario__first_name')

    actividades_del_curso = ActividadCalificable.objects.filter(
        curso=curso
    ).order_by('fecha_publicacion', 'titulo')

    libro_notas_data = []
    for estudiante in estudiantes_del_curso:
        calificaciones_estudiante = Calificacion.objects.filter(
            estudiante=estudiante,
            actividad_calificable__in=actividades_del_curso
        ).select_related('actividad_calificable')
        
        cal_map = {cal.actividad_calificable_id: cal for cal in calificaciones_estudiante}
        
        notas_actividades = []
        suma_notas_ponderadas_estudiante = 0
        suma_porcentajes_estudiante = 0

        for actividad in actividades_del_curso:
            calificacion = cal_map.get(actividad.id)
            notas_actividades.append({
                'actividad_id': actividad.id,
                'calificacion': calificacion 
            })
            if calificacion and calificacion.valor_numerico is not None and actividad.porcentaje_en_periodo is not None:
                suma_notas_ponderadas_estudiante += (calificacion.valor_numerico * actividad.porcentaje_en_periodo)
                suma_porcentajes_estudiante += actividad.porcentaje_en_periodo
        
        nota_final_estudiante_curso = None
        if suma_porcentajes_estudiante > 0:
            nota_final_estudiante_curso = suma_notas_ponderadas_estudiante / suma_porcentajes_estudiante
        
        libro_notas_data.append({
            'estudiante': estudiante,
            'notas_actividades': notas_actividades,
            'nota_final_curso': nota_final_estudiante_curso
        })

    context = {
        'titulo_pagina': f"Libro de Notas: {curso}",
        'curso': curso,
        'actividades_del_curso': actividades_del_curso,
        'libro_notas_data': libro_notas_data,
    }
    return render(request, 'gestion_academica/docente_libro_de_notas_por_curso.html', context)

# --- Vistas para Tipos de Concepto de Pago ---
class TipoConceptoPagoListView(LoginRequiredMixin, ListView):
    model = TipoConceptoPago
    template_name = 'gestion_academica/tipo_concepto_pago_lista.html'
    context_object_name = 'tipos_conceptos'
    paginate_by = 15
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Tipos de Conceptos de Pago"
        return context

class TipoConceptoPagoCreateView(LoginRequiredMixin, CreateView):
    model = TipoConceptoPago
    form_class = TipoConceptoPagoForm
    template_name = 'gestion_academica/tipo_concepto_pago_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_tipos_concepto_pago')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Crear Nuevo Tipo de Concepto de Pago"
        return context
    def form_valid(self, form):
        messages.success(self.request, f"Tipo de concepto '{form.cleaned_data['nombre']}' creado exitosamente.")
        return super().form_valid(form)

class TipoConceptoPagoUpdateView(LoginRequiredMixin, UpdateView):
    model = TipoConceptoPago
    form_class = TipoConceptoPagoForm
    template_name = 'gestion_academica/tipo_concepto_pago_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_tipos_concepto_pago')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Editar Tipo de Concepto de Pago"
        return context
    def form_valid(self, form):
        messages.success(self.request, f"Tipo de concepto '{form.cleaned_data['nombre']}' actualizado exitosamente.")
        return super().form_valid(form)

class TipoConceptoPagoDeleteView(LoginRequiredMixin, DeleteView):
    model = TipoConceptoPago
    template_name = 'gestion_academica/tipo_concepto_pago_confirmar_eliminar.html'
    success_url = reverse_lazy('gestion_academica:lista_tipos_concepto_pago')
    context_object_name = 'tipo_concepto_pago'
    def delete(self, request, *args, **kwargs):
        tipo_concepto_eliminado = self.get_object()
        messages.success(request, f"El tipo de concepto '{tipo_concepto_eliminado.nombre}' ha sido eliminado.")
        return super().delete(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Confirmar Eliminación de Tipo de Concepto"
        return context

# --- Vistas para Conceptos de Pago ---
class ConceptoPagoListView(LoginRequiredMixin, ListView):
    model = ConceptoPago
    template_name = 'gestion_academica/concepto_pago_lista.html'
    context_object_name = 'conceptos_pago'
    paginate_by = 15
    def get_queryset(self):
        return ConceptoPago.objects.select_related(
            'tipo_concepto', 'periodo_academico_aplicable'
        ).order_by('-periodo_academico_aplicable__año_escolar', 'tipo_concepto__nombre', 'nombre_concepto')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Conceptos de Pago Definidos"
        return context

class ConceptoPagoCreateView(LoginRequiredMixin, CreateView):
    model = ConceptoPago
    form_class = ConceptoPagoForm
    template_name = 'gestion_academica/concepto_pago_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_conceptos_pago')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Crear Nuevo Concepto de Pago"
        return context
    def form_valid(self, form):
        messages.success(self.request, f"Concepto de pago '{form.cleaned_data['nombre_concepto']}' creado exitosamente.")
        return super().form_valid(form)

class ConceptoPagoUpdateView(LoginRequiredMixin, UpdateView):
    model = ConceptoPago
    form_class = ConceptoPagoForm
    template_name = 'gestion_academica/concepto_pago_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_conceptos_pago')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Editar Concepto de Pago"
        return context
    def form_valid(self, form):
        messages.success(self.request, f"Concepto de pago '{form.cleaned_data['nombre_concepto']}' actualizado exitosamente.")
        return super().form_valid(form)

class ConceptoPagoDeleteView(LoginRequiredMixin, DeleteView):
    model = ConceptoPago
    template_name = 'gestion_academica/concepto_pago_confirmar_eliminar.html'
    success_url = reverse_lazy('gestion_academica:lista_conceptos_pago')
    context_object_name = 'concepto_pago'
    def delete(self, request, *args, **kwargs):
        concepto_eliminado = self.get_object()
        messages.success(request, f"El concepto de pago '{concepto_eliminado.nombre_concepto}' ha sido eliminado.")
        return super().delete(request, *args, **kwargs)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Confirmar Eliminación de Concepto de Pago"
        return context

class CuentaPorCobrarEstudianteListView(LoginRequiredMixin, ListView):
    model = CuentaPorCobrarEstudiante
    template_name = 'gestion_academica/cuenta_por_cobrar_lista.html'
    context_object_name = 'cuentas_por_cobrar'
    paginate_by = 20

    def get_queryset(self):
        # Optimizar y ordenar, filtrar por defecto por pendientes o vencidas podría ser útil
        return CuentaPorCobrarEstudiante.objects.select_related(
            'estudiante__usuario', 'concepto_pago__tipo_concepto', 'concepto_pago__periodo_academico_aplicable'
        ).order_by('estado', '-fecha_vencimiento_especifica', 'estudiante__usuario__last_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Cuentas por Cobrar a Estudiantes"
        # Podrías añadir filtros aquí (ej. por estado, por estudiante)
        return context

class CuentaPorCobrarEstudianteCreateView(LoginRequiredMixin, CreateView):
    model = CuentaPorCobrarEstudiante
    form_class = CuentaPorCobrarEstudianteForm
    template_name = 'gestion_academica/cuenta_por_cobrar_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_cuentas_por_cobrar')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Crear Nueva Cuenta por Cobrar"
        return context

    def form_valid(self, form):
        # Si monto_asignado no se llenó y hay un concepto_pago, usar el monto_estandar
        if form.instance.monto_asignado is None or form.instance.monto_asignado == 0:
            if form.cleaned_data.get('concepto_pago'):
                form.instance.monto_asignado = form.cleaned_data['concepto_pago'].monto_estandar
        
        # El método save() del modelo ya maneja la actualización del estado.
        messages.success(self.request, f"Cuenta por cobrar para '{form.cleaned_data['estudiante']}' por '{form.cleaned_data['concepto_pago']}' creada exitosamente.")
        return super().form_valid(form)

class CuentaPorCobrarEstudianteUpdateView(LoginRequiredMixin, UpdateView):
    model = CuentaPorCobrarEstudiante
    form_class = CuentaPorCobrarEstudianteForm
    template_name = 'gestion_academica/cuenta_por_cobrar_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_cuentas_por_cobrar')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Editar Cuenta por Cobrar"
        return context

    def form_valid(self, form):
        # El método save() del modelo ya maneja la actualización del estado.
        messages.success(self.request, f"Cuenta por cobrar para '{form.cleaned_data['estudiante']}' actualizada exitosamente.")
        return super().form_valid(form)

class CuentaPorCobrarEstudianteDeleteView(LoginRequiredMixin, DeleteView):
    model = CuentaPorCobrarEstudiante
    template_name = 'gestion_academica/cuenta_por_cobrar_confirmar_eliminar.html'
    success_url = reverse_lazy('gestion_academica:lista_cuentas_por_cobrar')
    context_object_name = 'cuenta_por_cobrar'

    def delete(self, request, *args, **kwargs):
        cuenta_eliminada = self.get_object()
        # Considerar si se deben revertir pagos o si solo se anula la cuenta
        # Por ahora, solo borra el registro. Una mejor opción sería cambiar el estado a 'ANULADO'.
        messages.success(request, f"La cuenta por cobrar para '{cuenta_eliminada.estudiante}' por '{cuenta_eliminada.concepto_pago}' ha sido eliminada.")
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Confirmar Eliminación de Cuenta por Cobrar"
        return context


# --- Vistas para Noticias y Anuncios ---
class NoticiaListView(ListView):
    model = Noticia
    template_name = 'gestion_academica/noticia_lista.html'
    context_object_name = 'noticias'
    paginate_by = 5
    queryset = Noticia.objects.all().order_by('-fecha_publicacion')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Noticias y Anuncios"
        return context

class NoticiaDetailView(DetailView):
    model = Noticia
    template_name = 'gestion_academica/noticia_detalle.html'
    context_object_name = 'noticia'
    queryset = Noticia.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = self.object.titulo
        return context

class NoticiaCreateView(LoginRequiredMixin, CreateView):
    model = Noticia
    form_class = NoticiaForm
    template_name = 'gestion_academica/noticia_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_noticias_gestion')

    def form_valid(self, form):
        form.instance.publicado_por = self.request.user
        messages.success(self.request, f"Noticia '{form.cleaned_data['titulo']}' creada exitosamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Crear Nueva Noticia/Anuncio"
        return context

class NoticiaUpdateView(LoginRequiredMixin, UpdateView):
    model = Noticia
    form_class = NoticiaForm
    template_name = 'gestion_academica/noticia_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_noticias_gestion')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Editar Noticia/Anuncio"
        return context

    def form_valid(self, form):
        messages.success(self.request, f"Noticia '{form.cleaned_data['titulo']}' actualizada exitosamente.")
        return super().form_valid(form)

class NoticiaDeleteView(LoginRequiredMixin, DeleteView):
    model = Noticia
    template_name = 'gestion_academica/noticia_confirmar_eliminar.html'
    success_url = reverse_lazy('gestion_academica:lista_noticias_gestion')
    context_object_name = 'noticia'

    def delete(self, request, *args, **kwargs):
        noticia_eliminada = self.get_object()
        messages.success(request, f"La noticia '{noticia_eliminada.titulo}' ha sido eliminada.")
        return super().delete(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Confirmar Eliminación de Noticia"
        return context

class NoticiaGestionListView(LoginRequiredMixin, ListView):
    model = Noticia
    template_name = 'gestion_academica/noticia_gestion_lista.html'
    context_object_name = 'noticias'
    paginate_by = 10

    def get_queryset(self):
        if self.request.user.is_superuser or (hasattr(self.request.user, 'rol') and self.request.user.rol == 'administrativo'):
            return Noticia.objects.all().order_by('-fecha_publicacion')
        elif hasattr(self.request.user, 'docente'):
             return Noticia.objects.filter(publicado_por=self.request.user).order_by('-fecha_publicacion')
        return Noticia.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Gestión de Noticias y Anuncios"
        return context

def mis_cuentas(request):
    cuentas = CuentaPorCobrarEstudiante.objects.all()

    for cuenta in cuentas:
        monto_asignado = cuenta.monto_asignado or 0
        pagos = PagoRegistrado.objects.filter(cuenta=cuenta)
        monto_pagado = pagos.aggregate(total=Sum('valor_pagado'))['total'] or 0
        cuenta.monto_pagado = monto_pagado
        cuenta.saldo_restante = monto_asignado - monto_pagado

    return render(request, 'gestion_academica/finanzas/mis_cuentas.html', {'cuentas': cuentas})

def registrar_pago(request, cuenta_id):
    cuenta = get_object_or_404(CuentaPorCobrarEstudiante, id=cuenta_id)

    pagos = PagoRegistrado.objects.filter(cuenta=cuenta)
    monto_pagado = pagos.aggregate(total=Sum('valor_pagado'))['total'] or 0
    saldo_restante = (cuenta.monto_asignado or 0) - monto_pagado

    if request.method == 'POST':
        form = PagoForm(request.POST)
        if form.is_valid():
            pago = form.save(commit=False)
            pago.cuenta = cuenta
            pago.estudiante = cuenta.estudiante
            pago.save()
            return redirect('gestion_academica:generar_recibo_pago', pago_id=pago.id)
    else:
        form = PagoForm()

    context = {
        'cuenta': cuenta,
        'form': form,
        'pagos_existentes': pagos,
        'monto_pagado': monto_pagado,
        'saldo_restante': saldo_restante,
    }
    return render(request, 'gestion_academica/finanzas/registrar_pago.html', context)

@login_required
@permission_required('gestion_academica.puede_editar_pago', raise_exception=True)
def editar_pago(request, pago_id):
    pago = get_object_or_404(PagoRegistrado, id=pago_id)
    if request.method == 'POST':
        form = PagoForm(request.POST, instance=pago)
        if form.is_valid():
            form.save()
            return redirect('gestion_academica:mis_cuentas')
    else:
        form = PagoForm(instance=pago)
    return render(request, 'gestion_academica/finanzas/editar_pago.html', {'form': form})

@login_required
@permission_required('gestion_academica.puede_eliminar_pago', raise_exception=True)
def eliminar_pago(request, pago_id):
    pago = get_object_or_404(PagoRegistrado, id=pago_id)
    if request.method == 'POST':
        pago.delete()
        return redirect('gestion_academica:mis_cuentas')
    return render(request, 'gestion_academica/finanzas/eliminar_pago.html', {'pago': pago})

def estado_pagos_estudiante(request):
    estudiantes = Estudiante.objects.all()
    grado = request.GET.get('grado')
    estudiante_id = request.GET.get('estudiante')
    mes = request.GET.get('mes')
    año = request.GET.get('año')

    cuentas = CuentaPorCobrarEstudiante.objects.select_related('concepto_pago', 'estudiante')

    if estudiante_id:
        cuentas = cuentas.filter(estudiante__id=estudiante_id)
    if grado:
        cuentas = cuentas.filter(estudiante__grado=grado)
    if mes and año:
        cuentas = cuentas.filter(fecha_vencimiento_especifica__month=mes, fecha_vencimiento_especifica__year=año)

    return render(request, 'gestion_academica/finanzas/estado_pagos.html', {
        'cuentas': cuentas,
        'estudiantes': estudiantes
    })

def generar_recibo_pago(request, pago_id):
    pago = PagoRegistrado.objects.get(id=pago_id)
    template = get_template('gestion_academica/finanzas/recibo_pago.html')
    html = template.render({'pago': pago})
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="recibo_pago_{pago.id}.pdf"'
    pisa.CreatePDF(html, dest=response)
    return response

def generar_volante_matricula(request, estudiante_id):
    estudiante = Estudiante.objects.get(id=estudiante_id)
    conceptos = CuentaPorCobrarEstudiante.objects.filter(estudiante=estudiante, concepto_pago__nombre_concepto__icontains="Matrícula")
    template = get_template('gestion_academica/finanzas/volante_matricula.html')
    html = template.render({'estudiante': estudiante, 'conceptos': conceptos})
    # Crear PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="volante_matricula_{estudiante.id}.pdf"'
    pisa.CreatePDF(html, dest=response)
    return response

    if estudiante.acudiente_email:
        email = EmailMessage(
            subject='Volante de Matrícula',
            body='Adjunto encontrarás el volante de matrícula del estudiante.',
            from_email='noreply@colegio.com',
            to=[estudiante.acudiente_email]
        )
        pisa_pdf = HttpResponse(content_type='application/pdf')
        pisa.CreatePDF(html, dest=pisa_pdf)
        email.attach(f'volante_matricula_{estudiante.id}.pdf', pisa_pdf.content, 'application/pdf')
        email.send()

    return response   

def registro_inicial(request):
    if get_user_model().objects.exists():
        return redirect('login')

    if request.method == 'POST':
        form = RegistroInicialForm(request.POST, request.FILES)
        if form.is_valid():
            institucion = form.save()
            user = get_user_model().objects.create_superuser(
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
                institucion=institucion
            )
            return redirect('login')
    else:
        form = RegistroInicialForm()

    return render(request, 'registro_inicial.html', {'form': form})

