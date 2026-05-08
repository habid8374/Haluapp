from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse
from django.template.loader import get_template
from django.db.models import Count, Sum, F
from xhtml2pdf import pisa
from io import BytesIO
from django.db import transaction
from django.utils.crypto import get_random_string
import random

from .models import Curso, Modulo, InscripcionCurso, ProgresoModulo, Evaluacion, Opcion
from finanzas.models import CuentaPorCobrarEstudiante, InstitucionEducativa
from gestion_academica.models import Estudiante, Usuario
from .forms import CursoForm, ModuloForm, MaterialForm, EvaluacionForm, PreguntaForm, OpcionForm

@login_required
def catalogo_cursos(request):
    # Mostrar cursos de la institución del usuario
    institucion = request.user.institucion_asociada
    cursos = Curso.objects.filter(institucion=institucion, publicado=True)
    
    # Identificar cuáles ya compró
    inscritos_ids = []
    if hasattr(request.user, 'estudiante'):
        inscritos_ids = InscripcionCurso.objects.filter(
            estudiante=request.user.estudiante, activo=True
        ).values_list('curso_id', flat=True)

    return render(request, 'cursos/catalogo.html', {
        'cursos': cursos,
        'inscritos_ids': inscritos_ids
    })

@login_required
def detalle_curso(request, curso_id):
    curso = get_object_or_404(Curso, pk=curso_id)
    estudiante = getattr(request.user, 'estudiante', None)
    inscrito = False
    
    if estudiante:
        inscrito = InscripcionCurso.objects.filter(estudiante=estudiante, curso=curso, activo=True).exists()

    # Eliminada la lógica de auto-inscripción/compra por parte del estudiante.
    # Ahora solo el admin matricula.
    if request.method == 'POST':
        messages.info(request, "Para inscribirte en este curso, por favor contacta a la administración.")

    return render(request, 'cursos/detalle.html', {'curso': curso, 'inscrito': inscrito})

@login_required
def aula_virtual(request, curso_id):
    """
    Vista principal donde el estudiante consume el contenido.
    """
    if not hasattr(request.user, 'estudiante'):
        messages.warning(request, "La vista del Aula Virtual es exclusiva para estudiantes matriculados. Usa el panel de configuración para ver el contenido.")
        return redirect('cursos:catalogo')

    estudiante = request.user.estudiante
    inscripcion = get_object_or_404(InscripcionCurso, estudiante=estudiante, curso_id=curso_id, activo=True)
    modulos = inscripcion.curso.modulos.all()
    
    # Lógica de desbloqueo
    modulos_data = []
    # bloqueado = False # ELIMINADO: Ya no bloqueamos módulos
    
    for mod in modulos:
        progreso, created = ProgresoModulo.objects.get_or_create(inscripcion=inscripcion, modulo=mod)
        
        estado = 'desbloqueado'
        # if bloqueado: estado = 'bloqueado' # ELIMINADO
        
        modulos_data.append({
            'modulo': mod,
            'progreso': progreso,
            'estado': estado
        })
        
        # Ya no actualizamos la variable 'bloqueado' basándonos en la aprobación.
        # El estudiante puede navegar libremente.
        # Sin embargo, para el certificado, validaremos que todo esté aprobado.

    return render(request, 'cursos/aula.html', {
        'curso': inscripcion.curso,
        'modulos_data': modulos_data
    })

@login_required
def rendir_evaluacion(request, modulo_id):
    if not hasattr(request.user, 'estudiante'):
        messages.error(request, "Solo los estudiantes pueden rendir evaluaciones.")
        return redirect('cursos:catalogo')

    modulo = get_object_or_404(Modulo, pk=modulo_id)
    estudiante = request.user.estudiante
    inscripcion = get_object_or_404(InscripcionCurso, estudiante=estudiante, curso=modulo.curso)
    progreso, _ = ProgresoModulo.objects.get_or_create(inscripcion=inscripcion, modulo=modulo)
    evaluacion = modulo.evaluacion

    # Verificar intentos
    if evaluacion.intentos_permitidos > 0 and progreso.intentos_usados >= evaluacion.intentos_permitidos:
        messages.error(request, "Has agotado tus intentos para esta prueba.")
        return redirect('cursos:aula_virtual', curso_id=modulo.curso.id)

    if request.method == 'POST':
        puntaje_total = 0
        puntaje_maximo = 0
        
        for pregunta in evaluacion.preguntas.all():
            puntaje_maximo += pregunta.puntos
            opcion_seleccionada = request.POST.get(f'pregunta_{pregunta.id}')
            if opcion_seleccionada:
                opcion = Opcion.objects.get(pk=opcion_seleccionada)
                if opcion.es_correcta:
                    puntaje_total += pregunta.puntos
        
        nota_final = (puntaje_total / puntaje_maximo) * 100
        progreso.intentos_usados += 1
        progreso.mejor_nota = max(progreso.mejor_nota, nota_final)
        
        if nota_final >= evaluacion.porcentaje_aprobacion:
            progreso.aprobado = True
            progreso.completado = True
            progreso.fecha_completado = timezone.now()
            messages.success(request, f"¡Felicidades! Aprobaste con {nota_final}%. Siguiente módulo desbloqueado.")
        else:
            messages.warning(request, f"Obtuviste {nota_final}%. Necesitas {evaluacion.porcentaje_aprobacion}% para avanzar. Inténtalo de nuevo.")
        
        progreso.save()
        return redirect('cursos:aula_virtual', curso_id=modulo.curso.id)

    return render(request, 'cursos/evaluacion.html', {'evaluacion': evaluacion})

# --- VISTAS DE ADMINISTRACIÓN Y REPORTES ---

@login_required
@permission_required('cursos.add_curso', raise_exception=True)
def gestion_cursos_admin(request):
    """Panel para crear y configurar cursos."""
    if request.user.is_superuser:
        cursos = Curso.objects.all().select_related('institucion')
    else:
        cursos = Curso.objects.filter(institucion=request.user.institucion_asociada)
    return render(request, 'cursos/admin/lista_cursos.html', {'cursos': cursos})

@login_required
@permission_required('cursos.add_curso', raise_exception=True)
def crear_curso(request):
    if request.method == 'POST':
        form = CursoForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            curso = form.save(commit=False)
            # Si no es superuser, asignamos la institución del usuario
            if not request.user.is_superuser:
                curso.institucion = request.user.institucion_asociada
            curso.save()
            messages.success(request, "Curso creado exitosamente.")
            return redirect('cursos:configurar_curso', curso_id=curso.id)
    else:
        form = CursoForm(user=request.user)
    return render(request, 'cursos/admin/formulario_curso.html', {'form': form, 'titulo': 'Crear Curso'})

@login_required
@permission_required('cursos.change_curso', raise_exception=True)
def editar_curso(request, curso_id):
    # Permitimos al superusuario editar cualquier curso
    if request.user.is_superuser:
        curso = get_object_or_404(Curso, pk=curso_id)
    else:
        curso = get_object_or_404(Curso, pk=curso_id, institucion=request.user.institucion_asociada)

    if request.method == 'POST':
        form = CursoForm(request.POST, request.FILES, instance=curso, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Información del curso actualizada exitosamente.")
            return redirect('cursos:gestion_cursos_admin')
    else:
        form = CursoForm(instance=curso, user=request.user)
    return render(request, 'cursos/admin/formulario_curso.html', {'form': form, 'titulo': 'Editar Curso'})

@login_required
@permission_required('cursos.change_curso', raise_exception=True)
def configurar_curso(request, curso_id):
    """Vista principal para gestionar módulos y materiales de un curso."""
    curso = get_object_or_404(Curso, pk=curso_id, institucion=request.user.institucion_asociada)
    return render(request, 'cursos/admin/configurar_curso.html', {'curso': curso})

@login_required
@permission_required('cursos.add_modulo', raise_exception=True)
def agregar_modulo(request, curso_id):
    curso = get_object_or_404(Curso, pk=curso_id)
    if request.method == 'POST':
        form = ModuloForm(request.POST)
        if form.is_valid():
            modulo = form.save(commit=False)
            modulo.curso = curso
            modulo.save()
            messages.success(request, "Módulo agregado.")
            return redirect('cursos:configurar_curso', curso_id=curso.id)
    else:
        form = ModuloForm()
    return render(request, 'cursos/admin/formulario_generico.html', {'form': form, 'titulo': f'Agregar Módulo a {curso.nombre}'})

@login_required
@permission_required('cursos.add_material', raise_exception=True)
def agregar_material(request, modulo_id):
    modulo = get_object_or_404(Modulo, pk=modulo_id)
    if request.method == 'POST':
        form = MaterialForm(request.POST, request.FILES)
        if form.is_valid():
            material = form.save(commit=False)
            material.modulo = modulo
            material.save()
            messages.success(request, "Material agregado.")
            return redirect('cursos:configurar_curso', curso_id=modulo.curso.id)
    else:
        form = MaterialForm()
    return render(request, 'cursos/admin/formulario_generico.html', {'form': form, 'titulo': f'Agregar Material a {modulo.titulo}'})

@login_required
@permission_required('cursos.add_evaluacion', raise_exception=True)
def agregar_evaluacion(request, modulo_id):
    modulo = get_object_or_404(Modulo, pk=modulo_id)
    if request.method == 'POST':
        form = EvaluacionForm(request.POST)
        if form.is_valid():
            evaluacion = form.save(commit=False)
            evaluacion.modulo = modulo
            evaluacion.save()
            messages.success(request, "Evaluación creada. Ahora agrega preguntas.")
            # Aquí podrías redirigir a una vista para agregar preguntas
            return redirect('cursos:configurar_curso', curso_id=modulo.curso.id)
    else:
        form = EvaluacionForm()
    return render(request, 'cursos/admin/formulario_generico.html', {'form': form, 'titulo': f'Crear Evaluación para {modulo.titulo}'})

@login_required
@permission_required('cursos.add_inscripcioncurso', raise_exception=True)
def matricular_estudiante_manual(request):
    """
    Vista para que el admin matricule a un estudiante tras pago en efectivo.
    Dispara la señal que envía el correo con el link.
    """
    # 1. Determinar la institución de trabajo
    if request.user.is_superuser:
        instituciones = InstitucionEducativa.objects.all()
        institucion_id = request.GET.get('institucion_id')
        if institucion_id:
            institucion_actual = get_object_or_404(InstitucionEducativa, pk=institucion_id)
        else:
            institucion_actual = instituciones.first()
    else:
        instituciones = [request.user.institucion_asociada]
        institucion_actual = request.user.institucion_asociada

    if request.method == 'POST':
        estudiante_id = request.POST.get('estudiante_id')
        curso_id = request.POST.get('curso_id')
        
        try:
            estudiante = Estudiante.objects.get(pk=estudiante_id)
            curso = Curso.objects.get(pk=curso_id)
            
            # Crear la inscripción (esto disparará la señal post_save)
            inscripcion, created = InscripcionCurso.objects.get_or_create(
                estudiante=estudiante,
                curso=curso,
                defaults={'activo': True}
            )
            
            if created:
                messages.success(request, f"Estudiante {estudiante} matriculado en {curso.nombre}. Se ha enviado el correo de acceso.")
            else:
                messages.warning(request, "El estudiante ya estaba matriculado en este curso.")
                
        except Exception as e:
            messages.error(request, f"Error al matricular: {e}")
            
        return redirect('cursos:gestion_cursos_admin')

    # GET: Mostrar formulario simple
    estudiantes = Estudiante.objects.filter(institucion=institucion_actual, activo=True)
    cursos = Curso.objects.filter(institucion=institucion_actual)
    
    return render(request, 'cursos/admin/matricular_manual.html', {
        'estudiantes': estudiantes,
        'cursos': cursos,
        'institucion_actual': institucion_actual,
        'instituciones': instituciones,
        'es_superuser': request.user.is_superuser
    })

@login_required
@permission_required('cursos.view_inscripcioncurso', raise_exception=True)
def reporte_estadisticas_cursos(request):
    """
    Genera informes de ventas (cantidad de alumnos * precio) y progreso.
    """
    institucion = request.user.institucion_asociada
    
    # Estadísticas por curso
    stats_cursos = Curso.objects.filter(institucion=institucion).annotate(
        total_alumnos=Count('inscripcioncurso')
    )
    
    # Ajuste manual para ingresos reales (Precio del curso * Num Inscritos)
    data_reporte = []
    total_general_ingresos = 0
    
    for curso in stats_cursos:
        ingreso_curso = curso.precio * curso.total_alumnos
        total_general_ingresos += ingreso_curso
        
        # Calcular % de finalización promedio
        inscripciones = curso.inscripcioncurso_set.all()
        promedio_progreso = 0
        if inscripciones.exists():
            promedios = [ins.progreso_porcentaje for ins in inscripciones]
            promedio_progreso = sum(promedios) / len(promedios)
            
        data_reporte.append({
            'curso': curso,
            'alumnos': curso.total_alumnos,
            'ingresos': ingreso_curso,
            'promedio_progreso': round(promedio_progreso, 2)
        })

    return render(request, 'cursos/admin/reporte_estadisticas.html', {
        'data_reporte': data_reporte,
        'total_general': total_general_ingresos
    })

@login_required
def generar_certificado_pdf(request, curso_id):
    """
    Genera el certificado si el estudiante ha aprobado los requisitos.
    """
    estudiante = request.user.estudiante
    inscripcion = get_object_or_404(InscripcionCurso, estudiante=estudiante, curso_id=curso_id)
    
    # Validar si ganó todos los exámenes (requisito del usuario: "bueno que el alumno los gane")
    modulos = inscripcion.curso.modulos.all()
    todo_aprobado = True
    
    for mod in modulos:
        if hasattr(mod, 'evaluacion'):
            progreso = ProgresoModulo.objects.filter(inscripcion=inscripcion, modulo=mod).first()
            if not progreso or not progreso.aprobado:
                todo_aprobado = False
                break
    
    if not todo_aprobado:
        messages.warning(request, "Debes aprobar todas las evaluaciones para descargar el certificado.")
        return redirect('cursos:aula_virtual', curso_id=curso_id)

    # Generar PDF
    template_path = 'cursos/pdfs/certificado.html'
    context = {
        'estudiante': estudiante,
        'curso': inscripcion.curso,
        'fecha': timezone.now(),
        'institucion': inscripcion.curso.institucion
    }
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Certificado_{inscripcion.curso.nombre}.pdf"'
    
    template = get_template(template_path)
    html = template.render(context)
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('Error al generar PDF', status=500)
    return response

@login_required
@permission_required('cursos.add_inscripcioncurso', raise_exception=True)
def registrar_estudiante_curso(request):
    """
    MÓDULO DE ADMISIÓN INDEPENDIENTE PARA CURSOS.
    Permite registrar un nuevo estudiante desde cero y matricularlo directamente,
    sin pasar por el proceso complejo de admisiones escolares.
    """
    # 1. Determinar la institución de trabajo (igual que en matricular)
    if request.user.is_superuser:
        instituciones = InstitucionEducativa.objects.all()
        # Prioridad: POST (si hubo error), luego GET, luego primera disponible
        institucion_id = request.POST.get('institucion_id') or request.GET.get('institucion_id')
        if institucion_id:
            institucion_actual = get_object_or_404(InstitucionEducativa, pk=institucion_id)
        else:
            institucion_actual = instituciones.first()
    else:
        instituciones = [request.user.institucion_asociada]
        institucion_actual = request.user.institucion_asociada

    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        documento = request.POST.get('documento')
        curso_id = request.POST.get('curso_id')
        
        # Validación básica
        if Usuario.objects.filter(email=email).exists():
            messages.error(request, "Error: Ya existe un usuario con este correo electrónico.")
            return redirect('cursos:registrar_estudiante_curso')
            
        try:
            with transaction.atomic():
                # 1. Crear Usuario (Login)
                username = f"{first_name.split()[0].lower()}.{last_name.split()[0].lower()}.{random.randint(100,999)}"
                # TODO: Reemplazar este mecanismo temporal por un flujo seguro de activacion/reset antes de produccion final.
                temp_password = get_random_string(
                    length=20,
                    allowed_chars='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+',
                )
                user = Usuario.objects.create_user(
                    username=username,
                    email=email,
                    password=temp_password, # Contraseña temporal aleatoria
                    first_name=first_name,
                    last_name=last_name,
                    rol='estudiante',
                    institucion_asociada=institucion_actual # Usamos la seleccionada
                )
                
                # 2. Crear Perfil de Estudiante (Sin grado escolar, solo vinculado a la institución)
                estudiante = Estudiante.objects.create(
                    usuario=user,
                    documento_identidad=documento,
                    institucion=institucion_actual, # Usamos la seleccionada
                    # No asignamos grado_actual porque es un estudiante de curso libre
                )
                messages.warning(
                    request,
                    f"Contrasena temporal para '{username}': {temp_password}. "
                    "Compártela por un canal seguro y solicita cambio inmediato."
                )
                
                # 3. Matricular en el Curso (Esto dispara el correo de bienvenida automáticamente)
                curso = Curso.objects.get(pk=curso_id)
                InscripcionCurso.objects.create(estudiante=estudiante, curso=curso, activo=True)
                
            messages.success(request, f"Estudiante {first_name} {last_name} registrado y matriculado exitosamente.")
            return redirect('cursos:gestion_cursos_admin')
            
        except Exception as e:
            messages.error(request, f"Ocurrió un error al registrar: {e}")
            
    # CORRECCIÓN: Mostramos todos los cursos (incluso borradores) para que el admin pueda matricular
    cursos = Curso.objects.filter(institucion=institucion_actual)
    return render(request, 'cursos/admin/registrar_estudiante.html', {
        'cursos': cursos,
        'institucion_actual': institucion_actual,
        'instituciones': instituciones,
        'es_superuser': request.user.is_superuser
    })

@login_required
@permission_required('cursos.view_inscripcioncurso', raise_exception=True)
def lista_estudiantes_curso(request, curso_id):
    """
    Muestra el listado de estudiantes matriculados en un curso específico y su estado.
    """
    curso = get_object_or_404(Curso, pk=curso_id, institucion=request.user.institucion_asociada)
    inscripciones = InscripcionCurso.objects.filter(curso=curso).select_related('estudiante__usuario').order_by('estudiante__usuario__last_name')
    
    return render(request, 'cursos/admin/lista_estudiantes_curso.html', {
        'curso': curso,
        'inscripciones': inscripciones
    })
