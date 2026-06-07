"""
gestion_academica/views/reportes.py
====================================
Todos los reportes académicos de HALU.
Extraído del monolito views.py (originalmente ~líneas 10388-11710).
"""
import random
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse
from django.db.models import Avg, Sum, Count, Q
from django.utils import timezone
from decimal import Decimal
import json
import openpyxl
from openpyxl.styles import Font, Alignment
from io import BytesIO
from collections import defaultdict, OrderedDict

from ..models import (
    Grado, Curso, Materia, PeriodoAcademico, Estudiante, Calificacion,
    ActividadCalificable, TipoActividad, EsquemaCalificacion, AnotacionObservador,
    RegistroAsistencia, MencionReconocimiento, EscalaCualitativa, DescriptorLogro,
    EvaluacionLogroPreescolar, LogroPreescolar, DimensionDesarrollo,
    PrediccionRiesgoEstudiante, AnalisisRiesgo, DirectorCurso, AreaAcademica,
    Docente, Familiar, Usuario, NivelEscolaridad, CasoConvivencia,
)
from ..utils import (
    calcular_estado_academico_curso,
    obtener_desempeno,
    analizar_riesgo_academico_curso,
)
from finanzas.models import InstitucionEducativa
from gestion_academica.decorators import requiere_pagos_al_dia
from utils.mensajes import mensaje_exito, mensaje_error, mostrar_mensaje

@login_required
def reportes_dashboard(request):
    """
    Dashboard central de reportes con KPIs institucionales en tiempo real.
    """
    institucion = getattr(request.user, 'institucion_asociada', None)
    today = timezone.localdate()

    # ── KPI 1: Total alumnos activos ─────────────────────────────────────
    total_alumnos = 0
    if institucion:
        total_alumnos = Estudiante.objects.filter(
            activo=True, institucion=institucion
        ).count()

    # ── KPI 2: Período académico activo ──────────────────────────────────
    periodo_activo = None
    if institucion:
        periodo_activo = PeriodoAcademico.objects.filter(
            institucion=institucion, activo=True
        ).first()

    # ── KPI 3: Promedio institucional (período activo) ────────────────────
    promedio_institucional = None
    if periodo_activo:
        avg = Calificacion.objects.filter(
            actividad_calificable__curso__periodo_academico=periodo_activo,
            actividad_calificable__curso__institucion=institucion,
            valor_numerico__isnull=False,
        ).aggregate(prom=Avg('valor_numerico'))['prom']
        if avg:
            promedio_institucional = round(float(avg), 1)

    # ── KPI 4: Asistencia hoy (% presentes) ──────────────────────────────
    asistencia_hoy_pct = None
    if institucion:
        total_hoy = RegistroAsistencia.objects.filter(
            fecha_solo=today, institucion=institucion
        ).count()
        if total_hoy > 0:
            presentes_hoy = RegistroAsistencia.objects.filter(
                fecha_solo=today, estado='PRESENTE', institucion=institucion
            ).count()
            asistencia_hoy_pct = round((presentes_hoy / total_hoy) * 100)

    # ── KPI 5: Alumnos en riesgo alto (último análisis) ───────────────────
    alumnos_riesgo = 0
    if institucion:
        alumnos_riesgo = (
            PrediccionRiesgoEstudiante.objects
            .filter(nivel_riesgo='ALTO', institucion=institucion)
            .values('estudiante')
            .distinct()
            .count()
        )

    # ── KPI 6: Casos Sentinel activos ─────────────────────────────────────
    casos_sentinel = 0
    if institucion:
        casos_sentinel = CasoConvivencia.objects.filter(
            estado__in=[
                CasoConvivencia.Estado.ABIERTO,
                CasoConvivencia.Estado.EN_SEGUIMIENTO,
                CasoConvivencia.Estado.VENCIDO,
            ],
            institucion=institucion,
        ).count()

    context = {
        'titulo_pagina': "Centro de Reportes",
        'total_alumnos': total_alumnos,
        'periodo_activo': periodo_activo,
        'promedio_institucional': promedio_institucional,
        'asistencia_hoy_pct': asistencia_hoy_pct,
        'alumnos_riesgo': alumnos_riesgo,
        'casos_sentinel': casos_sentinel,
        'institucion': institucion,
    }
    return render(request, 'gestion_academica/reportes/dashboard.html', context)


    
@login_required
def generar_boletin_dispatcher(request, estudiante_pk, periodo_pk):
    """
    Revisa el tipo de evaluación del grado del estudiante y redirige
    a la vista de generación de PDF correcta (cuantitativa o cualitativa).
    """
    estudiante = get_object_or_404(Estudiante.objects.select_related('grado_actual'), pk=estudiante_pk)
    
    # (Aquí puedes añadir la lógica de seguridad que usas en tus otras vistas de boletín
    # para verificar que el usuario (estudiante, familiar, staff) tiene permiso)

    if estudiante.grado_actual and estudiante.grado_actual.tipo_evaluacion == 'CUALITATIVO':
        # Si el grado es Cualitativo (Preescolar), redirigimos a la vista del boletín descriptivo.
        return redirect('gestion_academica:boletin_descriptivo_preescolar', estudiante_pk=estudiante.pk, periodo_pk=periodo_pk)
    else:
        # Para todos los demás casos (Cuantitativo), redirigimos al boletín numérico tradicional.
        return redirect('gestion_academica:boletin_imprimible', estudiante_pk=estudiante.pk, periodo_pk=periodo_pk)       

@login_required
def reporte_rendimiento_estudiante(request):
    """
    Vista MEJORADA para generar reportes de rendimiento.
    Distingue entre evaluación Cuantitativa (con gráfica) y Cualitativa.
    """
    grados = Grado.objects.all()
    periodos = PeriodoAcademico.objects.all().order_by('-año_escolar', '-fecha_inicio')
    
    grado_id = request.GET.get('grado')
    estudiante_id = request.GET.get('estudiante')
    periodo_id = request.GET.get('periodo')
    
    estudiantes_del_grado = Estudiante.objects.none()
    estudiante_seleccionado = None
    periodo_seleccionado = None
    contexto_reporte = {}

    if grado_id:
        estudiantes_del_grado = Estudiante.objects.filter(grado_actual__id=grado_id).select_related('usuario').order_by('usuario__last_name')

    if estudiante_id and periodo_id:
        estudiante_seleccionado = get_object_or_404(Estudiante.objects.select_related('grado_actual'), pk=estudiante_id)
        periodo_seleccionado = get_object_or_404(PeriodoAcademico, pk=periodo_id)
        
        # --- LÓGICA DE SELECCIÓN DE REPORTE ---
        if estudiante_seleccionado.grado_actual.tipo_evaluacion == 'CUALITATIVO':
            # --- LÓGICA PARA PREESCOLAR ---
            dimensiones = DimensionDesarrollo.objects.filter(institucion=estudiante_seleccionado.institucion).prefetch_related(
                Prefetch('logros_preescolar', queryset=LogroPreescolar.objects.filter(periodo=periodo_seleccionado, materia__cursos__grado=estudiante_seleccionado.grado_actual))
            )
            evaluaciones = EvaluacionLogroPreescolar.objects.filter(estudiante=estudiante_seleccionado, logro__periodo=periodo_seleccionado).select_related('estado')
            evaluaciones_map = {ev.logro_id: ev.estado for ev in evaluaciones}

            for dim in dimensiones:
                for logro in dim.logros_preescolar.all():
                    logro.evaluacion = evaluaciones_map.get(logro.id)

            contexto_reporte = {
                'tipo_reporte': 'CUALITATIVO',
                'dimensiones_data': dimensiones
            }
        else:
            # --- LÓGICA PARA PRIMARIA/SECUNDARIA (CUANTITATIVO) ---
            cursos_del_estudiante = Curso.objects.filter(
                grado=estudiante_seleccionado.grado_actual,
                periodo_academico=periodo_seleccionado
            ).select_related('materia').order_by('materia__nombre_materia')

            cursos_con_detalle = []
            promedio_numerador = 0
            promedio_denominador = 0
            
            # Datos para la gráfica
            chart_labels = []
            chart_data = []

            for curso in cursos_del_estudiante:
                nota_final_curso = Calificacion.objects.filter(
                    estudiante=estudiante_seleccionado,
                    actividad_calificable__curso=curso,
                    valor_numerico__isnull=False
                ).aggregate(promedio=Avg('valor_numerico'))['promedio']
                
                if nota_final_curso is not None:
                    promedio_numerador += nota_final_curso
                    promedio_denominador += 1
                    chart_labels.append(curso.materia.nombre_materia)
                    chart_data.append(float(nota_final_curso))
                
                cursos_con_detalle.append({
                    'curso': curso,
                    'nota_final_curso': nota_final_curso
                })

            promedio_general_calculado = (promedio_numerador / promedio_denominador) if promedio_denominador > 0 else None

            contexto_reporte = {
                'tipo_reporte': 'CUANTITATIVO',
                'cursos_con_detalle': cursos_con_detalle,
                'promedio_general_periodo': promedio_general_calculado,
                'chart_labels': json.dumps(chart_labels),
                'chart_data': json.dumps(chart_data)
            }

    context = {
        'titulo_pagina': "Reporte de Rendimiento Académico",
        'grados': grados,
        'estudiantes_del_grado': estudiantes_del_grado,
        'periodos': periodos,
        'grado_seleccionado_id': grado_id,
        'estudiante_seleccionado_id': estudiante_id,
        'periodo_seleccionado_id': periodo_id,
        'estudiante_seleccionado': estudiante_seleccionado,
        'periodo_seleccionado': periodo_seleccionado,
        'contexto_reporte': contexto_reporte,
    }
    
    return render(request, 'gestion_academica/reportes/rendimiento_estudiante.html', context)   


@login_required
def reporte_acumulado_periodo(request):
    """
    Muestra el rendimiento de un estudiante a lo largo de todos los periodos de un año.
    Distingue entre reportes cuantitativos y cualitativos, AMBOS CON GRÁFICOS.
    """
    grados = Grado.objects.all()
    años_escolares = PeriodoAcademico.objects.values_list('año_escolar', flat=True).distinct().order_by('-año_escolar')

    grado_id = request.GET.get('grado')
    estudiante_id = request.GET.get('estudiante')
    año_seleccionado_str = request.GET.get('año')
    
    año_seleccionado = int(año_seleccionado_str) if año_seleccionado_str else (años_escolares.first() or timezone.now().year)

    estudiantes_del_grado = Estudiante.objects.none()
    estudiante_seleccionado = None
    reporte_data = {}

    if grado_id:
        estudiantes_del_grado = Estudiante.objects.filter(grado_actual__id=grado_id).select_related('usuario').order_by('usuario__last_name')

    if estudiante_id:
        estudiante_seleccionado = get_object_or_404(Estudiante.objects.select_related('grado_actual'), pk=estudiante_id)
        periodos_del_año = PeriodoAcademico.objects.filter(año_escolar=año_seleccionado, institucion=estudiante_seleccionado.institucion).order_by('fecha_inicio')
        periodos_header = [p.nombre for p in periodos_del_año]

        if estudiante_seleccionado.grado_actual and estudiante_seleccionado.grado_actual.tipo_evaluacion == 'CUALITATIVO':
            # --- LÓGICA PARA REPORTE CUALITATIVO + GRÁFICO ---
            logros = LogroPreescolar.objects.filter(materia__cursos__grado=estudiante_seleccionado.grado_actual, periodo__in=periodos_del_año).select_related('dimension', 'materia').order_by('dimension__orden', 'orden')
            evaluaciones = EvaluacionLogroPreescolar.objects.filter(estudiante=estudiante_seleccionado, logro__in=logros).select_related('logro', 'estado')
            evaluaciones_map = {(ev.logro.periodo_id, ev.logro_id): ev.estado for ev in evaluaciones}
            
            logros_por_dimension = OrderedDict()
            unique_logros = set()
            for logro in logros:
                if logro.pk not in unique_logros:
                    dimension_nombre = logro.dimension.nombre
                    if dimension_nombre not in logros_por_dimension:
                        logros_por_dimension[dimension_nombre] = []
                    
                    evaluaciones_logro = []
                    for periodo in periodos_del_año:
                        evaluaciones_logro.append(evaluaciones_map.get((periodo.id, logro.id)))

                    logros_por_dimension[dimension_nombre].append({'logro': logro, 'evaluaciones': evaluaciones_logro})
                    unique_logros.add(logro.pk)

            # Preparar datos para el gráfico de barras apiladas
            escala = EscalaCualitativa.objects.filter(institucion=estudiante_seleccionado.institucion).order_by('orden')
            chart_datasets_cualitativo = []
            colores = ['rgba(75, 192, 192, 0.7)', 'rgba(255, 206, 86, 0.7)', 'rgba(255, 99, 132, 0.7)', 'rgba(153, 102, 255, 0.7)']
            for i, nivel_escala in enumerate(escala):
                data = []
                for periodo in periodos_del_año:
                    count = sum(1 for ev in evaluaciones if ev.logro.periodo == periodo and ev.estado == nivel_escala)
                    data.append(count)
                chart_datasets_cualitativo.append({'label': nivel_escala.nombre_escala, 'data': data, 'backgroundColor': colores[i % len(colores)]})

            reporte_data = {
                'tipo_reporte': 'CUALITATIVO', 'periodos_header': periodos_header,
                'logros_por_dimension': logros_por_dimension,
                'chart_labels': json.dumps(periodos_header),
                'chart_datasets': json.dumps(chart_datasets_cualitativo)
            }

        else:
            # --- LÓGICA PARA REPORTE CUANTITATIVO + GRÁFICO ---
            materias = Materia.objects.filter(cursos__grado=estudiante_seleccionado.grado_actual, cursos__periodo_academico__in=periodos_del_año).distinct().order_by('nombre_materia')
            notas_por_materia = OrderedDict()
            chart_datasets_cuantitativo = []

            for materia in materias:
                notas_periodos = []
                for periodo in periodos_del_año:
                    curso = Curso.objects.filter(materia=materia, periodo_academico=periodo, grado=estudiante_seleccionado.grado_actual).first()
                    nota_final = calcular_estado_academico_curso(curso, estudiante_seleccionado).get('nota_final_ponderada') if curso else None
                    notas_periodos.append(nota_final)
                notas_por_materia[materia.nombre_materia] = notas_periodos
                
                # Preparamos dataset para el gráfico de líneas
                color = f'rgb({random.randint(0, 255)}, {random.randint(0, 255)}, {random.randint(0, 255)})'
                chart_datasets_cuantitativo.append({
                    'label': materia.nombre_materia,
                    'data': [float(n) if n is not None else None for n in notas_periodos],
                    'borderColor': color,
                    'backgroundColor': color,
                    'fill': False,
                    'tension': 0.1
                })

            reporte_data = {
                'tipo_reporte': 'CUANTITATIVO', 'periodos_header': periodos_header,
                'notas_por_materia': notas_por_materia,
                'chart_labels': json.dumps(periodos_header),
                'chart_datasets': json.dumps(chart_datasets_cuantitativo)
            }

    context = {
        'titulo_pagina': "Reporte Acumulado por Periodo",
        'grados': grados, 'años_escolares': años_escolares, 'estudiantes_del_grado': estudiantes_del_grado,
        'grado_seleccionado_id': grado_id, 'estudiante_seleccionado_id': estudiante_id,
        'año_seleccionado': año_seleccionado, 'estudiante_seleccionado': estudiante_seleccionado,
        'reporte_data': reporte_data,
    }
    return render(request, 'gestion_academica/reportes/reporte_acumulado.html', context)

@login_required
def reporte_promedio_general_grado(request):
    """
    Muestra un ranking de estudiantes de un grado basado en su promedio
    general para un periodo específico. Incluye una gráfica comparativa.
    Solo funciona para grados con evaluación CUANTITATIVA.
    """
    grados = Grado.objects.filter(tipo_evaluacion='CUANTITATIVO') # Solo mostramos grados cuantitativos
    periodos = PeriodoAcademico.objects.all().order_by('-año_escolar', '-fecha_inicio')

    grado_id = request.GET.get('grado')
    periodo_id = request.GET.get('periodo')

    reporte_data = []
    grado_seleccionado = None
    periodo_seleccionado = None
    chart_labels = []
    chart_data = []

    if grado_id and periodo_id:
        grado_seleccionado = get_object_or_404(Grado, pk=grado_id)
        periodo_seleccionado = get_object_or_404(PeriodoAcademico, pk=periodo_id)
        
        estudiantes_del_grado = Estudiante.objects.filter(grado_actual=grado_seleccionado, activo=True)
        
        # Calculamos el promedio para cada estudiante
        for estudiante in estudiantes_del_grado:
            cursos = Curso.objects.filter(grado=estudiante.grado_actual, periodo_academico=periodo_seleccionado)
            
            total_puntos_ponderados = Decimal('0.0')
            total_ihs = 0
            
            for curso in cursos:
                estado_academico = calcular_estado_academico_curso(curso, estudiante)
                nota_final = estado_academico.get('nota_final_ponderada')
                ihs = curso.materia.intensidad_horaria_semanal

                if nota_final is not None and ihs > 0:
                    total_puntos_ponderados += nota_final * ihs
                    total_ihs += ihs
            
            promedio_general = total_puntos_ponderados / total_ihs if total_ihs > 0 else None
            
            if promedio_general is not None:
                reporte_data.append({'estudiante': estudiante, 'promedio': promedio_general})

        # Ordenamos la lista de mayor a menor promedio
        reporte_data = sorted(reporte_data, key=lambda x: x['promedio'], reverse=True)

        # Preparamos los datos para el gráfico de barras
        chart_labels = [item['estudiante'].usuario.get_full_name() for item in reporte_data]
        chart_data = [float(item['promedio']) for item in reporte_data]

    context = {
        'titulo_pagina': "Ranking de Estudiantes por Grado",
        'grados': grados,
        'periodos': periodos,
        'grado_seleccionado': grado_seleccionado,
        'periodo_seleccionado': periodo_seleccionado,
        'reporte_data': reporte_data,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
    }
    return render(request, 'gestion_academica/reportes/reporte_promedio_general.html', context)


@login_required
def reporte_estudiante_dashboard(request):
    """
    Muestra un dashboard consolidado con toda la información relevante de un
    único estudiante, adaptado para evaluación cuantitativa y cualitativa.
    """
    grados = Grado.objects.all()
    estudiantes_del_grado = Estudiante.objects.none()
    
    grado_id = request.GET.get('grado')
    estudiante_id = request.GET.get('estudiante')
    
    contexto_reporte = {}
    estudiante_seleccionado = None

    if grado_id:
        estudiantes_del_grado = Estudiante.objects.filter(grado_actual__id=grado_id).select_related('usuario').order_by('usuario__last_name')

    if estudiante_id:
        estudiante_seleccionado = get_object_or_404(Estudiante.objects.select_related('grado_actual', 'institucion'), pk=estudiante_id)
        institucion = estudiante_seleccionado.institucion
        periodo_activo = PeriodoAcademico.objects.filter(institucion=institucion, activo=True).first()
        
        # --- DATOS COMUNES ---
        anotaciones_recientes = AnotacionObservador.objects.filter(estudiante=estudiante_seleccionado).order_by('-fecha_hora')[:5]
        esta_al_dia = not CuentaPorCobrarEstudiante.objects.filter(estudiante=estudiante_seleccionado, estado='VENCIDO').exists()

        if estudiante_seleccionado.grado_actual and estudiante_seleccionado.grado_actual.tipo_evaluacion == 'CUALITATIVO':
            # --- LÓGICA PARA DASHBOARD CUALITATIVO (PREESCOLAR) ---
            logros_alcanzados = 0
            logros_en_proceso = 0
            if periodo_activo:
                evaluaciones = EvaluacionLogroPreescolar.objects.filter(estudiante=estudiante_seleccionado, logro__periodo=periodo_activo).select_related('estado')
                for ev in evaluaciones:
                    if "alcanzado" in ev.estado.nombre_escala.lower():
                        logros_alcanzados += 1
                    elif "proceso" in ev.estado.nombre_escala.lower():
                        logros_en_proceso += 1

            contexto_reporte = {
                'tipo_reporte': 'CUALITATIVO',
                'logros_alcanzados': logros_alcanzados,
                'logros_en_proceso': logros_en_proceso,
                'anotaciones_recientes': anotaciones_recientes,
                'esta_al_dia': esta_al_dia,
                # El gráfico para cualitativo podría ser un resumen total, lo añadiremos en un futuro reporte.
            }

        else:
            # --- LÓGICA PARA DASHBOARD CUANTITATIVO ---
            promedio_periodo_actual = None
            materias_en_riesgo = 0
            inasistencias = 0
            
            if periodo_activo:
                cursos = Curso.objects.filter(grado=estudiante_seleccionado.grado_actual, periodo_academico=periodo_activo)
                nota_minima = institucion.nota_minima_aprobacion if institucion else Decimal('3.0')
                
                total_puntos = Decimal('0.0')
                total_ihs = 0
                for curso in cursos:
                    estado = calcular_estado_academico_curso(curso, estudiante_seleccionado)
                    nota_final = estado.get('nota_final_ponderada')
                    if nota_final is not None:
                        if nota_final < nota_minima:
                            materias_en_riesgo += 1
                        if curso.materia.intensidad_horaria_semanal > 0:
                            total_puntos += nota_final * curso.materia.intensidad_horaria_semanal
                            total_ihs += curso.materia.intensidad_horaria_semanal
                
                promedio_periodo_actual = total_puntos / total_ihs if total_ihs > 0 else None
                inasistencias = RegistroAsistencia.objects.filter(estudiante=estudiante_seleccionado, curso__periodo_academico=periodo_activo, estado='AUSENTE').count()

            # Datos para el gráfico de evolución
            periodos_año = PeriodoAcademico.objects.filter(año_escolar=periodo_activo.año_escolar, institucion=institucion).order_by('fecha_inicio') if periodo_activo else []
            chart_labels = [p.nombre for p in periodos_año]
            chart_data = []
            for p in periodos_año:
                # Lógica similar para calcular el promedio en cada periodo del año
                cursos_p = Curso.objects.filter(grado=estudiante_seleccionado.grado_actual, periodo_academico=p)
                total_puntos_p = Decimal('0.0')
                total_ihs_p = 0
                for c in cursos_p:
                    estado_p = calcular_estado_academico_curso(c, estudiante_seleccionado)
                    nota_p = estado_p.get('nota_final_ponderada')
                    if nota_p and c.materia.intensidad_horaria_semanal > 0:
                        total_puntos_p += nota_p * c.materia.intensidad_horaria_semanal
                        total_ihs_p += c.materia.intensidad_horaria_semanal
                promedio_p = total_puntos_p / total_ihs_p if total_ihs_p > 0 else None
                chart_data.append(float(promedio_p) if promedio_p else None)

            contexto_reporte = {
                'tipo_reporte': 'CUANTITATIVO',
                'promedio_actual': promedio_periodo_actual,
                'materias_riesgo': materias_en_riesgo,
                'inasistencias': inasistencias,
                'esta_al_dia': esta_al_dia,
                'anotaciones_recientes': anotaciones_recientes,
                'chart_labels': json.dumps(chart_labels),
                'chart_data': json.dumps(chart_data),
            }

    context = {
        'titulo_pagina': "Dashboard del Estudiante",
        'grados': grados,
        'estudiantes_del_grado': estudiantes_del_grado,
        'grado_seleccionado_id': grado_id,
        'estudiante_seleccionado_id': estudiante_id,
        'estudiante_seleccionado': estudiante_seleccionado,
        'contexto_reporte': contexto_reporte,
    }
    return render(request, 'gestion_academica/reportes/reporte_estudiante_dashboard.html', context)

@login_required
def reporte_rendimiento_por_grado(request):
    """
    Muestra el promedio por materia (cuantitativo) o un resumen de logros (cualitativo)
    para un grado y periodo específicos. Incluye gráficos para ambos casos.
    VERSIÓN CORREGIDA PARA PREESCOLAR.
    """
    grados = Grado.objects.all().order_by('orden', 'nombre')
    periodos = PeriodoAcademico.objects.all().order_by('-año_escolar', '-fecha_inicio')

    grado_id = request.GET.get('grado')
    periodo_id = request.GET.get('periodo')

    reporte_data = {}
    grado_seleccionado = None
    periodo_seleccionado = None

    if grado_id and periodo_id:
        grado_seleccionado = get_object_or_404(Grado, pk=grado_id)
        periodo_seleccionado = get_object_or_404(PeriodoAcademico, pk=periodo_id)
        
        if grado_seleccionado.tipo_evaluacion == 'CUALITATIVO':
            # --- LÓGICA MEJORADA PARA REPORTE CUALITATIVO POR GRADO ---
            # 1. Obtenemos todas las escalas posibles para usarlas como base.
            escala_completa = EscalaCualitativa.objects.filter(institucion=grado_seleccionado.institucion).order_by('orden')
            
            # 2. Inicializamos nuestro contador con todas las escalas en cero.
            conteo_por_escala = OrderedDict((escala.nombre_escala, 0) for escala in escala_completa)

            # 3. Buscamos las evaluaciones existentes.
            estudiantes = Estudiante.objects.filter(grado_actual=grado_seleccionado, activo=True)
            evaluaciones = EvaluacionLogroPreescolar.objects.filter(
                estudiante__in=estudiantes,
                logro__periodo=periodo_seleccionado
            ).select_related('estado')

            # 4. Actualizamos el conteo con los datos reales.
            for ev in evaluaciones:
                if ev.estado and ev.estado.nombre_escala in conteo_por_escala:
                    conteo_por_escala[ev.estado.nombre_escala] += 1
            
            reporte_data = {
                'tipo_reporte': 'CUALITATIVO',
                'conteo_logros': conteo_por_escala,
                'total_evaluaciones': sum(conteo_por_escala.values())
            }
            # 5. Preparamos los datos para el gráfico (ahora nunca estarán vacíos).
            chart_labels = list(conteo_por_escala.keys())
            chart_data = list(conteo_por_escala.values())

        else:
            # --- LÓGICA CUANTITATIVA (SIN CAMBIOS) ---
            cursos_del_grado = Curso.objects.filter(grado=grado_seleccionado, periodo_academico=periodo_seleccionado)
            datos_cuantitativos = []
            
            for curso in cursos_del_grado:
                promedio_curso = Calificacion.objects.filter(
                    actividad_calificable__curso=curso, valor_numerico__isnull=False
                ).aggregate(promedio=Avg('valor_numerico'))['promedio']

                if promedio_curso is not None:
                    datos_cuantitativos.append({'materia': curso.materia.nombre_materia, 'promedio': promedio_curso})
            
            datos_cuantitativos = sorted(datos_cuantitativos, key=lambda x: x['promedio'], reverse=True)
            
            reporte_data = {
                'tipo_reporte': 'CUANTITATIVO',
                'datos_tabla': datos_cuantitativos,
            }
            chart_labels = [item['materia'] for item in datos_cuantitativos]
            chart_data = [float(item['promedio']) for item in datos_cuantitativos]

        reporte_data['chart_labels'] = json.dumps(chart_labels)
        reporte_data['chart_data'] = json.dumps(chart_data)

    context = {
        'titulo_pagina': "Rendimiento General por Grado",
        'grados': grados, 'periodos': periodos,
        'grado_seleccionado': grado_seleccionado, 'periodo_seleccionado': periodo_seleccionado,
        'reporte_data': reporte_data,
    }
    return render(request, 'gestion_academica/reportes/reporte_rendimiento_grado.html', context)  

@login_required
def reporte_promedio_por_area(request):
    """
    Muestra el promedio por Área (cuantitativo) o un resumen de logros por
    Dimensión (cualitativo). VERSIÓN CORREGIDA PARA INCLUIR PREESCOLAR.
    """
    grados = Grado.objects.all().order_by('orden', 'nombre')
    periodos = PeriodoAcademico.objects.all().order_by('-año_escolar', '-fecha_inicio')

    grado_id = request.GET.get('grado')
    periodo_id = request.GET.get('periodo')

    reporte_data = {}
    grado_seleccionado = None
    periodo_seleccionado = None

    if grado_id and periodo_id:
        grado_seleccionado = get_object_or_404(Grado, pk=grado_id)
        periodo_seleccionado = get_object_or_404(PeriodoAcademico, pk=periodo_id)
        institucion = grado_seleccionado.institucion

        if grado_seleccionado.tipo_evaluacion == 'CUALITATIVO':
            # --- LÓGICA PARA REPORTE CUALITATIVO POR DIMENSIÓN ---
            dimensiones = DimensionDesarrollo.objects.filter(institucion=institucion).order_by('orden')
            estudiantes = Estudiante.objects.filter(grado_actual=grado_seleccionado, activo=True)
            
            datos_cualitativos = []
            conteo_general_por_escala = OrderedDict((escala.nombre_escala, 0) for escala in EscalaCualitativa.objects.filter(institucion=institucion))

            for dimension in dimensiones:
                logros_dimension = LogroPreescolar.objects.filter(dimension=dimension, periodo=periodo_seleccionado)
                evaluaciones = EvaluacionLogroPreescolar.objects.filter(
                    estudiante__in=estudiantes, logro__in=logros_dimension
                ).select_related('estado')
                
                conteo_dimension = defaultdict(int)
                for ev in evaluaciones:
                    if ev.estado:
                        conteo_dimension[ev.estado.nombre_escala] += 1
                        if ev.estado.nombre_escala in conteo_general_por_escala:
                             conteo_general_por_escala[ev.estado.nombre_escala] +=1

                datos_cualitativos.append({'dimension': dimension.nombre, 'conteo': dict(conteo_dimension)})

            reporte_data = {
                'tipo_reporte': 'CUALITATIVO',
                'datos_tabla': datos_cualitativos,
                'chart_labels': json.dumps(list(conteo_general_por_escala.keys())),
                'chart_data': json.dumps(list(conteo_general_por_escala.values()))
            }
        else:
            # --- LÓGICA CUANTITATIVA ---
            areas_academicas = AreaAcademica.objects.filter(institucion=institucion)
            datos_cuantitativos = []
            for area in areas_academicas:
                materias_del_area = area.materias.all()
                promedio_area = Calificacion.objects.filter(
                    actividad_calificable__curso__grado=grado_seleccionado,
                    actividad_calificable__curso__periodo_academico=periodo_seleccionado,
                    actividad_calificable__curso__materia__in=materias_del_area,
                    valor_numerico__isnull=False
                ).aggregate(promedio=Avg('valor_numerico'))['promedio']
                if promedio_area is not None:
                    datos_cuantitativos.append({'area': area.nombre, 'promedio': promedio_area})
            
            datos_cuantitativos = sorted(datos_cuantitativos, key=lambda x: x['promedio'], reverse=True)
            reporte_data = {
                'tipo_reporte': 'CUANTITATIVO',
                'datos_tabla': datos_cuantitativos,
                'chart_labels': json.dumps([item['area'] for item in datos_cuantitativos]),
                'chart_data': json.dumps([float(item['promedio']) for item in datos_cuantitativos])
            }
            
    context = {
        'titulo_pagina': "Rendimiento por Áreas Académicas",
        'grados': grados, 'periodos': periodos,
        'grado_seleccionado': grado_seleccionado, 'periodo_seleccionado': periodo_seleccionado,
        'reporte_data': reporte_data,
    }
    return render(request, 'gestion_academica/reportes/reporte_promedio_area.html', context) 

@login_required
def reporte_final_reprobacion(request):
    """
    Genera un informe de fin de año con los estudiantes que reprobaron una o
    más materias. Se adapta a evaluaciones cuantitativas y cualitativas.
    """
    grados = Grado.objects.all().order_by('orden', 'nombre')
    años_escolares = PeriodoAcademico.objects.values_list('año_escolar', flat=True).distinct().order_by('-año_escolar')
    
    grado_id = request.GET.get('grado')
    año_seleccionado_str = request.GET.get('año')
    año_seleccionado = int(año_seleccionado_str) if año_seleccionado_str else (años_escolares.first() or timezone.now().year)

    reporte_data = {}
    grado_seleccionado = None

    if grado_id:
        grado_seleccionado = get_object_or_404(Grado, pk=grado_id)
        estudiantes_del_grado = Estudiante.objects.filter(grado_actual=grado_seleccionado, activo=True)
        periodos_del_año = PeriodoAcademico.objects.filter(año_escolar=año_seleccionado, institucion=grado_seleccionado.institucion)
        
        estudiantes_reprobados = defaultdict(list)
        conteo_reprobados_por_materia = defaultdict(int)

        if grado_seleccionado.tipo_evaluacion == 'CUALITATIVO':
            # --- LÓGICA PARA REPROBACIÓN CUALITATIVA ---
            escala_reprobado = EscalaCualitativa.objects.filter(institucion=grado_seleccionado.institucion, es_reprobatoria=True).first()
            if escala_reprobado:
                materias = Materia.objects.filter(cursos__grado=grado_seleccionado, cursos__periodo_academico__in=periodos_del_año).distinct()
                for estudiante in estudiantes_del_grado:
                    for materia in materias:
                        # Contamos si en el último periodo tuvo una evaluación reprobatoria en algún logro de esa materia
                        logros_reprobados = EvaluacionLogroPreescolar.objects.filter(
                            estudiante=estudiante,
                            logro__materia=materia,
                            logro__periodo=periodos_del_año.order_by('-fecha_fin').first(),
                            estado=escala_reprobado
                        ).exists()
                        if logros_reprobados:
                            estudiantes_reprobados[estudiante].append(materia.nombre_materia)
                            conteo_reprobados_por_materia[materia.nombre_materia] += 1
        
        else:
            # --- LÓGICA PARA REPROBACIÓN CUANTITATIVA ---
            nota_minima = grado_seleccionado.institucion.nota_minima_aprobacion
            cursos_del_grado = Curso.objects.filter(grado=grado_seleccionado, periodo_academico__in=periodos_del_año).select_related('materia')
            materias_del_grado = Materia.objects.filter(cursos__in=cursos_del_grado).distinct()

            for estudiante in estudiantes_del_grado:
                promedio_anual_por_materia = {}
                for materia in materias_del_grado:
                    cursos_materia_año = cursos_del_grado.filter(materia=materia)
                    notas_periodos = []
                    for curso in cursos_materia_año:
                        estado = calcular_estado_academico_curso(curso, estudiante)
                        nota_final = estado.get('nota_final_ponderada')
                        if nota_final is not None:
                            notas_periodos.append(nota_final)
                    
                    if notas_periodos:
                        promedio_anual_materia = sum(notas_periodos) / len(notas_periodos)
                        if promedio_anual_materia < nota_minima:
                            estudiantes_reprobados[estudiante].append(f"{materia.nombre_materia} ({promedio_anual_materia:.2f})")
                            conteo_reprobados_por_materia[materia.nombre_materia] += 1

        # Preparar datos para el gráfico
        chart_labels = list(conteo_reprobados_por_materia.keys())
        chart_data = list(conteo_reprobados_por_materia.values())

        reporte_data = {
            'estudiantes_reprobados': dict(estudiantes_reprobados),
            'chart_labels': json.dumps(chart_labels),
            'chart_data': json.dumps(chart_data)
        }

    context = {
        'titulo_pagina': "Informe Final de Reprobación",
        'grados': grados,
        'años_escolares': años_escolares,
        'grado_seleccionado': grado_seleccionado,
        'año_seleccionado': año_seleccionado,
        'reporte_data': reporte_data,
    }
    return render(request, 'gestion_academica/reportes/reporte_reprobacion.html', context)    

@login_required
def reporte_consolidado_materia(request):
    """
    Muestra una planilla de notas detallada (consolidado).
    VERSIÓN FINAL: Asegura que el gráfico cualitativo siempre se muestre.
    """
    grados = Grado.objects.all().order_by('orden', 'nombre')
    periodos = PeriodoAcademico.objects.all().order_by('-año_escolar', '-fecha_inicio')
    materias_del_grado = Materia.objects.none()

    grado_id = request.GET.get('grado')
    periodo_id = request.GET.get('periodo')
    materia_id = request.GET.get('materia')

    reporte_data = {}
    grado_seleccionado = None
    periodo_seleccionado = None
    materia_seleccionada = None

    if grado_id:
        grado_seleccionado = get_object_or_404(Grado, pk=grado_id)
        materias_del_grado = Materia.objects.filter(cursos__grado=grado_seleccionado).distinct().order_by('nombre_materia')
    if periodo_id:
        periodo_seleccionado = get_object_or_404(PeriodoAcademico, pk=periodo_id)

    if grado_seleccionado and periodo_seleccionado:
        estudiantes = Estudiante.objects.filter(grado_actual=grado_seleccionado, activo=True).select_related('usuario').order_by('usuario__last_name')
        institucion = grado_seleccionado.institucion

        if grado_seleccionado.tipo_evaluacion == 'CUALITATIVO':
            # --- LÓGICA DE GRÁFICO CORREGIDA PARA CUALITATIVO ---
            logros = LogroPreescolar.objects.filter(periodo=periodo_seleccionado, materia__cursos__grado=grado_seleccionado).distinct().select_related('dimension').order_by('dimension__orden', 'orden')
            evaluaciones = EvaluacionLogroPreescolar.objects.filter(estudiante__in=estudiantes, logro__in=logros)
            evaluaciones_map = {(ev.estudiante_id, ev.logro_id): ev.estado for ev in evaluaciones}
            
            logros_agrupados_por_dimension = OrderedDict()
            for logro in logros:
                if logro.dimension not in logros_agrupados_por_dimension:
                    logros_agrupados_por_dimension[logro.dimension] = []
                logros_agrupados_por_dimension[logro.dimension].append(logro)

            datos_tabla_cualitativa = []
            for est in estudiantes:
                evaluaciones_ordenadas = [evaluaciones_map.get((est.pk, logro.pk)) for logro in logros]
                datos_tabla_cualitativa.append({'estudiante': est, 'evaluaciones': evaluaciones_ordenadas})
            
            # 1. Obtenemos todas las escalas de la institución
            escala_completa = EscalaCualitativa.objects.filter(institucion=institucion).order_by('orden')
            # 2. Inicializamos el contador con todas las escalas en CERO
            conteo_desempenos = OrderedDict((escala.nombre_escala, 0) for escala in escala_completa)
            # 3. Actualizamos el conteo con las evaluaciones que sí existen
            for ev in evaluaciones:
                if ev.estado and ev.estado.nombre_escala in conteo_desempenos:
                    conteo_desempenos[ev.estado.nombre_escala] += 1
            
            reporte_data = {
                'tipo_reporte': 'CUALITATIVO', 'logros_agrupados': logros_agrupados_por_dimension,
                'datos_tabla': datos_tabla_cualitativa,
                'chart_labels': json.dumps(list(conteo_desempenos.keys())), # Esta lista nunca estará vacía
                'chart_data': json.dumps(list(conteo_desempenos.values())) # Podrá tener ceros, pero existirá
            }
        
        elif materia_id:
            # Lógica cuantitativa (sin cambios)
            materia_seleccionada = get_object_or_404(Materia, pk=materia_id)
            curso = Curso.objects.filter(grado=grado_seleccionado, periodo_academico=periodo_seleccionado, materia=materia_seleccionada).first()
            datos_tabla_cuantitativa = []
            notas_finales_para_grafico = []
            if curso:
                actividades = ActividadCalificable.objects.filter(curso=curso).order_by('fecha_publicacion')
                calificaciones = Calificacion.objects.filter(actividad_calificable__in=actividades)
                calificaciones_map = {(cal.estudiante_id, cal.actividad_calificable_id): cal.valor_numerico for cal in calificaciones}
                for est in estudiantes:
                    # ... (resto de la lógica cuantitativa sin cambios) ...
                    estado = calcular_estado_academico_curso(curso, est)
                    nota_final = estado.get('nota_final_ponderada')
                    if nota_final is not None:
                        notas_finales_para_grafico.append(nota_final)
                    datos_tabla_cuantitativa.append({'estudiante': est, 'calificaciones': [calificaciones_map.get((est.pk, act.pk)) for act in actividades], 'nota_final': nota_final})
                
                rangos = {"Reprobado": 0, "Básico": 0, "Alto": 0, "Superior": 0}
                nota_minima = institucion.nota_minima_aprobacion
                for nota in notas_finales_para_grafico:
                    if nota < nota_minima: rangos["Reprobado"] += 1
                    elif nota < 4.0: rangos["Básico"] += 1
                    elif nota < 4.6: rangos["Alto"] += 1
                    else: rangos["Superior"] += 1
                
                reporte_data = {
                    'tipo_reporte': 'CUANTITATIVO', 'actividades_header': actividades,
                    'datos_tabla': datos_tabla_cuantitativa,
                    'chart_labels': json.dumps(list(rangos.keys())),
                    'chart_data': json.dumps(list(rangos.values()))
                }
            
    context = {
        'titulo_pagina': "Consolidado de Notas por Materia",
        'grados': grados, 'periodos': periodos, 'materias_del_grado': materias_del_grado,
        'grado_seleccionado': grado_seleccionado, 'periodo_seleccionado': periodo_seleccionado,
        'materia_seleccionada': materia_seleccionada, 'reporte_data': reporte_data,
    }
    return render(request, 'gestion_academica/reportes/reporte_consolidado_materia.html', context)


@login_required
def reporte_consolidado_areas(request):
    """
    Muestra un consolidado por Área (cuantitativo) o por Dimensión (cualitativo).
    VERSIÓN CORREGIDA Y DEFINITIVA PARA INCLUIR PREESCOLAR.
    """
    # CORRECCIÓN: Quitamos el filtro inicial para mostrar TODOS los grados
    grados = Grado.objects.all().order_by('orden', 'nombre')
    periodos = PeriodoAcademico.objects.all().order_by('-año_escolar', '-fecha_inicio')

    grado_id = request.GET.get('grado')
    periodo_id = request.GET.get('periodo')

    reporte_data = {}
    grado_seleccionado = None
    periodo_seleccionado = None

    if grado_id and periodo_id:
        grado_seleccionado = get_object_or_404(Grado, pk=grado_id)
        periodo_seleccionado = get_object_or_404(PeriodoAcademico, pk=periodo_id)
        institucion = grado_seleccionado.institucion
        estudiantes = Estudiante.objects.filter(grado_actual=grado_seleccionado, activo=True).select_related('usuario')

        if grado_seleccionado.tipo_evaluacion == 'CUALITATIVO':
            # --- LÓGICA PARA CONSOLIDADO CUALITATIVO POR DIMENSIÓN ---
            dimensiones = DimensionDesarrollo.objects.filter(institucion=institucion).order_by('orden')
            datos_tabla = []
            conteo_general_para_grafico = defaultdict(int)

            for estudiante in estudiantes:
                resumen_por_dimension = OrderedDict()
                for dimension in dimensiones:
                    evaluaciones = EvaluacionLogroPreescolar.objects.filter(
                        estudiante=estudiante, logro__dimension=dimension, logro__periodo=periodo_seleccionado
                    ).select_related('estado')
                    
                    resumen_dimension = defaultdict(int)
                    for ev in evaluaciones:
                        if ev.estado:
                            resumen_dimension[ev.estado.abreviatura] += 1
                            conteo_general_para_grafico[ev.estado.nombre_escala] += 1
                    
                    resumen_por_dimension[dimension.nombre] = dict(resumen_dimension)
                
                datos_tabla.append({'estudiante': estudiante, 'resumen_por_dimension': resumen_por_dimension})

            reporte_data = {
                'tipo_reporte': 'CUALITATIVO', 'areas_header': dimensiones,
                'datos_tabla': datos_tabla,
                'chart_labels': json.dumps(list(conteo_general_para_grafico.keys())),
                'chart_data': json.dumps(list(conteo_general_para_grafico.values()))
            }
        
        else:
            # --- LÓGICA PARA CONSOLIDADO CUANTITATIVO POR ÁREA ---
            areas = AreaAcademica.objects.filter(institucion=institucion).prefetch_related('materias')
            datos_tabla = []
            conteo_desempenos_por_area = OrderedDict((area.nombre, defaultdict(int)) for area in areas)

            for estudiante in estudiantes:
                promedios_por_area = OrderedDict()
                notas_para_promedio_general = []

                for area in areas:
                    materias_del_area = area.materias.all()
                    cursos_del_area = Curso.objects.filter(grado=grado_seleccionado, periodo_academico=periodo_seleccionado, materia__in=materias_del_area)
                    notas_finales_area = [estado.get('nota_final_ponderada') for curso in cursos_del_area if (estado := calcular_estado_academico_curso(curso, estudiante)) and estado.get('nota_final_ponderada') is not None]
                    promedio_area = sum(notas_finales_area) / len(notas_finales_area) if notas_finales_area else None
                    promedios_por_area[area.nombre] = promedio_area
                    if promedio_area:
                        notas_para_promedio_general.append(promedio_area)
                        desempeno = obtener_desempeno(promedio_area, institucion)
                        if desempeno: conteo_desempenos_por_area[area.nombre][desempeno] += 1
                
                promedio_general_estudiante = sum(notas_para_promedio_general) / len(notas_para_promedio_general) if notas_para_promedio_general else None
                datos_tabla.append({'estudiante': estudiante, 'promedios_por_area': promedios_por_area, 'promedio_general': promedio_general_estudiante})
            
            escalas = EscalaValorativa.objects.filter(institucion=institucion).order_by('orden')
            chart_labels = list(conteo_desempenos_por_area.keys())
            chart_datasets = [{'label': esc.nombre_desempeno, 'data': [conteo_desempenos_por_area[area][esc.abreviatura] for area in chart_labels], 'backgroundColor': ['rgba(220, 53, 69, 0.7)','rgba(255, 193, 7, 0.7)','rgba(25, 135, 84, 0.7)','rgba(13, 110, 253, 0.7)'][i % 4]} for i, esc in enumerate(escalas)]
            
            reporte_data = {
                'tipo_reporte': 'CUANTITATIVO', 'areas_header': areas,
                'datos_tabla': datos_tabla,
                'chart_labels': json.dumps(chart_labels),
                'chart_datasets': json.dumps(chart_datasets)
            }

    context = {
        'titulo_pagina': "Consolidado por Áreas Académicas",
        'grados': grados, 'periodos': periodos,
        'grado_seleccionado': grado_seleccionado, 'periodo_seleccionado': periodo_seleccionado,
        'reporte_data': reporte_data,
    }
    return render(request, 'gestion_academica/reportes/reporte_consolidado_areas.html', context)

@login_required
def reporte_ranking_institucion(request):
    """
    Vista que INICIA la tarea de Celery para el ranking y muestra
    una página para esperar y ver los resultados.
    """
    periodos = PeriodoAcademico.objects.all().order_by('-año_escolar', '-fecha_inicio')
    periodo_id = request.GET.get('periodo')
    task_id = None

    if periodo_id:
        # En lugar de calcular aquí, llamamos a la tarea con .delay()
        # Esto envía la tarea a Redis y devuelve inmediatamente un ID.
        task = generar_ranking_institucional_task.delay(periodo_id)
        task_id = task.id

    context = {
        'titulo_pagina': "Ranking General de la Institución",
        'periodos': periodos,
        'periodo_seleccionado_id': periodo_id,
        'task_id': task_id, # Pasamos el ID de la tarea a la plantilla
    }
    return render(request, 'gestion_academica/reportes/reporte_ranking_institucion.html', context)

@login_required
def reporte_promedio_cualitativo(request):
    """
    Genera un resumen estadístico y un gráfico de pastel con la distribución
    de los desempeños cualitativos para un grado de preescolar en un periodo.
    """
    # Filtramos para que en el selector solo aparezcan grados cualitativos
    grados = Grado.objects.filter(tipo_evaluacion='CUALITATIVO').order_by('orden', 'nombre')
    periodos = PeriodoAcademico.objects.all().order_by('-año_escolar', '-fecha_inicio')

    grado_id = request.GET.get('grado')
    periodo_id = request.GET.get('periodo')

    reporte_data = {}
    grado_seleccionado = None
    periodo_seleccionado = None

    if grado_id and periodo_id:
        grado_seleccionado = get_object_or_404(Grado, pk=grado_id)
        periodo_seleccionado = get_object_or_404(PeriodoAcademico, pk=periodo_id)
        institucion = grado_seleccionado.institucion

        # 1. Obtenemos todas las escalas posibles de la institución para usarlas como base
        escala_completa = EscalaCualitativa.objects.filter(institucion=institucion).order_by('orden')
        
        # 2. Inicializamos el contador con todas las escalas en cero
        conteo_desempenos = OrderedDict((escala.nombre_escala, 0) for escala in escala_completa)

        # 3. Buscamos todas las evaluaciones existentes para ese grado y periodo
        estudiantes = Estudiante.objects.filter(grado_actual=grado_seleccionado, activo=True)
        evaluaciones = EvaluacionLogroPreescolar.objects.filter(
            estudiante__in=estudiantes,
            logro__periodo=periodo_seleccionado
        ).select_related('estado')

        # 4. Actualizamos el conteo con los datos reales
        for ev in evaluaciones:
            if ev.estado and ev.estado.nombre_escala in conteo_desempenos:
                conteo_desempenos[ev.estado.nombre_escala] += 1
        
        total_evaluaciones = sum(conteo_desempenos.values())
        
        # 5. Preparamos los datos para la tabla y el gráfico
        datos_tabla = []
        for nombre, cantidad in conteo_desempenos.items():
            porcentaje = (cantidad / total_evaluaciones * 100) if total_evaluaciones > 0 else 0
            datos_tabla.append({
                'escala': nombre,
                'cantidad': cantidad,
                'porcentaje': porcentaje
            })

        reporte_data = {
            'datos_tabla': datos_tabla,
            'total_evaluaciones': total_evaluaciones,
            'chart_labels': json.dumps(list(conteo_desempenos.keys())),
            'chart_data': json.dumps(list(conteo_desempenos.values()))
        }

    context = {
        'titulo_pagina': "Resumen de Desempeño Cualitativo por Grado",
        'grados': grados,
        'periodos': periodos,
        'grado_seleccionado': grado_seleccionado,
        'periodo_seleccionado': periodo_seleccionado,
        'reporte_data': reporte_data,
    }
    return render(request, 'gestion_academica/reportes/reporte_promedio_cualitativo.html', context) 


@login_required
def reporte_promedio_por_materia(request):
    """
    Muestra el rendimiento promedio de una materia específica a través de
    todos los grados en los que se imparte durante un periodo.
    """
    # Para los filtros, mostramos todas las materias y periodos de la institución
    materias = Materia.objects.all().order_by('nombre_materia')
    periodos = PeriodoAcademico.objects.all().order_by('-año_escolar', '-fecha_inicio')

    materia_id = request.GET.get('materia')
    periodo_id = request.GET.get('periodo')

    reporte_data = {}
    materia_seleccionada = None
    periodo_seleccionado = None

    if materia_id and periodo_id:
        materia_seleccionada = get_object_or_404(Materia, pk=materia_id)
        periodo_seleccionado = get_object_or_404(PeriodoAcademico, pk=periodo_id)
        
        # 1. Encontramos todos los cursos de esa materia en ese periodo
        cursos_de_la_materia = Curso.objects.filter(
            materia=materia_seleccionada,
            periodo_academico=periodo_seleccionado,
            grado__tipo_evaluacion='CUANTITATIVO' # Solo en grados cuantitativos
        ).select_related('grado')

        datos_tabla = []
        for curso in cursos_de_la_materia:
            # 2. Para cada curso (es decir, para cada grado), calculamos el promedio general
            promedio_grado_en_materia = Calificacion.objects.filter(
                actividad_calificable__curso=curso,
                valor_numerico__isnull=False
            ).aggregate(
                promedio=Avg('valor_numerico')
            )['promedio']

            if promedio_grado_en_materia is not None:
                datos_tabla.append({
                    'grado': curso.grado,
                    'promedio': promedio_grado_en_materia
                })

        # 3. Preparamos los datos para la tabla y el gráfico
        datos_tabla = sorted(datos_tabla, key=lambda x: x['grado'].orden)
        
        reporte_data = {
            'datos_tabla': datos_tabla,
            'chart_labels': json.dumps([item['grado'].nombre for item in datos_tabla]),
            'chart_data': json.dumps([float(item['promedio']) for item in datos_tabla])
        }

    context = {
        'titulo_pagina': "Rendimiento Comparativo por Materia",
        'materias': materias,
        'periodos': periodos,
        'materia_seleccionada': materia_seleccionada,
        'periodo_seleccionado': periodo_seleccionado,
        'reporte_data': reporte_data,
    }
    return render(request, 'gestion_academica/reportes/reporte_promedio_materia.html', context)

          
@login_required
def cuadro_honor_grado(request):
    """
    Muestra un ranking de estudiantes DENTRO de un grado específico.
    VERSIÓN CORREGIDA: Muestra todos los grados y maneja la selección.
    """
    # CORRECCIÓN: Quitamos el filtro para mostrar TODOS los grados
    grados = Grado.objects.all().order_by('orden', 'nombre')
    periodos = PeriodoAcademico.objects.all().order_by('-año_escolar', '-fecha_inicio')

    grado_id = request.GET.get('grado')
    periodo_id = request.GET.get('periodo')

    reporte_data = []
    grado_seleccionado = None
    periodo_seleccionado = None
    
    # Esta nueva variable nos dirá si el reporte no aplica
    reporte_no_aplica = False

    if grado_id and periodo_id:
        grado_seleccionado = get_object_or_404(Grado, pk=grado_id)
        periodo_seleccionado = get_object_or_404(PeriodoAcademico, pk=periodo_id)
        
        # VERIFICAMOS EL TIPO DE EVALUACIÓN DESPUÉS DE SELECCIONAR
        if grado_seleccionado.tipo_evaluacion == 'CUANTITATIVO':
            estudiantes_del_grado = Estudiante.objects.filter(grado_actual=grado_seleccionado, activo=True)
            
            for estudiante in estudiantes_del_grado:
                cursos = Curso.objects.filter(grado=estudiante.grado_actual, periodo_academico=periodo_seleccionado)
                total_puntos_ponderados = Decimal('0.0')
                total_ihs = 0
                for curso in cursos:
                    estado = calcular_estado_academico_curso(curso, estudiante)
                    nota_final = estado.get('nota_final_ponderada')
                    ihs = curso.materia.intensidad_horaria_semanal
                    if nota_final is not None and ihs > 0:
                        total_puntos_ponderados += nota_final * ihs
                        total_ihs += ihs
                promedio_general = total_puntos_ponderados / total_ihs if total_ihs > 0 else None
                if promedio_general is not None:
                    reporte_data.append({'estudiante': estudiante, 'promedio': promedio_general})

            reporte_data = sorted(reporte_data, key=lambda x: x['promedio'], reverse=True)
        else:
            # Si el grado es CUALITATIVO, activamos nuestra bandera
            reporte_no_aplica = True

    context = {
        'titulo_pagina': "Cuadro de Honor por Grado",
        'grados': grados,
        'periodos': periodos,
        'grado_seleccionado': grado_seleccionado,
        'periodo_seleccionado': periodo_seleccionado,
        'reporte_data': reporte_data,
        'reporte_no_aplica': reporte_no_aplica, # Pasamos la bandera a la plantilla
        'chart_labels': json.dumps([item['estudiante'].usuario.get_full_name() for item in reporte_data]),
        'chart_data': json.dumps([float(item['promedio']) for item in reporte_data]),
    }
    return render(request, 'gestion_academica/reportes/cuadro_honor_grado.html', context)        


@login_required
def reporte_estadistica_asistencia_diaria(request):
    """
    Muestra un resumen estadístico de la asistencia (presentes, ausentes, etc.)
    para una fecha específica, con un gráfico de pastel.
    """
    # Lógica de filtros
    fecha_str = request.GET.get('fecha', timezone.localdate().strftime('%Y-%m-%d'))
    try:
        fecha_seleccionada = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        fecha_seleccionada = timezone.localdate()

    institucion = request.user.institucion_asociada
    reporte_data = {}
    
    if institucion:
        # 1. Obtenemos el total de estudiantes activos
        total_estudiantes = Estudiante.objects.filter(institucion=institucion, activo=True).count()

        # 2. Contamos los registros de asistencia para la fecha seleccionada
        conteo_estados = RegistroAsistencia.objects.filter(
            fecha__date=fecha_seleccionada,
            institucion=institucion
        ).values('estado').annotate(total=Count('id'))
        
        # 3. Procesamos los conteos en un diccionario limpio
        resumen = {
            'Presentes': 0,
            'Ausentes': 0,
            'Tardanzas': 0,
            'Justificados': 0
        }
        for item in conteo_estados:
            # Mapeamos los valores del modelo a nombres más amigables
            if item['estado'] == 'PRESENTE': resumen['Presentes'] = item['total']
            elif item['estado'] == 'AUSENTE': resumen['Ausentes'] = item['total']
            elif item['estado'] == 'TARDANZA': resumen['Tardanzas'] = item['total']
            elif item['estado'] == 'JUSTIFICADO': resumen['Justificados'] = item['total']
        
        # 4. Calculamos los estudiantes sin registro
        total_registrados = sum(resumen.values())
        resumen['Sin Registro'] = total_estudiantes - total_registrados
        
        reporte_data = {
            'total_estudiantes': total_estudiantes,
            'resumen': resumen,
            'chart_labels': json.dumps(list(resumen.keys())),
            'chart_data': json.dumps(list(resumen.values())),
        }

    context = {
        'titulo_pagina': "Estadística de Asistencia Diaria",
        'fecha_seleccionada': fecha_seleccionada,
        'reporte_data': reporte_data,
    }
    return render(request, 'gestion_academica/reportes/reporte_asistencia_diaria.html', context)


@login_required
@permission_required('gestion_academica.view_registroasistencia') # Permiso adecuado
def reporte_asistencia_materia(request):
    """
    Muestra un reporte detallado de asistencia por materia, listando a cada
    estudiante y su conteo de presentes, ausentes y tardanzas.
    """
    institucion = request.user.institucion_asociada
    
    # Filtramos por la institución del usuario para seguridad
    grados = Grado.objects.filter(institucion=institucion).order_by('orden')
    periodos = PeriodoAcademico.objects.filter(institucion=institucion).order_by('-año_escolar', '-fecha_inicio')
    materias_del_grado = Materia.objects.none()

    grado_id = request.GET.get('grado')
    periodo_id = request.GET.get('periodo')
    materia_id = request.GET.get('materia')

    reporte_data = {}
    curso_seleccionado = None

    if grado_id:
        materias_del_grado = Materia.objects.filter(
            cursos__grado_id=grado_id, 
            cursos__institucion=institucion
        ).distinct().order_by('nombre_materia')

    if grado_id and periodo_id and materia_id:
        curso_seleccionado = get_object_or_404(
            Curso.objects.select_related('grado', 'periodo_academico', 'materia'),
            grado_id=grado_id, 
            periodo_academico_id=periodo_id, 
            materia_id=materia_id,
            institucion=institucion
        )
        
        # Obtenemos los estudiantes y anotamos sus conteos de asistencia para este curso
        estudiantes_con_asistencia = Estudiante.objects.filter(
            grado_actual=curso_seleccionado.grado, 
            activo=True,
            institucion=institucion
        ).annotate(
            total_presente=Count('asistencias', filter=Q(asistencias__curso=curso_seleccionado, asistencias__estado='PRESENTE')),
            total_ausente=Count('asistencias', filter=Q(asistencias__curso=curso_seleccionado, asistencias__estado='AUSENTE')),
            total_tardanza=Count('asistencias', filter=Q(asistencias__curso=curso_seleccionado, asistencias__estado='TARDANZA')),
            total_justificado=Count('asistencias', filter=Q(asistencias__curso=curso_seleccionado, asistencias__estado='JUSTIFICADO')),
        ).select_related('usuario').order_by('usuario__last_name')

        # Preparamos los datos para el gráfico
        total_general_presentes = sum(e.total_presente for e in estudiantes_con_asistencia)
        total_general_ausentes = sum(e.total_ausente for e in estudiantes_con_asistencia)
        total_general_tardanzas = sum(e.total_tardanza for e in estudiantes_con_asistencia)
        total_general_justificados = sum(e.total_justificado for e in estudiantes_con_asistencia)

        reporte_data = {
            'estudiantes_data': estudiantes_con_asistencia,
            'chart_labels': json.dumps(['Presentes', 'Ausentes', 'Tardanzas', 'Justificados']),
            'chart_data': json.dumps([total_general_presentes, total_general_ausentes, total_general_tardanzas, total_general_justificados])
        }

    context = {
        'titulo_pagina': "Reporte de Asistencia por Materia",
        'grados': grados, 'periodos': periodos, 'materias_del_grado': materias_del_grado,
        'curso_seleccionado': curso_seleccionado,
        'reporte_data': reporte_data
    }
    return render(request, 'gestion_academica/reportes/reporte_asistencia_materia.html', context)


@login_required
def reporte_incidencias_estudiante(request):
    """
    Muestra un historial detallado de todas las anotaciones en el observador
    para un estudiante específico, con un gráfico resumen.
    """
    grados = Grado.objects.all().order_by('orden', 'nombre')
    estudiantes_del_grado = Estudiante.objects.none()

    grado_id = request.GET.get('grado')
    estudiante_id = request.GET.get('estudiante')

    reporte_data = {}
    estudiante_seleccionado = None

    if grado_id:
        estudiantes_del_grado = Estudiante.objects.filter(grado_actual__id=grado_id).select_related('usuario').order_by('usuario__last_name')

    if estudiante_id:
        estudiante_seleccionado = get_object_or_404(Estudiante, pk=estudiante_id)
        
        # Obtenemos todas las anotaciones del estudiante
        anotaciones = AnotacionObservador.objects.filter(
            estudiante=estudiante_seleccionado
        ).select_related('registrado_por').order_by('-fecha_hora')

        # Preparamos los datos para el gráfico, contando por tipo de anotación
        conteo_por_tipo = defaultdict(int)
        for an in anotaciones:
            conteo_por_tipo[an.get_tipo_display()] += 1
        
        reporte_data = {
            'anotaciones': anotaciones,
            'chart_labels': json.dumps(list(conteo_por_tipo.keys())),
            'chart_data': json.dumps(list(conteo_por_tipo.values()))
        }

    context = {
        'titulo_pagina': "Reporte de Incidencias y Observador",
        'grados': grados,
        'estudiantes_del_grado': estudiantes_del_grado,
        'grado_seleccionado_id': grado_id,
        'estudiante_seleccionado_id': estudiante_id,
        'estudiante_seleccionado': estudiante_seleccionado,
        'reporte_data': reporte_data
    }
    return render(request, 'gestion_academica/reportes/reporte_incidencias.html', context)

@login_required
def reporte_consolidado_convivencia(request):
    """
    Muestra un consolidado de todas las anotaciones de convivencia (Halu Sentinel)
    clasificadas por la IA para toda la institución o un grado específico.
    """
    grados = Grado.objects.all().order_by('orden', 'nombre')
    periodos = PeriodoAcademico.objects.all().order_by('-año_escolar', '-fecha_inicio')

    grado_id = request.GET.get('grado')
    periodo_id = request.GET.get('periodo')

    reporte_data = {}
    grado_seleccionado = None
    periodo_seleccionado = None

    # El coordinador puede ver el consolidado sin necesidad de filtrar
    institucion = request.user.institucion_asociada
    
    # 1. Obtenemos todas las anotaciones que han sido clasificadas por la IA
    anotaciones_qs = AnotacionObservador.objects.filter(
        institucion=institucion
    ).exclude(
        Q(tipo_situacion_ia='NINGUNO') | Q(tipo_situacion_ia__isnull=True)
    ).select_related('estudiante__usuario', 'estudiante__grado_actual')

    # 2. Aplicamos los filtros si existen
    if grado_id:
        grado_seleccionado = get_object_or_404(Grado, pk=grado_id)
        anotaciones_qs = anotaciones_qs.filter(estudiante__grado_actual=grado_seleccionado)
    if periodo_id:
        periodo_seleccionado = get_object_or_404(PeriodoAcademico, pk=periodo_id)
        anotaciones_qs = anotaciones_qs.filter(fecha_hora__range=(periodo_seleccionado.fecha_inicio, periodo_seleccionado.fecha_fin))

    # 3. Agrupamos las anotaciones por estudiante
    casos_por_estudiante = defaultdict(list)
    for anotacion in anotaciones_qs:
        casos_por_estudiante[anotacion.estudiante].append(anotacion)

    # 4. Preparamos datos para el gráfico (conteo por tipo de situación)
    conteo_por_tipo = anotaciones_qs.values('tipo_situacion_ia').annotate(
        total=Count('id')
    ).order_by('tipo_situacion_ia')

    reporte_data = {
        'casos_por_estudiante': sorted(casos_por_estudiante.items(), key=lambda item: item[0].usuario.last_name),
        'chart_labels': json.dumps([item['tipo_situacion_ia'] for item in conteo_por_tipo]),
        'chart_data': json.dumps([item['total'] for item in conteo_por_tipo])
    }

    context = {
        'titulo_pagina': "Consolidado de Convivencia Escolar (Halu Sentinel)",
        'grados': grados,
        'periodos': periodos,
        'grado_seleccionado': grado_seleccionado,
        'periodo_seleccionado': periodo_seleccionado,
        'reporte_data': reporte_data,
    }
    return render(request, 'gestion_academica/reportes/reporte_consolidado_convivencia.html', context)   

