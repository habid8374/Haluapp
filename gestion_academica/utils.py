# gestion_academica/utils.py
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from xhtml2pdf import pisa
from django.template.loader import get_template
from django.db.models import Q
from io import BytesIO
from django.core.files.base import ContentFile
from django.contrib.sites.models import Site
from django.db.models import Avg, Count
import logging
from django.urls import reverse
from django.template.loader import render_to_string
from collections import defaultdict
from .models import (
    Calificacion, ActividadCalificable, TipoActividad, 
    EscalaValorativa, RegistroAsistenciaDocente, Docente, 
    PeriodoAcademico, Estudiante, Grado, Materia, Curso,
    AnotacionObservador, RegistroAsistencia, LeccionDiaria, BloqueHorario, 
    PlaneacionClase
)

from finanzas.models import CuentaPorCobrarEstudiante


logger = logging.getLogger(__name__)

def calcular_estado_academico_curso(curso, estudiante):
    """
    Función centralizada para calcular el estado académico de un estudiante en un curso.
    """
    actividades_del_curso = ActividadCalificable.objects.filter(curso=curso).select_related('tipo_actividad')
    calificaciones_del_estudiante = Calificacion.objects.filter(
        estudiante=estudiante,
        actividad_calificable__in=actividades_del_curso,
        valor_numerico__isnull=False
    )
    
    calificaciones_map = {cal.actividad_calificable_id: cal.valor_numerico for cal in calificaciones_del_estudiante}

    actividades_por_categoria = defaultdict(list)
    for actividad in actividades_del_curso:
        if actividad.tipo_actividad and actividad.tipo_actividad.porcentaje is not None:
            actividades_por_categoria[actividad.tipo_actividad].append(actividad)

    puntos_acumulados = Decimal('0.0')
    porcentaje_total_evaluado = Decimal('0.0')

    for categoria, actividades_en_categoria in actividades_por_categoria.items():
        notas_de_la_categoria = [calificaciones_map[act.id] for act in actividades_en_categoria if act.id in calificaciones_map]
        
        if notas_de_la_categoria:
            promedio_categoria = sum(notas_de_la_categoria) / len(notas_de_la_categoria)
            porcentaje_categoria = categoria.porcentaje
            
            puntos_acumulados += promedio_categoria * (porcentaje_categoria / Decimal('100.0'))
            porcentaje_total_evaluado += porcentaje_categoria

    nota_final = puntos_acumulados
    nota_actual = (puntos_acumulados / (porcentaje_total_evaluado / 100)) if porcentaje_total_evaluado > 0 else Decimal('0.0')

    return {
        'nota_final_ponderada': nota_final if nota_final > 0 else None,
        'nota_actual_promediada': nota_actual if nota_actual > 0 else None,
        'porcentaje_evaluado': porcentaje_total_evaluado,
    }

def analizar_riesgo_academico_curso(curso, estudiante):
    """
    Analiza el estado de un estudiante en un curso y determina si está en riesgo.
    Versión corregida para manejar correctamente los estados de Aprobado/Reprobado.
    """
    estado_academico = calcular_estado_academico_curso(curso, estudiante)
    puntos_acumulados = estado_academico.get('nota_final_ponderada') or Decimal('0.0')
    porcentaje_evaluado = estado_academico.get('porcentaje_evaluado') or Decimal('0.0')
    
    # Obtenemos la nota mínima para aprobar de la institución (ver Paso 2)
    NOTA_OBJETIVO = getattr(curso.institucion, 'nota_minima_aprobacion', Decimal('3.0'))
    
    porcentaje_restante = Decimal('100.0') - porcentaje_evaluado
    resultado = {'estado': 'OK', 'nota_requerida': None}

    # --- INICIO DE LA CORRECCIÓN LÓGICA ---
    if porcentaje_restante <= Decimal('0.01'): # Si el curso ya está 100% evaluado
        if puntos_acumulados >= NOTA_OBJETIVO:
            resultado['estado'] = "Aprobado"
        else:
            resultado['estado'] = "Reprobado"
    else: # Si el curso aún no ha terminado
        puntos_necesarios_para_aprobar = NOTA_OBJETIVO - puntos_acumulados
        if puntos_necesarios_para_aprobar > 0:
            nota_requerida = (puntos_necesarios_para_aprobar * Decimal('100.0')) / porcentaje_restante
            resultado['nota_requerida'] = nota_requerida
            
            if nota_requerida > 5.0:
                resultado['estado'] = "Situación Crítica"
            elif nota_requerida >= NOTA_OBJETIVO:
                resultado['estado'] = "En Riesgo"
    # --- FIN DE LA CORRECCIÓN LÓGICA ---
    
    return resultado


def obtener_desempeno(nota, institucion):
    """
    Busca en la base de datos la abreviatura del desempeño que corresponde
    a una nota específica para una institución dada, usando el modelo EscalaValorativa.
    """
    if nota is None or institucion is None:
        return ""
    
    # Aseguramos que la nota sea un objeto Decimal para una comparación precisa
    nota_decimal = Decimal(str(nota)).quantize(Decimal('0.01'))
    
    # Buscamos en la tabla de EscalaValorativa el rango que contenga la nota
    escala = EscalaValorativa.objects.filter(
        institucion=institucion,
        nota_minima__lte=nota_decimal, # lte = Less Than or Equal (menor o igual que)
        nota_maxima__gte=nota_decimal  # gte = Greater Than or Equal (mayor o igual que)
    ).first()

    # Si encontramos una escala que coincide, devolvemos su abreviatura. Si no, un guion.
    return escala.abreviatura if escala else "-"


def registrar_inasistencias_docentes(institucion, fecha=None):
    """
    Recorre todos los docentes de la institución y crea registros AUSENTE si no marcaron.
    """
    if fecha is None:
        fecha = timezone.localdate()

    docentes = Docente.objects.filter(institucion=institucion)
    registrados = RegistroAsistenciaDocente.objects.filter(institucion=institucion, fecha__date=fecha).values_list('docente_id', flat=True)

    inasistentes = docentes.exclude(pk__in=registrados)

    for docente in inasistentes:
        RegistroAsistenciaDocente.objects.create(
            docente=docente,
            estado='AUSENTE',
            fecha=timezone.now(),
            institucion=institucion,
            registrado_por=None  # No hay quien lo haya marcado
        ) 

def generar_boletin_pdf_en_memoria(estudiante, año_academico):
    """
    Genera el PDF de un boletín para un estudiante y año específicos 
    y lo devuelve como un objeto en memoria, sin guardarlo en disco.
    """
    
    # 1. Busca las calificaciones (AJUSTA ESTA CONSULTA A TU MODELO)
    # Asume que tienes un modelo PeriodoAcademico con un campo 'año'
    periodo_final = PeriodoAcademico.objects.filter(año=año_academico).order_by('-fecha_fin').first()
    
    calificaciones = Calificacion.objects.filter(
        estudiante=estudiante,
        periodo=periodo_final
    ).select_related('asignatura')

    # 2. Prepara el contexto para la plantilla de tu boletín
    context = {
        'estudiante': estudiante,
        'institucion': estudiante.institucion,
        'calificaciones': calificaciones,
        'periodo': periodo_final,
        'año_academico': año_academico,
    }

    # 3. Renderiza tu plantilla de boletín existente
    # ¡IMPORTANTE! Usa la ruta de tu plantilla de boletín actual.
    template = get_template('gestion_academica/pdfs/boletin_actual.html') 
    html = template.render(context)

    # 4. Crea el PDF en un buffer de memoria
    buffer = BytesIO()
    pisa_status = pisa.CreatePDF(html, dest=buffer)
    if pisa_status.err:
        raise Exception(f'Error al generar el PDF del boletín para {estudiante.pk}')
    
    buffer.seek(0)
    
    # 5. Devuelve el buffer con el PDF
    return buffer           

def enviar_correo_documento_listo(solicitud):
    """
    Notifica al egresado que su documento solicitado ya está listo para descargar.
    """
    egresado = solicitud.egresado
    institucion = egresado.estudiante.institucion
    
    # Construye la URL al portal del egresado
    domain = Site.objects.get_current().domain
    protocol = 'https' # Asumimos https para producción
    portal_url = f"{protocol}://{domain}{reverse('gestion_academica:portal_egresado')}"
    
    asunto = f"Tu documento '{solicitud.tipo_documento_solicitado}' está listo"
    context = {
        'solicitud': solicitud,
        'egresado': egresado,
        'portal_url': portal_url,
    }
    
    # IMPORTANTE: Debes crear esta plantilla de correo
    html_content = render_to_string('gestion_academica/emails/documento_listo.html', context)
    
    # Lógica para encontrar el email (puedes reutilizar la de la vista de eliminar pago)
    email_destinatario = egresado.estudiante.usuario.email

    if not email_destinatario:
        logger.warning(f"No se pudo notificar a {egresado} sobre documento listo (sin email).")
        return False

    # Reutilizamos la función de envío de correo de la app 'admisiones'
    from admisiones.utils import enviar_correo_dinamico
    return enviar_correo_dinamico(
        institucion=institucion,
        asunto=asunto,
        destinatarios=[email_destinatario],
        html_content=html_content
    )

# --- HERRAMIENTAS PARA LA IA (VERSIÓN MULTI-INSTITUCIÓN DEFINITIVA) ---

def calcular_estado_academico_curso(curso, estudiante):
    """
    Función de ayuda centralizada para calcular la nota final ponderada de un
    estudiante en un curso. Esta función es utilizada por múltiples herramientas y reportes.
    """
    if not curso or not estudiante:
        return {}

    calificaciones = Calificacion.objects.filter(
        estudiante=estudiante,
        actividad_calificable__curso=curso,
        valor_numerico__isnull=False
    ).select_related('actividad_calificable__tipo_actividad')

    calificaciones_map = {cal.actividad_calificable_id: cal.valor_numerico for cal in calificaciones}
    
    nota_final_ponderada = Decimal('0.0')
    porcentaje_evaluado = Decimal('0.0')

    # Agrupamos por categoría para respetar los porcentajes
    actividades_por_categoria = defaultdict(list)
    for actividad in curso.actividades_calificables.select_related('tipo_actividad'):
        if actividad.tipo_actividad and actividad.tipo_actividad.porcentaje is not None:
            actividades_por_categoria[actividad.tipo_actividad].append(actividad)
    
    for categoria, actividades_en_categoria in actividades_por_categoria.items():
        notas_de_la_categoria = [
            calificaciones_map.get(act.id) for act in actividades_en_categoria if calificaciones_map.get(act.id) is not None
        ]
        
        if notas_de_la_categoria:
            promedio_categoria = sum(notas_de_la_categoria) / len(notas_de_la_categoria)
            porcentaje_categoria = categoria.porcentaje
            nota_final_ponderada += promedio_categoria * (porcentaje_categoria / Decimal('100.0'))
            porcentaje_evaluado += porcentaje_categoria
            
    return {
        'nota_final_ponderada': nota_final_ponderada if porcentaje_evaluado > 0 else None,
        'porcentaje_evaluado': porcentaje_evaluado,
    }

def obtener_promedio_materia_por_grado(materia_nombre: str, periodo_nombre: str, institucion_id: int) -> str:
    """Obtiene el rendimiento promedio de una materia en todos los grados de la institución."""
    try:
        periodo = PeriodoAcademico.objects.get(nombre__icontains=periodo_nombre, institucion_id=institucion_id, activo=True)
        materia = Materia.objects.get(nombre_materia__icontains=materia_nombre, institucion_id=institucion_id)
        
        cursos = Curso.objects.filter(materia=materia, periodo_academico=periodo).select_related('grado')
        if not cursos:
            return f"No se encontraron cursos para la materia '{materia_nombre}' en el periodo '{periodo_nombre}'."

        resultados = []
        for curso in cursos:
            promedio = Calificacion.objects.filter(
                actividad_calificable__curso=curso
            ).aggregate(avg=Avg('valor_numerico'))['avg']
            if promedio:
                resultados.append(f"- {curso.grado.nombre}: Promedio de {promedio:.2f}")

        return f"Rendimiento de '{materia_nombre}' en el {periodo.nombre}:\n" + "\n".join(resultados) if resultados else "No se encontraron calificaciones para esta materia."
    except (PeriodoAcademico.DoesNotExist, Materia.DoesNotExist):
        return "No pude encontrar la materia o el periodo especificado. Por favor, sé más específico."
    except Exception as e:
        return f"Ocurrió un error: {str(e)}"

def obtener_conteo_estudiantes_por_grado(institucion_id: int) -> str:
    """Obtiene el número total de estudiantes activos en cada grado de la institución."""
    conteo = Grado.objects.filter(institucion_id=institucion_id).annotate(
        num_estudiantes=Count('estudiantes_actuales', filter=Q(estudiantes_actuales__activo=True))
    ).order_by('orden')
    
    resultados = [f"- {grado.nombre}: {grado.num_estudiantes} estudiantes" for grado in conteo]
    return "Conteo de estudiantes por grado:\n" + "\n".join(resultados)

def get_absent_students_by_grade(nombre_grado: str, institucion_id: int) -> str:
    """Obtiene una lista de los estudiantes ausentes hoy en un grado específico."""
    try:
        hoy = timezone.localdate()
        grado = Grado.objects.get(nombre__iexact=nombre_grado, institucion_id=institucion_id)
        
        estudiantes_ausentes_ids = RegistroAsistencia.objects.filter(
            fecha__date=hoy,
            estudiante__grado_actual=grado,
            estado='AUSENTE'
        ).values_list('estudiante_id', flat=True)

        if not estudiantes_ausentes_ids:
            return f"No se registraron ausencias en {nombre_grado} el día de hoy."

        estudiantes_ausentes = Estudiante.objects.filter(pk__in=estudiantes_ausentes_ids).select_related('usuario')
        lista_nombres = [f"- {est.usuario.get_full_name()}" for est in estudiantes_ausentes]
        
        return f"Estudiantes ausentes en {nombre_grado} hoy:\n" + "\n".join(lista_nombres)
    except Grado.DoesNotExist:
        return f"No pude encontrar el grado '{nombre_grado}'. Intenta con el nombre exacto."
    except Exception as e:
        return f"Ocurrió un error al consultar la asistencia: {str(e)}"

def obtener_resumen_financiero_estudiantes(institucion_id: int) -> str:
    """
    Calcula un resumen del estado de cartera: en mora, pendientes y al día,
    contando estudiantes únicos.
    """
    try:
        # ▼▼▼ CORRECCIÓN CLAVE AQUÍ ▼▼▼
        # 1. Obtenemos una lista de los IDs de estudiantes únicos que tienen al menos UNA cuenta vencida.
        estudiantes_en_mora_ids = CuentaPorCobrarEstudiante.objects.filter(
            institucion_id=institucion_id, estado='VENCIDO'
        ).values_list('estudiante_id', flat=True).distinct()
        
        # El conteo es la longitud de esa lista de IDs únicos.
        conteo_en_mora = len(estudiantes_en_mora_ids)

        # 2. Contamos estudiantes únicos con cuentas pendientes, EXCLUYENDO a los que ya están en mora.
        conteo_pendientes = CuentaPorCobrarEstudiante.objects.filter(
            institucion_id=institucion_id, estado__in=['PENDIENTE', 'PAGADO_PARCIAL']
        ).exclude(
            estudiante_id__in=estudiantes_en_mora_ids
        ).values_list('estudiante_id', flat=True).distinct().count()
        
        # 3. Calculamos los que están "Al día"
        total_estudiantes_activos = Estudiante.objects.filter(
            institucion_id=institucion_id, activo=True
        ).count()
        
        conteo_al_dia = total_estudiantes_activos - conteo_en_mora - conteo_pendientes
        
        # 4. Formateamos la respuesta para la IA
        respuesta = (
            "Aquí tienes un resumen del estado de cartera de la institución:\n"
            f"- Estudiantes en Mora (con deudas vencidas): {conteo_en_mora}\n"
            f"- Estudiantes con Pagos Pendientes (no vencidos): {conteo_pendientes}\n"
            f"- Estudiantes completamente al Día: {conteo_al_dia}"
        )
        return respuesta
        # ▲▲▲ FIN DE LA CORRECCIÓN ▲▲▲
    except Exception as e:
        return f"Ocurrió un error al consultar las finanzas: {str(e)}"

def get_top_student_in_school(periodo_nombre: str, institucion_id: int) -> str:
    """Encuentra al estudiante con el mejor promedio de la institución en un periodo."""
    try:
        periodo = PeriodoAcademico.objects.get(nombre__icontains=periodo_nombre, institucion_id=institucion_id)
        estudiantes = Estudiante.objects.filter(institucion_id=institucion_id, activo=True, grado_actual__tipo_evaluacion='CUANTITATIVO')
        
        ranking_data = []
        for estudiante in estudiantes:
            cursos = Curso.objects.filter(grado=estudiante.grado_actual, periodo_academico=periodo)
            total_puntos = Decimal('0.0')
            total_ihs = 0
            for curso in cursos:
                estado = calcular_estado_academico_curso(curso, estudiante)
                nota = estado.get('nota_final_ponderada')
                if nota is not None and curso.materia.intensidad_horaria_semanal > 0:
                    total_puntos += nota * curso.materia.intensidad_horaria_semanal
                    total_ihs += curso.materia.intensidad_horaria_semanal
            
            promedio = total_puntos / total_ihs if total_ihs > 0 else None
            if promedio is not None:
                ranking_data.append({'estudiante': estudiante, 'promedio': promedio})

        if not ranking_data:
            return "No se encontraron datos suficientes para calcular el ranking."

        mejor_estudiante_info = max(ranking_data, key=lambda x: x['promedio'])
        estudiante = mejor_estudiante_info['estudiante']
        promedio = mejor_estudiante_info['promedio']

        return (f"El mejor estudiante de la institución en el {periodo.nombre} es "
                f"{estudiante.usuario.get_full_name()} del grado {estudiante.grado_actual.nombre}, "
                f"con un promedio de {promedio:.2f}.")
    except PeriodoAcademico.DoesNotExist:
        return "No pude encontrar ese periodo. Por favor, sé más específico."
    except Exception as e:
        return f"Ocurrió un error al calcular el ranking: {str(e)}"

def get_observation_count_for_student(nombre_estudiante: str, institucion_id: int) -> str:
    """Cuenta las anotaciones en el observador para un estudiante específico."""
    try:
        nombres = nombre_estudiante.split()
        query = Q(institucion_id=institucion_id)
        if len(nombres) > 1:
            query &= Q(usuario__first_name__icontains=nombres[0]) & Q(usuario__last_name__icontains=nombres[-1])
        else:
            query &= Q(usuario__first_name__icontains=nombre_estudiante) | Q(usuario__last_name__icontains=nombre_estudiante)

        estudiante = Estudiante.objects.filter(query).first()
        if not estudiante:
            return f"No pude encontrar a un estudiante llamado '{nombre_estudiante}' en tu institución."
        
        conteo = AnotacionObservador.objects.filter(estudiante=estudiante).count()
        return f"El estudiante {estudiante.usuario.get_full_name()} tiene {conteo} anotaciones en el observador."
    except Exception as e:
        return f"Ocurrió un error al buscar al estudiante: {str(e)}"
    

def crear_lecciones_diarias_desde_planeacion(planeacion_id):
    """
    Toma una planeación completada y crea los registros de LeccionDiaria
    correspondientes, usando los nombres de campo correctos del modelo.
    VERSIÓN DEFINITIVA Y CORREGIDA.
    """
    try:
        planeacion = PlaneacionClase.objects.get(pk=planeacion_id)
        curso = planeacion.curso
        detalles_clase = list(planeacion.detalles_clase.all().order_by('numero_clase'))
        
        dias_de_clase = list(BloqueHorario.objects.filter(curso=curso).values_list('dia_semana', flat=True).distinct())
        if not dias_de_clase:
            return 0, "Error: El curso no tiene un horario definido. No se pueden crear las lecciones."

        lecciones_creadas = 0
        fecha_actual = timezone.now().date()
        
        while lecciones_creadas < len(detalles_clase):
            if fecha_actual.weekday() in dias_de_clase:
                
                if not LeccionDiaria.objects.filter(curso=curso, fecha=fecha_actual).exists():
                    detalle_actual = detalles_clase[lecciones_creadas]
                    
                    # --- INICIO DE LA CORRECCIÓN CLAVE ---
                    # Usamos los nombres de campo correctos de tu modelo LeccionDiaria
                    LeccionDiaria.objects.create(
                        curso=curso,
                        fecha=fecha_actual,
                        tema_tratado=detalle_actual.tema_clase,
                        resumen_clase=f"INICIO:\n{detalle_actual.actividades_inicio}\n\nDESARROLLO:\n{detalle_actual.actividades_desarrollo}\n\nCIERRE:\n{detalle_actual.actividades_cierre}",
                        creado_por=planeacion.docente.usuario, # Usamos el usuario del docente
                        institucion=planeacion.institucion
                    )
                    # --- FIN DE LA CORRECCIÓN CLAVE ---
                    lecciones_creadas += 1
            
            fecha_actual += timedelta(days=1)

        return lecciones_creadas, f"Se crearon exitosamente {lecciones_creadas} lecciones diarias."

    except PlaneacionClase.DoesNotExist:
        return 0, "Error: La planeación especificada no existe."
    except Exception as e:
        logger.error(f"Error al crear lecciones desde la planeación {planeacion_id}: {e}", exc_info=True)
        return 0, f"Error inesperado: {e}"