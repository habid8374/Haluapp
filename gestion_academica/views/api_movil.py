"""
gestion_academica/views/api_movil.py
=====================================
Endpoints REST /api/v1/ para la aplicación móvil HALU.
Autenticación: JWT (Bearer token) o sesión Django.
Extraído del monolito views.py.
"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Avg, Count, Q, Sum
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from collections import defaultdict
import logging

from ..models import (
    Estudiante, Docente, Familiar, Curso, PeriodoAcademico, Grado, Materia,
    ActividadCalificable, Calificacion, Deber, EntregaDeber, RegistroAsistencia,
    MencionReconocimiento, BloqueHorario, Noticia, TipoActividad, DescriptorLogro,
    DisponibilidadDocente, CitaReunion, DirectorCurso, AnotacionObservador,
    EsquemaCalificacion, AreaAcademica, LeccionDiaria,
)
from finanzas.models import CuentaPorCobrarEstudiante, PagoRegistrado
from gestion_academica.decorators import EstaAlDiaPermission

logger = logging.getLogger(__name__)

def api_reportes_data(request):
    """
    API que devuelve datos para generar reportes
    """
    user = request.user
    if not (user.is_staff and user.rol in ['coordinador', 'administrador']):
        return Response({'error': 'Acceso denegado.'}, status=403)

    try:
        user_inst = getattr(user, 'institucion_asociada', None)
        periodo_activo = PeriodoAcademico.objects.filter(
            institucion=user_inst, 
            activo=True
        ).first() if user_inst else None

        if not periodo_activo:
            return Response({'error': 'No hay periodo académico activo'}, status=404)

        # Datos para reportes
        grados = Grado.objects.filter(institucion=user_inst).order_by('nombre')
        
        reportes_disponibles = [
            {
                'id': 'asistencia',
                'titulo': 'Reporte de Asistencia',
                'descripcion': 'Estadísticas de asistencia por curso y período',
                'icono': 'checkmark-done-outline'
            },
            {
                'id': 'academico', 
                'titulo': 'Reporte Académico',
                'descripcion': 'Rendimiento académico por materia y estudiante',
                'icono': 'school-outline'
            },
            {
                'id': 'disciplinario',
                'titulo': 'Reporte Disciplinario', 
                'descripcion': 'Incidentes y observaciones de comportamiento',
                'icono': 'alert-circle-outline'
            },
            {
                'id': 'bienestar',
                'titulo': 'Reporte de Bienestar',
                'descripcion': 'Alertas y seguimiento psicosocial',
                'icono': 'heart-outline'
            }
        ]

        data = {
            'periodo_activo': {
                'id': periodo_activo.id,
                'nombre': periodo_activo.nombre
            },
            'grados_disponibles': [
                {'id': g.id, 'nombre': g.nombre} for g in grados
            ],
            'reportes_disponibles': reportes_disponibles
        }
        
        return Response(data)
        
    except Exception as e:
        return Response({'error': f'Error inesperado: {str(e)}'}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_asistencia_diaria_data(request):
    """
    API que devuelve datos detallados de asistencia diaria
    """
    user = request.user
    if not (user.is_staff and user.rol in ['coordinador', 'administrador']):
        return Response({'error': 'Acceso denegado.'}, status=403)

    try:
        user_inst = getattr(user, 'institucion_asociada', None)
        fecha_str = request.GET.get('fecha', timezone.localdate().strftime('%Y-%m-%d'))
        
        try:
            fecha_consulta = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            fecha_consulta = timezone.localdate()

        # Registros de asistencia del día
        registros_dia = RegistroAsistencia.objects.filter(
            estudiante__institucion=user_inst,
            fecha__date=fecha_consulta
        ).select_related('estudiante__usuario', 'estudiante__grado_actual', 'curso__materia')

        # Agrupar por grado
        asistencia_por_grado = defaultdict(lambda: {
            'total_estudiantes': 0,
            'presentes': 0,
            'ausentes': 0, 
            'tardanzas': 0,
            'estudiantes_detalle': []
        })

        # Obtener todos los estudiantes activos
        estudiantes_activos = Estudiante.objects.filter(
            institucion=user_inst,
            usuario__is_active=True
        ).select_related('usuario', 'grado_actual')

        # Crear mapa de registros por estudiante
        registros_map = {r.estudiante.id: r for r in registros_dia}

        for estudiante in estudiantes_activos:
            if estudiante.grado_actual:
                grado_nombre = estudiante.grado_actual.nombre
                asistencia_por_grado[grado_nombre]['total_estudiantes'] += 1
                
                registro = registros_map.get(estudiante.id)
                if registro:
                    if registro.estado == 'PRESENTE':
                        asistencia_por_grado[grado_nombre]['presentes'] += 1
                    elif registro.estado == 'AUSENTE':
                        asistencia_por_grado[grado_nombre]['ausentes'] += 1
                    elif registro.estado == 'TARDANZA':
                        asistencia_por_grado[grado_nombre]['tardanzas'] += 1
                    
                    estado_display = registro.get_estado_display()
                else:
                    estado_display = 'Sin registro'
                
                asistencia_por_grado[grado_nombre]['estudiantes_detalle'].append({
                    'id': estudiante.id,
                    'nombre': estudiante.usuario.get_full_name(),
                    'estado': estado_display,
                    'hora_registro': registro.fecha.strftime('%H:%M') if registro else None
                })

        # Calcular porcentajes
        for grado_data in asistencia_por_grado.values():
            total = grado_data['total_estudiantes']
            if total > 0:
                grado_data['porcentaje_asistencia'] = round(
                    (grado_data['presentes'] / total) * 100, 1
                )
            else:
                grado_data['porcentaje_asistencia'] = 0

        data = {
            'fecha_consulta': fecha_consulta.strftime('%Y-%m-%d'),
            'fecha_display': fecha_consulta.strftime('%d de %B de %Y'),
            'resumen_general': {
                'total_estudiantes': sum(g['total_estudiantes'] for g in asistencia_por_grado.values()),
                'total_presentes': sum(g['presentes'] for g in asistencia_por_grado.values()),
                'total_ausentes': sum(g['ausentes'] for g in asistencia_por_grado.values()),
                'total_tardanzas': sum(g['tardanzas'] for g in asistencia_por_grado.values())
            },
            'asistencia_por_grado': dict(asistencia_por_grado)
        }
        
        return Response(data)
        
    except Exception as e:
        return Response({'error': f'Error inesperado: {str(e)}'}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_alertas_bienestar_data(request):
    """
    API que devuelve las alertas de bienestar para revisión
    """
    user = request.user
    if not (user.is_staff and user.rol in ['coordinador', 'administrador', 'psicologo']):
        return Response({'error': 'Acceso denegado.'}, status=403)

    try:
        user_inst = getattr(user, 'institucion_asociada', None)
        
        # Filtros opcionales
        categoria = request.GET.get('categoria', 'todas')
        
        alertas_query = AnotacionObservador.objects.filter(
            requiere_revision=True
        ).select_related('estudiante__usuario', 'estudiante__grado_actual', 'registrado_por')
        
        if user_inst:
            alertas_query = alertas_query.filter(estudiante__institucion=user_inst)
        
        # Aplicar filtro de categoría si se especifica
        if categoria != 'todas':
            alertas_query = alertas_query.filter(tipo_situacion_ia=categoria.upper())

        alertas = alertas_query.order_by('-fecha_hora')[:50]  # Limitar a 50 más recientes

        # Estadísticas por categoría
        estadisticas = {
            'total': alertas_query.count(),
            'criticas': alertas_query.filter(tipo_situacion_ia='CRITICA').count(),
            'activas': alertas_query.filter(requiere_revision=True).count(),
        }

        alertas_data = []
        for alerta in alertas:
            alertas_data.append({
                'id': alerta.id,
                'estudiante': {
                    'id': alerta.estudiante.id,
                    'nombre': alerta.estudiante.usuario.get_full_name(),
                    'grado': alerta.estudiante.grado_actual.nombre if alerta.estudiante.grado_actual else 'Sin grado'
                },
                'descripcion': alerta.descripcion,
                'tipo_situacion': alerta.tipo_situacion_ia or 'NINGUNO',
                'fecha': alerta.fecha_hora.strftime('%d/%m/%Y %H:%M'),
                'registrado_por': alerta.registrado_por.get_full_name() if alerta.registrado_por else 'Sistema'
            })

        data = {
            'estadisticas': estadisticas,
            'alertas': alertas_data,
            'categorias_disponibles': [
                {'id': 'todas', 'label': 'Todas'},
                {'id': 'academico', 'label': 'Académico'},
                {'id': 'comportamiento', 'label': 'Comportamiento'},
                {'id': 'emocional', 'label': 'Emocional'},
                {'id': 'familiar', 'label': 'Familiar'}
            ]
        }
        
        return Response(data)
        
    except Exception as e:
        return Response({'error': f'Error inesperado: {str(e)}'}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_citas_supervision_data(request):
    """
    API que devuelve las citas programadas para supervisión
    """
    user = request.user
    if not (user.is_staff and user.rol in ['coordinador', 'administrador']):
        return Response({'error': 'Acceso denegado.'}, status=403)

    try:
        user_inst = getattr(user, 'institucion_asociada', None)
        
        citas_query = CitaReunion.objects.select_related(
            'docente__usuario', 
            'familiar__usuario', 
            'estudiante__usuario'
        )
        
        if user_inst:
            citas_query = citas_query.filter(docente__institucion=user_inst)
        
        # Filtros opcionales
        estado = request.GET.get('estado', 'todas')
        if estado != 'todas':
            citas_query = citas_query.filter(estado=estado.upper())

        citas = citas_query.order_by('-fecha_hora_inicio')[:100]  # Últimas 100 citas

        # Estadísticas
        estadisticas = {
            'total': citas_query.count(),
            'pendientes': citas_query.filter(estado='PENDIENTE').count(),
            'confirmadas': citas_query.filter(estado='CONFIRMADA').count(),
            'realizadas': citas_query.filter(estado='REALIZADA').count(),
            'canceladas': citas_query.filter(estado='CANCELADA').count()
        }

        citas_data = []
        for cita in citas:
            citas_data.append({
                'id': cita.id,
                'docente': cita.docente.usuario.get_full_name(),
                'familiar': cita.familiar.usuario.get_full_name(),
                'estudiante': cita.estudiante.usuario.get_full_name(),
                'fecha_hora': cita.fecha_hora_inicio.strftime('%d/%m/%Y %H:%M'),
                'asunto': cita.asunto,
                'estado': cita.get_estado_display(),
                'estado_codigo': cita.estado,
                'notas': cita.notas_reunion or '',
                'acuerdos': cita.acuerdos_establecidos or ''
            })

        data = {
            'estadisticas': estadisticas,
            'citas': citas_data,
            'estados_disponibles': [
                {'id': 'todas', 'label': 'Todas'},
                {'id': 'pendiente', 'label': 'Pendientes'},
                {'id': 'confirmada', 'label': 'Confirmadas'},
                {'id': 'realizada', 'label': 'Realizadas'},
                {'id': 'cancelada', 'label': 'Canceladas'}
            ]
        }
        
        return Response(data)
        
    except Exception as e:
        return Response({'error': f'Error inesperado: {str(e)}'}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_noticias_gestion_data(request):
    """
    API que devuelve las noticias para gestión por coordinadores
    """
    user = request.user
    if not (user.is_staff and user.rol in ['coordinador', 'administrador']):
        return Response({'error': 'Acceso denegado.'}, status=403)

    try:
        user_inst = getattr(user, 'institucion_asociada', None)
        
        noticias_query = Noticia.objects.select_related('publicado_por')
        
        if user_inst:
            noticias_query = noticias_query.filter(institucion=user_inst)
        
        noticias = noticias_query.order_by('-fecha_publicacion')[:50]

        noticias_data = []
        for noticia in noticias:
            noticias_data.append({
                'id': noticia.id,
                'titulo': noticia.titulo,
                'resumen': noticia.resumen or noticia.contenido[:100] + '...',
                'fecha_publicacion': noticia.fecha_publicacion.strftime('%d/%m/%Y'),
                'publicado_por': noticia.publicado_por.get_full_name() if noticia.publicado_por else 'Sistema',
                'activa': noticia.activa if hasattr(noticia, 'activa') else True
            })

        data = {
            'noticias': noticias_data,
            'total_noticias': noticias_query.count()
        }
        
        return Response(data)
        
    except Exception as e:
        return Response({'error': f'Error inesperado: {str(e)}'}, status=500)

@api_view(['GET'])
def mis_menciones_api_view(request):
    """ API para la PANTALLA DE DETALLE de menciones y honores del estudiante. """
    user = request.user
    if not hasattr(user, 'estudiante'): return Response({'error': 'Acceso denegado.'}, status=403)
    try:
        menciones = MencionReconocimiento.objects.filter(estudiante=user.estudiante).order_by('-fecha_emision')
        data = [{'id_mencion': m.pk, 'titulo': m.titulo, 'descripcion': m.descripcion, 'fecha': m.fecha_emision.strftime('%d %b, %Y')} for m in menciones]
        return Response(data)
    except Exception as e: return Response({'error': f'Ocurrió un error: {str(e)}'}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated, EstaAlDiaPermission])
def mi_historial_asistencia_api_view(request):
    """ API para la PANTALLA DE DETALLE del historial de asistencia. """
    user = request.user
    if not hasattr(user, 'estudiante'): return Response({'error': 'Acceso denegado.'}, status=403)
    try:
        estudiante = user.estudiante
        periodo_activo = PeriodoAcademico.objects.filter(institucion=estudiante.institucion, activo=True).first()
        if not periodo_activo: return Response([])
        historial = RegistroAsistencia.objects.filter(estudiante=estudiante, curso__periodo_academico=periodo_activo).select_related('curso__materia').order_by('-fecha')
        data = [{'fecha': r.fecha.strftime('%d/%m/%Y'), 'materia': r.curso.materia.nombre_materia if r.curso else 'N/A', 'estado': r.get_estado_display()} for r in historial]
        return Response(data)
    except Exception as e: return Response({'error': f'Ocurrió un error: {str(e)}'}, status=500)     

def get_cursos_docente_periodo_activo(user):
    docente = user.docente
    periodo_activo = PeriodoAcademico.objects.filter(institucion=docente.institucion, activo=True).first()
    if not periodo_activo: return Curso.objects.none()
    return Curso.objects.filter(docentes_asignados=docente, periodo_academico=periodo_activo).select_related('materia', 'grado')

@api_view(['GET'])
def api_seleccionar_curso_asistencia(request):
    """ API que devuelve TODOS los cursos de la institución para asistir. """
    user = request.user
    if not hasattr(user, 'docente'): return Response({'error': 'Acceso denegado.'}, status=403)
    periodo_activo = PeriodoAcademico.objects.filter(institucion=user.docente.institucion, activo=True).first()
    cursos = Curso.objects.filter(periodo_academico=periodo_activo).select_related('materia', 'grado')
    data = [{'id_curso': c.id, 'nombre_curso': f"{c.materia.nombre_materia} - {c.grado.nombre}"} for c in cursos]
    return Response(data)

@api_view(['GET'])
def api_seleccionar_curso_libro_notas(request):
    """ API que devuelve los cursos del docente para el Libro de Notas. """
    user = request.user
    if not hasattr(user, 'docente'): return Response({'error': 'Acceso denegado.'}, status=403)
    cursos = get_cursos_docente_periodo_activo(user)
    data = [{'id_curso': c.id, 'nombre_curso': f"{c.materia.nombre_materia} - {c.grado.nombre}"} for c in cursos]
    return Response(data)

@api_view(['GET'])
def api_docente_lista_actividades(request):
    """ API que devuelve la lista de actividades creadas por el docente. """
    user = request.user
    if not hasattr(user, 'docente'): return Response({'error': 'Acceso denegado.'}, status=403)
    cursos_docente = get_cursos_docente_periodo_activo(user)
    actividades = ActividadCalificable.objects.filter(curso__in=cursos_docente).select_related('curso__materia', 'tipo_actividad')
    data = [{'id': a.id, 'titulo': a.titulo, 'curso': a.curso.materia.nombre_materia, 'tipo': a.tipo_actividad.nombre} for a in actividades]
    return Response(data)

@api_view(['GET'])
def api_docente_lista_categorias(request):
    """ API para la lista de categorías del docente. """
    user = request.user
    if not hasattr(user, 'docente'): return Response({'error': 'Acceso denegado.'}, status=403)
    categorias = TipoActividad.objects.filter(institucion=user.docente.institucion)
    data = [{'id': c.id, 'nombre': c.nombre, 'porcentaje': c.porcentaje} for c in categorias]
    return Response(data)

@api_view(['GET'])
def api_docente_lista_descriptores(request):
    """ API para la lista de descriptores del docente. """
    user = request.user
    if not hasattr(user, 'docente'): return Response({'error': 'Acceso denegado.'}, status=403)
    descriptores = DescriptorLogro.objects.filter(creado_por=user).select_related('materia')
    data = [{'id': d.id, 'descripcion': d.descripcion, 'materia': d.materia.nombre_materia} for d in descriptores]
    return Response(data)

@api_view(['GET'])
def api_docente_lista_materiales(request):
    """ API para la lista de materiales del docente. """
    user = request.user
    if not hasattr(user, 'docente'): return Response({'error': 'Acceso denegado.'}, status=403)
    materiales = ArchivoPlanAcademico.objects.filter(subido_por=user)
    data = [{'id': m.id, 'nombre': m.nombre_archivo_descriptivo, 'url': request.build_absolute_uri(m.archivo.url)} for m in materiales if m.archivo]
    return Response(data)

@api_view(['GET'])
def api_seleccionar_curso_leccion(request):
    """ API que devuelve los cursos del docente para registrar lecciones. """
    return api_seleccionar_curso_libro_notas(request) # Reutiliza la misma lógica y vista

@api_view(['GET'])
def api_seleccionar_estudiante_observador(request):
    """ API que devuelve la lista de estudiantes del docente para el observador. """
    user = request.user
    if not hasattr(user, 'docente'): return Response({'error': 'Acceso denegado.'}, status=403)
    cursos_docente = get_cursos_docente_periodo_activo(user)
    grados_ids = cursos_docente.values_list('grado_id', flat=True).distinct()
    estudiantes = Estudiante.objects.filter(grado_actual_id__in=grados_ids).select_related('usuario')
    data = [{'id_estudiante': e.pk, 'nombre_completo': e.usuario.get_full_name()} for e in estudiantes]
    return Response(data)

@api_view(['GET'])
def api_gestionar_disponibilidad(request):
    """ API para la lista de disponibilidades del docente. """
    user = request.user
    if not hasattr(user, 'docente'): return Response({'error': 'Acceso denegado.'}, status=403)
    disponibilidades = DisponibilidadDocente.objects.filter(docente=user.docente)
    data = [{'id': d.id, 'dia': d.get_dia_semana_display(), 'inicio': d.hora_inicio, 'fin': d.hora_fin} for d in disponibilidades]
    return Response(data)

@api_view(['GET'])
def api_docente_lista_menciones(request):
    """ API para la lista de menciones creadas por el docente. """
    user = request.user
    if not hasattr(user, 'docente'): return Response({'error': 'Acceso denegado.'}, status=403)
    menciones = MencionReconocimiento.objects.filter(otorgado_por=user.docente).select_related('estudiante__usuario')
    data = [{'id': m.pk, 'tipo': m.tipo, 'estudiante': m.estudiante.usuario.get_full_name(), 'fecha': m.fecha_otorgamiento} for m in menciones]
    return Response(data)
    
@api_view(['GET'])
def api_seleccionar_curso_reporte_minima(request):
    """ API que devuelve los cursos del docente para el reporte de nota mínima. """
    return api_seleccionar_curso_libro_notas(request) # Reutiliza la misma lógica

@api_view(['GET'])
def api_panel_director_grupo(request):
    """ API que devuelve los datos del panel del director de grupo. """
    user = request.user
    if not hasattr(user, 'docente'): return Response({'error': 'Acceso denegado.'}, status=403)
    # ... (lógica para calcular y devolver los datos del panel)
    return Response({"mensaje": "Datos del panel del director de grupo"})               

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_admin_asistencia_diaria(request):
    """ API que devuelve un resumen de la asistencia del día. """
    user = request.user
    if not user.is_staff: return Response({'error': 'Acceso denegado.'}, status=403)
    
    user_inst = getattr(user, 'institucion_asociada', None)
    if not user_inst: return Response({'error': 'Usuario no asociado a una institución.'}, status=400)

    hoy = timezone.localdate()
    registros_hoy = RegistroAsistencia.objects.filter(estudiante__institucion=user_inst, fecha__date=hoy)
    
    total_estudiantes = Estudiante.objects.filter(institucion=user_inst, usuario__is_active=True).count()
    presentes = registros_hoy.filter(estado='PRESENTE').count()
    ausentes = registros_hoy.filter(estado='AUSENTE').count()
    tardanzas = registros_hoy.filter(estado='TARDANZA').count()

    data = {
        'fecha': hoy.strftime('%d de %B de %Y'),
        'total_estudiantes': total_estudiantes,
        'presentes': presentes,
        'ausentes': ausentes,
        'tardanzas': tardanzas,
        'sin_registro': total_estudiantes - (presentes + ausentes + tardanzas)
    }
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_dashboard_bienestar(request):
    """ API que devuelve la lista de alertas de bienestar. """
    user = request.user
    if not user.is_staff: return Response({'error': 'Acceso denegado.'}, status=403)
    
    user_inst = getattr(user, 'institucion_asociada', None)
    alertas = AnotacionObservador.objects.filter(requiere_revision=True)
    if user_inst:
        alertas = alertas.filter(estudiante__institucion=user_inst)
    
    data = [{
        'id': a.id, 
        'estudiante': a.estudiante.usuario.get_full_name(), 
        'fecha': a.fecha_hora, 
        'descripcion_corta': a.descripcion[:70] + '...'
    } for a in alertas.select_related('estudiante__usuario')]
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_supervisar_citas(request):
    """ API que devuelve la lista de todas las citas agendadas. """
    user = request.user
    if not user.is_staff: return Response({'error': 'Acceso denegado.'}, status=403)

    user_inst = getattr(user, 'institucion_asociada', None)
    citas = CitaReunion.objects.all()
    if user_inst:
        citas = citas.filter(docente__institucion=user_inst)
        
    data = [{
        'id': c.id, 
        'docente': c.docente.usuario.get_full_name(), 
        'familiar': c.familiar.usuario.get_full_name(),
        'estudiante': c.estudiante.usuario.get_full_name(),
        'fecha_hora': c.fecha_hora_inicio,
        'estado': c.get_estado_display()
    } for c in citas.select_related('docente__usuario', 'familiar__usuario', 'estudiante__usuario')]
    return Response(data)    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_admin_asistencia_diaria(request):
    user = request.user
    if not user.is_staff: return Response({'error': 'Acceso denegado.'}, status=403)
    user_inst = getattr(user, 'institucion_asociada', None)
    if not user_inst: return Response({'error': 'Usuario no asociado a una institución.'}, status=400)
    
    hoy = timezone.localdate()
    registros_hoy = RegistroAsistencia.objects.filter(estudiante__institucion=user_inst, fecha__date=hoy)
    total_estudiantes = Estudiante.objects.filter(institucion=user_inst, usuario__is_active=True).count()
    presentes = registros_hoy.filter(estado='PRESENTE').count()
    
    data = {
        'fecha': hoy.strftime('%d de %B de %Y'),
        'total_estudiantes': total_estudiantes,
        'presentes': presentes,
        'ausentes': registros_hoy.filter(estado='AUSENTE').count(),
        'tardanzas': registros_hoy.filter(estado='TARDANZA').count(),
    }
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_dashboard_bienestar(request):
    user = request.user
    if not user.is_staff: return Response({'error': 'Acceso denegado.'}, status=403)
    user_inst = getattr(user, 'institucion_asociada', None)
    alertas = AnotacionObservador.objects.filter(requiere_revision=True)
    if user_inst:
        alertas = alertas.filter(estudiante__institucion=user_inst)
    
    data = [{
        'id': a.id, 
        'estudiante': a.estudiante.usuario.get_full_name(), 
        'fecha': a.fecha_hora.strftime('%d/%m/%Y'), 
        'descripcion_corta': a.descripcion[:70] + '...'
    } for a in alertas.select_related('estudiante__usuario')]
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_supervisar_citas(request):
    user = request.user
    if not user.is_staff: return Response({'error': 'Acceso denegado.'}, status=403)
    user_inst = getattr(user, 'institucion_asociada', None)
    citas = CitaReunion.objects.all()
    if user_inst:
        citas = citas.filter(docente__institucion=user_inst)
        
    data = [{
        'id': c.id, 
        'docente': c.docente.usuario.get_full_name(), 
        'familiar': c.familiar.usuario.get_full_name(),
        'estudiante': c.estudiante.usuario.get_full_name(),
        'fecha_hora': c.fecha_hora_inicio.strftime('%d/%m/%Y %I:%M %p'),
        'estado': c.get_estado_display()
    } for c in citas.select_related('docente__usuario', 'familiar__usuario', 'estudiante__usuario')]
    return Response(data)    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_familiar_calificaciones_view(request, estudiante_pk):
    """ API que devuelve los cursos de un estudiante para que el familiar vea las calificaciones. """
    user = request.user
    if not hasattr(user, 'familiar'): return Response({'error': 'Acceso denegado.'}, status=403)
    try:
        estudiante = user.familiar.estudiantes_asociados.get(pk=estudiante_pk)
        periodo_activo = PeriodoAcademico.objects.filter(institucion=estudiante.institucion, activo=True).first()
        if not (periodo_activo and estudiante.grado_actual): return Response([])
        
        cursos = Curso.objects.filter(grado=estudiante.grado_actual, periodo_academico=periodo_activo).select_related('materia')
        data = [{'id_materia': c.materia.pk, 'nombre_materia': c.materia.nombre_materia} for c in cursos]
        return Response(data)
    except Estudiante.DoesNotExist:
        return Response({'error': 'No tienes permiso para ver este estudiante.'}, status=403)
    except Exception as e: return Response({'error': f'Ocurrió un error: {str(e)}'}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_familiar_boletin_view(request, estudiante_pk):
    """ API que devuelve los datos del boletín de un estudiante para su familiar. """
    user = request.user
    if not hasattr(user, 'familiar'): return Response({'error': 'Acceso denegado.'}, status=403)
    try:
        estudiante = user.familiar.estudiantes_asociados.get(pk=estudiante_pk)
        # (Aquí iría la misma lógica de cálculo de la vista `mi_boletin_api_view` para devolver el JSON del boletín)
        # Por simplicidad, devolvemos un mensaje de éxito por ahora.
        return Response({'mensaje': f"Datos del boletín para {estudiante.usuario.get_full_name()}"})
    except Estudiante.DoesNotExist:
        return Response({'error': 'No tienes permiso para ver este estudiante.'}, status=403)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_familiar_deberes_view(request, estudiante_pk):
    """ API que devuelve los deberes de un estudiante para su familiar. """
    user = request.user
    if not hasattr(user, 'familiar'): return Response({'error': 'Acceso denegado.'}, status=403)
    try:
        estudiante = user.familiar.estudiantes_asociados.get(pk=estudiante_pk)
        # (Aquí iría la misma lógica de la vista `mis_deberes_api_view` para devolver la lista de deberes)
        return Response({'mensaje': f"Lista de deberes para {estudiante.usuario.get_full_name()}"})
    except Estudiante.DoesNotExist:
        return Response({'error': 'No tienes permiso para ver este estudiante.'}, status=403)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_familiar_seleccionar_docente(request):
    """ API que devuelve la lista de docentes con los que un familiar puede agendar cita. """
    user = request.user
    if not hasattr(user, 'familiar'): return Response({'error': 'Acceso denegado.'}, status=403)
    try:
        estudiantes_asociados = user.familiar.estudiantes_asociados.all()
        cursos_hijos = Curso.objects.filter(grado__in=[e.grado_actual for e in estudiantes_asociados])
        docentes = Docente.objects.filter(cursos_impartidos__in=cursos_hijos).distinct().select_related('usuario')
        data = [{'id_docente': d.pk, 'nombre_completo': d.usuario.get_full_name()} for d in docentes]
        return Response(data)
    except Exception as e: return Response({'error': f'Ocurrió un error: {str(e)}'}, status=500)    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detalle_noticia_api_view(request, noticia_pk):
    """
    Devuelve el detalle completo de una noticia específica.
    VERSIÓN CORREGIDA CON LOS NOMBRES DE CAMPO REALES.
    """
    noticia = get_object_or_404(Noticia, pk=noticia_pk)
    
    data = {
        'id': noticia.pk,
        'titulo': noticia.titulo,
        'cuerpo': noticia.contenido,  # <-- CORRECCIÓN: Usa 'contenido' en lugar de 'cuerpo'
        'fecha': noticia.fecha_publicacion.strftime('%d de %B de %Y'),
        'imagen_url': request.build_absolute_uri(noticia.imagen_destacada.url) if noticia.imagen_destacada else None # <-- CORRECCIÓN: Usa 'imagen_destacada'
    }
    return Response(data)

