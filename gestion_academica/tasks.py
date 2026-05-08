# gestion_academica/tasks.py

from celery import shared_task
from .models import PeriodoAcademico, Estudiante, Curso, Calificacion
from .utils import calcular_estado_academico_curso
from django.utils import timezone
from decimal import Decimal
import json
from .models import PlaneacionClase, DetalleClase
import google.generativeai as genai
from django.conf import settings
from django.db import transaction
from django.urls import reverse
from allauth.socialaccount.models import SocialToken
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from celery.exceptions import SoftTimeLimitExceeded
from django.contrib.auth import get_user_model
from datetime import time, timedelta, date
import traceback
import re
import docx
import PyPDF2
import io

import logging

from .models import ( 
    Usuario, BloqueHorario, 
    PeriodoAcademico, Candidato, 
    AnotacionObservador, 
    AnalisisComportamientoIA, 
    Notificacion, PeriodoAcademico, 
    Docente, Curso, Aula, Grado, EntregaDeber
)

logger = logging.getLogger(__name__)

@shared_task
def generar_ranking_institucional_task(periodo_id):
    """
    Tarea de Celery que calcula el ranking general de la institución
    y devuelve los resultados en formato JSON.
    """
    periodo = PeriodoAcademico.objects.get(pk=periodo_id)
    institucion = periodo.institucion
    estudiantes = Estudiante.objects.filter(
        institucion=institucion, activo=True, grado_actual__tipo_evaluacion='CUANTITATIVO'
    )

    ranking_data = []
    for estudiante in estudiantes:
        # (Aquí va la misma lógica de cálculo de promedio que ya conoces)
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
            ranking_data.append({
                'nombre_estudiante': estudiante.usuario.get_full_name(),
                'nombre_grado': estudiante.grado_actual.nombre,
                'promedio': float(promedio)
            })
            
    # Ordenamos los resultados
    reporte_final = sorted(ranking_data, key=lambda x: x['promedio'], reverse=True)
    
    # Devolvemos el resultado como un JSON
    return json.dumps(reporte_final)

@shared_task(bind=True, max_retries=3, default_retry_delay=180)
def sincronizar_horario_google_calendar_task(self, user_id):
    """
    Sincroniza el horario de clases de un usuario (estudiante o docente)
    con su Google Calendar principal.
    """
    try:
        user = Usuario.objects.get(pk=user_id)
        if not user.google_calendar_id:
            logger.warning(f"Usuario {user_id} no tiene un ID de calendario de Google. Abortando sincronización.")
            return "Usuario sin calendario configurado."

        social_token = SocialToken.objects.get(account__user=user, account__provider='google')
        
        credentials = Credentials(
            token=social_token.token,
            refresh_token=social_token.token_secret,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=social_token.app.client_id,
            client_secret=social_token.app.secret
        )
        
        service = build('calendar', 'v3', credentials=credentials)
        
        # Buscamos el periodo académico activo para definir las fechas de los eventos
        periodo_activo = PeriodoAcademico.objects.filter(institucion=user.institucion_asociada, activo=True).first()
        if not periodo_activo:
            logger.error(f"No hay un periodo académico activo para la institución del usuario {user_id}.")
            return "Sin periodo activo."

        # Buscamos todos los bloques de horario del usuario
        bloques_horario = BloqueHorario.objects.none()
        if hasattr(user, 'estudiante'):
            bloques_horario = BloqueHorario.objects.filter(curso__grado=user.estudiante.grado_actual, curso__periodo_academico=periodo_activo)
        elif hasattr(user, 'docente'):
            bloques_horario = BloqueHorario.objects.filter(curso__docentes_asignados=user.docente, curso__periodo_academico=periodo_activo)

        for bloque in bloques_horario:
            # Si el evento ya fue creado, lo saltamos por ahora (en un futuro se podría actualizar)
            if bloque.google_event_id:
                continue

            # Creamos el evento en el calendario
            evento = {
                'summary': f"{bloque.curso.materia.nombre_materia} - {bloque.curso.grado.nombre}",
                'location': bloque.aula.nombre if bloque.aula else '',
                'description': f"Clase impartida por: {', '.join([d.usuario.get_full_name() for d in bloque.curso.docentes_asignados.all()])}",
                'start': {
                    'dateTime': f"{periodo_activo.fecha_inicio.strftime('%Y-%m-%d')}T{bloque.hora_inicio.strftime('%H:%M:%S')}",
                    'timeZone': 'America/Bogota',
                },
                'end': {
                    'dateTime': f"{periodo_activo.fecha_inicio.strftime('%Y-%m-%d')}T{bloque.hora_fin.strftime('%H:%M:%S')}",
                    'timeZone': 'America/Bogota',
                },
                'recurrence': [
                    f"RRULE:FREQ=WEEKLY;BYDAY={['MO','TU','WE','TH','FR','SA','SU'][bloque.dia_semana]};UNTIL={periodo_activo.fecha_fin.strftime('%Y%m%dT235959Z')}"
                ],
            }

            created_event = service.events().insert(calendarId=user.google_calendar_id, body=evento).execute()
            
            # Guardamos el ID del evento creado para futuras referencias
            bloque.google_event_id = created_event.get('id')
            bloque.save(update_fields=['google_event_id'])
            logger.info(f"Evento '{evento['summary']}' creado en el calendario del usuario {user_id}.")

        return f"Sincronización completada para el usuario {user_id}."

    except Exception as e:
        logger.error(f"Error en la sincronización de calendario para el usuario {user_id}: {e}", exc_info=True)
        raise self.retry(exc=e)   
    

@shared_task(bind=True, max_retries=3, default_retry_delay=180, soft_time_limit=150, time_limit=180)
def generar_contenido_planeacion_task(self, planeacion_id):
    """
    Tarea de Celery que genera el contenido de una planeación.
    VERSIÓN FINAL: Basada en tu código, con manejo de errores de JSON mejorado.
    """
    planeacion = None
    raw_text = "" # Inicializamos la variable para que esté disponible en el bloque except
    try:
        planeacion = PlaneacionClase.objects.get(pk=planeacion_id)

        

        api_key = getattr(settings, 'GOOGLE_API_KEY', None)
        if not api_key:
            raise Exception("GOOGLE_API_KEY no configurada.")

        genai.configure(api_key=api_key)
        generation_config = genai.types.GenerationConfig(response_mime_type="application/json")
        model = genai.GenerativeModel('gemini-2.5-flash', generation_config=generation_config)

        prompt = f"""
        Actúa como un experto pedagogo. Crea una planeación de clases detallada basada en la siguiente información.
        La respuesta debe ser únicamente un objeto JSON válido, sin markdown.

        Información base:
        - Título de la Unidad: "{planeacion.titulo}"
        - Curso: "{planeacion.curso.materia.nombre_materia}" para "{planeacion.curso.grado.nombre}"
        - Metodología: "{planeacion.get_metodologia_display()}"
        - Duración: {planeacion.duracion_clases} clase(s)

        Estructura JSON requerida:
        {{
          "objetivos_aprendizaje": "Un párrafo con los objetivos de la unidad.",
          "recursos_necesarios": "Una lista de recursos necesarios.",
          "criterios_evaluacion": "Un párrafo con los criterios de evaluación.",
          "clases": [
            {{
              "numero_clase": 1,
              "tema_clase": "Título específico para esta clase.",
              "actividades_inicio": "Actividades para empezar la clase.",
              "actividades_desarrollo": "Actividades principales de la clase.",
              "actividades_cierre": "Actividades para concluir la clase."
            }}
          ]
        }}

        Asegúrate de que la lista "clases" contenga exactamente {planeacion.duracion_clases} objetos.
        """

        response = model.generate_content(prompt)

        # Tu lógica de limpieza es excelente, la mantenemos
        raw_text = response.text.strip() if hasattr(response, "text") and response.text else ""

        if not raw_text:
            feedback = getattr(response, 'prompt_feedback', 'Sin contenido ni feedback. Posiblemente se superó la cuota de la API.')
            raise ValueError(f"La IA no generó contenido. Feedback: {feedback}")

        if raw_text.startswith("```json"):
            raw_text = raw_text.removeprefix("```json").strip()
        if raw_text.endswith("```"):
            raw_text = raw_text.removesuffix("```").strip()

        ai_data = json.loads(raw_text)

        with transaction.atomic():
            planeacion.objetivos_aprendizaje = ai_data.get('objetivos_aprendizaje')
            planeacion.recursos_necesarios = ai_data.get('recursos_necesarios')
            planeacion.criterios_evaluacion = ai_data.get('criterios_evaluacion')
            planeacion.estado_generacion = PlaneacionClase.EstadoGeneracion.COMPLETADO
            planeacion.save(update_fields=[
                'objetivos_aprendizaje',
                'recursos_necesarios',
                'criterios_evaluacion',
                'estado_generacion'
            ])

            planeacion.detalles_clase.all().delete()
            for detalle in ai_data.get('clases', []):
                DetalleClase.objects.create(
                    planeacion=planeacion,
                    numero_clase=detalle.get('numero_clase'),
                    tema_clase=detalle.get('tema_clase'),
                    actividades_inicio=detalle.get('actividades_inicio'),
                    actividades_desarrollo=detalle.get('actividades_desarrollo'),
                    actividades_cierre=detalle.get('actividades_cierre')
                )

        logger.info(f"Contenido de la planeación {planeacion.id} generado exitosamente.")
        return "Generación exitosa."

    # --- INICIO DE LA CORRECCIÓN CLAVE ---
    except json.JSONDecodeError as e:
        error_message = f"La IA devolvió un formato inválido. Error: {e}. Respuesta recibida: {raw_text[:500]}..."
        logger.error(error_message, exc_info=True)
        if planeacion:
            planeacion.estado_generacion = PlaneacionClase.EstadoGeneracion.FALLIDO
            planeacion.error_generacion = error_message
            planeacion.save(update_fields=['estado_generacion', 'error_generacion'])
        return "Error final: Formato JSON inválido." # No reintentamos
    # --- FIN DE LA CORRECCIÓN CLAVE ---

    except Exception as e:
        logger.error(f"Error en la tarea de planeación para ID {planeacion_id}: {e}", exc_info=True)
        if planeacion:
            planeacion.estado_generacion = PlaneacionClase.EstadoGeneracion.FALLIDO
            planeacion.error_generacion = f"Error: {type(e).__name__} - {e}"
            planeacion.save(update_fields=['estado_generacion', 'error_generacion'])

        if "quota" in str(e).lower():
            return f"Error final: {e}"

        raise self.retry(exc=e)

@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def analizar_propuesta_candidato_task(self, candidato_id):
    """
    Tarea de Celery que toma la propuesta de un candidato, la envía a la IA de Gemini
    para su análisis y guarda el resultado en la base de datos.
    """
    try:
        candidato = Candidato.objects.get(pk=candidato_id)
        
        api_key = getattr(settings, 'GOOGLE_API_KEY', None)
        if not api_key:
            raise Exception("GOOGLE_API_KEY no configurada.")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-pro')

        prompt = f"""
        Actúa como un asesor político estudiantil y analista de discursos.
        Tu tarea es analizar la siguiente propuesta de un candidato para una elección escolar.
        Sé objetivo, neutral y constructivo.

        Propuesta del candidato '{candidato.estudiante.usuario.get_full_name()}':
        ---
        {candidato.propuesta}
        ---

        Por favor, genera un análisis breve (máximo 3 párrafos) que cubra los siguientes puntos:
        1.  **Puntos Clave:** Identifica las 2 o 3 ideas más importantes de la propuesta.
        2.  **Viabilidad:** Evalúa de forma realista qué tan factibles son las propuestas en un entorno escolar.
        3.  **Impacto Potencial:** Describe el posible impacto positivo que tendrían estas propuestas en la comunidad estudiantil.

        La respuesta debe ser solo el texto del análisis, sin títulos ni formato adicional.
        """

        response = model.generate_content(prompt)
        
        if not response.parts:
            feedback = getattr(response, 'prompt_feedback', 'Razón desconocida.')
            raise Exception(f"La IA no generó contenido. Feedback: {feedback}")

        # Guardamos el análisis directamente en el modelo del candidato
        candidato.analisis_ia = response.text
        candidato.save(update_fields=['analisis_ia'])
        
        logger.info(f"Análisis de IA generado exitosamente para el candidato ID {candidato_id}.")
        return f"Análisis completado para el candidato {candidato_id}."

    except Exception as e:
        logger.error(f"Error en la tarea de análisis de propuesta para el candidato ID {candidato_id}: {e}", exc_info=True)
        raise self.retry(exc=e)        
    

@shared_task
def analizar_comportamiento_task(user_id):
    """
    Tarea de Celery que analiza el comportamiento y notifica al usuario al finalizar.
    Versión final y robusta.
    """
    print("Iniciando tarea de análisis de comportamiento...")
    User = get_user_model()
    try:
        usuario_solicitante = User.objects.get(pk=user_id)
        institucion = usuario_solicitante.institucion_asociada
    except (User.DoesNotExist, AttributeError):
        print(f"Error: No se encontró el usuario o la institución para el user_id {user_id}")
        return "Error: Usuario no válido."

    try:
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        generation_config = genai.types.GenerationConfig(response_mime_type="application/json")
        model = genai.GenerativeModel('gemini-2.5-flash', generation_config=generation_config)
    except Exception as e:
        print(f"Error CRÍTICO al configurar la API de Google: {e}")
        # Notificamos al usuario del error de configuración
        Notificacion.objects.create(
            destinatario=usuario_solicitante,
            mensaje=f"No se pudo completar el análisis. Error de configuración de la IA: {e}",
            institucion=institucion
        )
        return f"Error de configuración de API: {e}"

    fecha_limite = timezone.now() - timedelta(days=90)
    estudiantes_activos = Estudiante.objects.filter(activo=True, institucion=institucion)
    total_analizados = 0

    for estudiante in estudiantes_activos:
        anotaciones = AnotacionObservador.objects.filter(
            estudiante=estudiante,
            fecha_hora__gte=fecha_limite
        ).order_by('fecha_hora')

        if anotaciones.count() < 3: # Solo analizar si hay suficiente historial
            continue

        historial_texto = "\n".join(
            [f"- Fecha: {a.fecha_hora.strftime('%Y-%m-%d')}, Anotación: '{a.descripcion}'" for a in anotaciones]
        )

        prompt = f"""
        Actúa como un psicólogo educativo experto llamado HALU. A continuación, te presento un historial de anotaciones del observador para el estudiante {estudiante.usuario.get_full_name()}.
        
        Historial de los últimos 90 días:
        {historial_texto}

        Por favor, analiza este historial y realiza dos tareas:
        1. Escribe un resumen conciso (máximo 100 palabras) sobre el comportamiento general, tendencias o posibles patrones de riesgo que observes. Sé objetivo y profesional.
        2. Identifica y extrae hasta 3 patrones o temas clave del historial.

        Devuelve tu análisis en un formato JSON válido con las claves "resumen_ia" y "patrones_detectados" (una lista de strings).
        """

        try:
            response = model.generate_content(prompt)
            json_text = response.text.strip().replace("```json", "").replace("```", "")
            analisis_data = json.loads(json_text)

            AnalisisComportamientoIA.objects.update_or_create(
                estudiante=estudiante,
                institucion=institucion,
                defaults={
                    'resumen_ia': analisis_data.get("resumen_ia"),
                    'patrones_detectados': analisis_data.get("patrones_detectados"),
                    'fecha_analisis': timezone.now()
                }
            )
            total_analizados += 1
        except Exception as e:
            print(f"Error procesando al estudiante {estudiante.id}: {e}")

    mensaje_final = f"Análisis de comportamiento finalizado. Se procesaron los historiales de {total_analizados} estudiantes."
    print(mensaje_final)

    Notificacion.objects.create(
        destinatario=usuario_solicitante,
        mensaje=mensaje_final,
        enlace=reverse('gestion_academica:dashboard_bienestar'),
        institucion=institucion
    )

    return mensaje_final



@shared_task
def generar_propuesta_horario_task(periodo_pk, institucion_id, grado_pk): # <-- Nuevo parámetro
    """
    Genera una propuesta de horario para un GRADO específico.
    """
    try:
        # 1. Recopilamos datos, ahora filtrados por el grado
        periodo = PeriodoAcademico.objects.get(pk=periodo_pk)
        grado = Grado.objects.get(pk=grado_pk)
        
        # Filtramos los cursos por grado
        cursos = Curso.objects.filter(periodo_academico=periodo, grado_id=grado_pk)
        
        # Filtramos los docentes que enseñan en esos cursos
        docentes_ids = cursos.values_list('docentes_asignados', flat=True)
        docentes = Docente.objects.filter(pk__in=set(docentes_ids)).prefetch_related('disponibilidades', 'cursos_impartidos__materia')

        aulas = Aula.objects.filter(institucion_id=institucion_id)

        # 2. Formatear las restricciones para el prompt (ahora mucho más enfocado)
        docentes_texto = "\n".join([f"- {d.usuario.get_full_name()} (ID: {d.pk})." for d in docentes])
        cursos_texto = "\n".join([f"- Curso ID {c.pk}: '{c.materia.nombre_materia}'." for c in cursos])
        aulas_texto = "\n".join([f"- Aula ID {a.pk}: '{a.nombre}' (Cap: {a.capacidad})." for a in aulas])

        # 3. Construir el prompt, ahora específico para el grado
        prompt = f"""
        Actúa como un experto en logística educativa. Tu tarea es crear un horario escolar para el grado '{grado.nombre}'.
        
        RESTRICCIONES:
        1. DOCENTES DISPONIBLES PARA ESTE GRADO:
        {docentes_texto}

        2. CURSOS A PROGRAMAR PARA ESTE GRADO:
        {cursos_texto}

        3. AULAS DISPONIBLES:
        {aulas_texto}

         4. REGLAS:
        - Horario escolar de Lunes a Viernes.
        - Las clases pueden tener duraciones variables: 45 minutos, 60 minutos o 90 minutos.
        - Para grados de 'Preescolar', el horario es de 08:00 a 12:00.
        - Para otros grados, el horario es de 06:30 a 14:00.
        - Un docente no puede estar en dos lugares al mismo tiempo.
        - Un aula no puede ser usada por dos cursos al mismo tiempo.

        TAREA:
        Genera una propuesta de horario en formato JSON (una lista de eventos).
        Cada evento debe tener estas claves: "dia", "hora_inicio", "hora_fin", "curso_id", "docente_id", "aula_id".
        Calcula la "hora_fin" basándote en la "hora_inicio" y la duración que asignes a la clase.
        Usa el formato de fecha y hora completo ISO 8601 (ej: "2025-08-04T06:30:00").
        """

        genai.configure(api_key=settings.GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        
        json_text = response.text
        match = re.search(r'\[.*\]', json_text, re.DOTALL)
        if not match:
             match = re.search(r'\{.*\}', json_text, re.DOTALL)

        if not match:
            raise json.JSONDecodeError("No se encontró un bloque JSON válido en la respuesta de la IA.", json_text, 0)
        
        horario_propuesto = json.loads(match.group(0))
        
        return {'status': 'SUCCESS', 'horario': horario_propuesto}

    except Exception as e:
        traceback.print_exc()
        return {'status': 'FAILURE', 'error': str(e)}   


def extract_text_from_file(file_field):
    """
    Función auxiliar para extraer texto de archivos .docx y .pdf.
    """
    try:
        file_name = file_field.name.lower()
        if file_name.endswith('.docx'):
            document = docx.Document(file_field)
            return "\n".join([para.text for para in document.paragraphs])
        elif file_name.endswith('.pdf'):
            text = ""
            # Usamos un buffer en memoria para que PyPDF2 pueda leer el archivo de Django
            pdf_buffer = io.BytesIO(file_field.read())
            reader = PyPDF2.PdfReader(pdf_buffer)
            
            # Limitamos la lectura a las primeras 10 páginas para evitar consumo excesivo de RAM
            max_pages = min(len(reader.pages), 10)
            for i in range(max_pages):
                text += reader.pages[i].extract_text()
            return text
        elif file_name.endswith('.txt'):
            return file_field.read().decode('utf-8')
        else:
            return None # Tipo de archivo no soportado
    except Exception as e:
        print(f"Error extrayendo texto del archivo {file_field.name}: {e}")
        return None

@shared_task
def analizar_plagio_tarea_task(entrega_id):
    """
    Tarea de Celery que analiza una entrega de deber para detectar posible plagio
    comparándola con otras entregas para el mismo deber.
    """
    try:
        entrega_actual = EntregaDeber.objects.select_related('deber', 'estudiante').get(pk=entrega_id)
        texto_actual = extract_text_from_file(entrega_actual.archivo_adjunto_estudiante)

        if not texto_actual or len(texto_actual) < 100: # No analizar textos muy cortos
            return f"El texto de la entrega {entrega_id} es demasiado corto para analizar."

        # Buscamos las entregas de otros estudiantes para el mismo deber
        otras_entregas = EntregaDeber.objects.filter(
            deber=entrega_actual.deber
        ).exclude(pk=entrega_id)

        mayor_similitud = 0
        texto_mas_similar = ""

        genai.configure(api_key=settings.GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')

        for otra_entrega in otras_entregas:
            texto_comparar = extract_text_from_file(otra_entrega.archivo_adjunto_estudiante)
            if not texto_comparar:
                continue

            prompt = f"""
            Actúa como un detector de plagio. Compara el "Texto del Estudiante" con el "Texto de Referencia".
            Devuelve un análisis en formato JSON con una única clave: "porcentaje_similitud" (un número entero de 0 a 100).
            No añadas explicaciones, solo el JSON.

            Texto del Estudiante:
            ---
            {texto_actual[:2000]}
            ---

            Texto de Referencia:
            ---
            {texto_comparar[:2000]}
            ---
            """
            
            response = model.generate_content(prompt)
            json_text = response.text.strip().replace("```json", "").replace("```", "")
            resultado = json.loads(json_text)
            
            similitud_actual = resultado.get('porcentaje_similitud', 0)
            if similitud_actual > mayor_similitud:
                mayor_similitud = similitud_actual

        # Si la similitud supera un umbral (ej. 70%), marcamos la entrega
        if mayor_similitud >= 70:
            entrega_actual.porcentaje_similitud = mayor_similitud
            entrega_actual.alerta_plagio = True
            entrega_actual.save()

            # Notificamos al docente
            docente_a_notificar = entrega_actual.deber.curso.docentes_asignados.first()
            if docente_a_notificar:
                Notificacion.objects.create(
                    destinatario=docente_a_notificar.usuario,
                    mensaje=f"Alerta de Plagio: La entrega de '{entrega_actual.estudiante}' para la tarea '{entrega_actual.deber.titulo}' tiene una similitud del {mayor_similitud}%.",
                    enlace=reverse('gestion_academica:calificar_entrega', kwargs={'entrega_pk': entrega_id}),
                    institucion=docente_a_notificar.institucion
                )
        
        return f"Análisis de plagio para entrega {entrega_id} completado. Similitud máxima encontrada: {mayor_similitud}%."

    except EntregaDeber.DoesNotExist:
        return f"Error: No se encontró la entrega con ID {entrega_id}."
    except Exception as e:
        traceback.print_exc()
        return f"Error inesperado en el análisis de plagio: {e}"