"""
gestion_academica/views/ia.py
==============================
Todas las vistas con integración de Inteligencia Artificial:
  - Asistente HALU (chatbot)
  - Planeador de clases con Gemini
  - Análisis de comportamiento estudiantil
  - Optimizador de horarios
  - Generación de resúmenes y correos para acudientes
Extraído del monolito views.py.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy, reverse
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import Group
from django.views.generic import View, ListView, CreateView, UpdateView, DeleteView
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.db.models import Avg, Count, Q
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from celery.result import AsyncResult
import json
import google.generativeai as genai
import google.ai.generativelanguage as glm
import logging

from ..models import (
    Estudiante, Docente, Curso, PeriodoAcademico, Grado, BloqueHorario, Aula,
    ActividadCalificable, Calificacion, AnotacionObservador, AnalisisComportamientoIA,
    PlaneacionClase, DetalleClase, LeccionDiaria, Candidato, Notificacion,
    RegistroAsistencia, TipoActividad, EsquemaCalificacion, Materia,
    DimensionDesarrollo, LogroPreescolar, EscalaCualitativa, DescriptorLogro,
    EvaluacionLogroPreescolar, NivelEscolaridad, Familiar, Usuario,
    DirectorCurso, AreaAcademica, Deber, EntregaDeber, MencionReconocimiento,
)
from ..forms import (
    PlaneacionClaseForm, LeccionDiariaIaForm, CandidatoForm,
    DimensionDesarrolloForm, EscalaCualitativaForm, LogroPreescolarForm,
    DescriptorLogroForm,
)
from ..tasks import (
    generar_contenido_planeacion_task,
    analizar_propuesta_candidato_task,
    analizar_comportamiento_task,
    generar_propuesta_horario_task,
)
from finanzas.models import InstitucionEducativa
from finanzas.institucion_credentials import google_api_key as institucion_google_api_key

# ── Herramientas (tools) para el Asistente HALU ──────────────────────────────
from ..utils import (
    # Admin / Coordinador
    obtener_promedio_materia_por_grado,
    obtener_conteo_estudiantes_por_grado,
    get_absent_students_by_grade,
    obtener_resumen_financiero_estudiantes,
    get_top_student_in_school,
    get_observation_count_for_student,
    # Docente
    obtener_resumen_cursos_docente,
    obtener_estudiantes_riesgo_docente,
    # Estudiante
    obtener_tareas_pendientes_estudiante,
    obtener_resumen_notas_estudiante,
    # Familiar
    obtener_resumen_hijos_familiar,
    # Planeador
    crear_lecciones_diarias_desde_planeacion,
)

logger = logging.getLogger(__name__)

@require_POST
@login_required
def asistente_halu_api(request):
    """
    API para el asistente HALU, con uso de herramientas y manejo
    seguro de múltiples instituciones.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Esta vista solo acepta peticiones POST.'}, status=405)

    try:
        data = json.loads(request.body)
        pregunta = data.get('pregunta', '').strip()
        historial_previo = data.get('historial', [])

        if not pregunta:
            return JsonResponse({'respuesta': 'Por favor, escribe una pregunta.'})

        institucion = getattr(request.user, 'institucion_asociada', None)
        if not institucion:
            return JsonResponse({'respuesta': "Error: Tu usuario no está asociado a ninguna institución."}, status=403)

        api_key = institucion_google_api_key(institucion)
        if not api_key:
            return JsonResponse(
                {'respuesta': "Error de configuración: la institución no tiene configurada la API key de Google (Gemini)."},
                status=500,
            )

        genai.configure(api_key=api_key)

        tools_disponibles = {}
        instrucciones_sistema = ""
        user = request.user

        if user.is_superuser or (hasattr(user, 'rol') and user.rol in ['administrador', 'coordinador']):
            tools_disponibles = {
                'obtener_promedio_materia_por_grado': obtener_promedio_materia_por_grado,
                'obtener_conteo_estudiantes_por_grado': obtener_conteo_estudiantes_por_grado,
                'get_absent_students_by_grade': get_absent_students_by_grade,
                'obtener_resumen_financiero_estudiantes': obtener_resumen_financiero_estudiantes,
                'get_top_student_in_school': get_top_student_in_school,
                'get_observation_count_for_student': get_observation_count_for_student,
            }
            instrucciones_sistema = f"""
Eres HALU, el asistente oficial de la plataforma de gestión escolar HALU, ayudando a {user.get_full_name()} en la institución '{institucion.nombre}'.

## TU PROPÓSITO PRINCIPAL
Eres una guía experta de la plataforma. Tu función prioritaria es enseñar a los usuarios cómo usar cada módulo de HALU. Solo usa herramientas de datos cuando el usuario explícitamente pida números, promedios o consultar información concreta. El ID de la institución es {institucion.id} (úsalo silenciosamente en las herramientas).

## MÓDULOS Y CÓMO FUNCIONAN

### 📋 ADMISIONES
- Gestiona aspirantes desde el módulo "Módulo de Admisiones" en el sidebar.
- El flujo es: crear aspirante → registrar datos → IA analiza la propuesta → decisión de admisión.
- Cada aspirante tiene un formulario con datos personales, documentos y entrevistas.
- Puedes ver el dashboard con estadísticas de admisiones activas.

### 🎓 PROCESO DE GRADUACIÓN
- Accede desde "Proceso de Graduación" en el sidebar.
- Permite gestionar los candidatos al grado de graduación con requisitos académicos y documentales.

### 💻 E-LEARNING (CURSOS VIRTUALES)
- En "Cursos Virtuales" del sidebar puedes: ver el catálogo, gestionar cursos, matricular estudiantes manualmente o hacer alta express.
- Los estudiantes acceden al catálogo de cursos en línea desde su panel.

### 👨‍🎓 GRADOS
- En "Grados" se crean y administran los grados de la institución.
- Cada grado tiene un tipo de evaluación: cuantitativo (notas numéricas) o cualitativo (evaluación por logros).
- Los grados de preescolar usan evaluación cualitativa con dimensiones de desarrollo.

### 👩‍🎓 ESTUDIANTES
- En "Estudiantes" puedes ver la lista de estudiantes organizados por grado.
- Desde cada estudiante puedes ver su perfil, notas, asistencia y observador.
- Para agregar un estudiante, ve a la lista del grado correspondiente y usa el botón "Nuevo Estudiante".

### ✅ CONTROL DE ASISTENCIA
- Accede desde "Control de Asistencia" en el sidebar.
- Muestra el control diario de asistencia de todos los cursos.
- Los docentes registran asistencia desde su propio panel.

### 👥 GESTIÓN DE USUARIOS
- En "Gestión de Usuarios" puedes ver y administrar todos los usuarios de la plataforma.
- Puedes cambiar roles, restablecer contraseñas y activar/desactivar cuentas.

### 👨‍🏫 DOCENTES
- En "Docentes" encuentras la lista completa con opción de importar desde Excel.
- Descarga la plantilla Excel, complétala y súbela para crear docentes masivamente.
- El escaneo QR de asistencia permite registrar la asistencia diaria de docentes.

### 👨‍👩‍👧 FAMILIARES / ACUDIENTES
- "Registrar Familiar" permite crear un acudiente y vincularlo a estudiantes.
- "Cargar Acudientes (masivo)" permite subir un archivo Excel con múltiples familiares.

### 📚 ÁREAS ACADÉMICAS Y MATERIAS
- En "Áreas Académicas" se agrupan las materias por área (Humanidades, Ciencias, etc.).
- En "Materias" se crean las asignaturas vinculadas a un área académica.

### 📅 GESTIÓN DE HORARIOS
- En "Gestión de Horarios" se crean los bloques horarios de la institución.
- Funciona por días de la semana y horas definidas.

### 📖 CURSOS
- En "Cursos" se crean los cursos que combinan un grado + una materia + un docente.
- Cada curso puede tener múltiples docentes asignados.

### 🏫 AULAS
- En "Gestión de Aulas" se registran los salones físicos disponibles.

### 👨‍💼 DIRECTORES DE CURSO
- En "Directores de Curso" se asigna un docente como director de cada grupo/curso.

### 🏆 DESCRIPTORES DE LOGRO
- En "Descriptores" se crean los descriptores de logro por grado, materia y período.
- Los descriptores aparecen en los boletines de calificaciones.
- Se organizan visualmente por grado con acordeón: haz clic en el grado para ver sus descriptores.
- Para crear uno: botón "Nuevo Descriptor" → selecciona grado, materia, período → escribe la descripción.

### 📆 PERIODOS ACADÉMICOS
- En "Periodos" se crean los períodos del año lectivo (Período 1, 2, 3, 4).
- Cada período tiene fecha de inicio, fecha de fin y año lectivo.

### 🏷️ TIPOS DE ACTIVIDAD (CATEGORÍAS)
- En "Tipos de Actividad" se crean las categorías de evaluación (Talleres, Quices, Exámenes, etc.).
- Cada tipo tiene un peso (%) que define cuánto vale en la nota final.
- La suma de pesos de todos los tipos debe ser 100%.

### 💰 MÓDULO DE FINANZAS
- Accede desde "Ir a Módulo de Finanzas" en el sidebar (solo instituciones privadas).
- Gestiona cobros de pensiones, matrículas, pagos y estados de cuenta de estudiantes.

### ⚙️ COORDINADOR — MÓDULOS ESPECIALES

**Dashboard Principal**: KPIs globales de la institución, alertas y resumen del día.

**Sincronizar Permisos**: Actualiza los permisos del sistema después de cambios de rol. Úsalo si un usuario dice que no puede ver algo que debería ver.

**Reporte de Riesgo (IA)**: La IA analiza estudiantes con bajo rendimiento o alta inasistencia y genera alertas automáticas.

**Centro de Reportes**: Genera reportes académicos descargables en PDF/Excel por grado, período o materia.

**Optimizador de Horarios**: La IA propone una distribución óptima de clases según disponibilidad de docentes y aulas.

**Mallas Curriculares**: Define los contenidos por grado y período (ejes temáticos, logros, EBC, DBA, competencias, indicadores por nivel). Una malla por materia+grado+período.

**Supervisión de Planes Semanales**: Revisa y aprueba/rechaza los planes semanales enviados por los docentes. Estados: Borrador → Enviado → Aprobado o Con Observaciones.

**Cortes Preventivos**: Permite registrar un corte de notas parcial para identificar estudiantes en riesgo antes de cerrar el período. Para crear uno: ve a "Cortes Preventivos" → "Nuevo Corte" → selecciona período y fecha.

**Alertas de Bienestar / Halu Sentinel**: Sentinel monitorea automáticamente patrones de riesgo (inasistencia, caída de notas, anotaciones negativas) y genera alertas. El coordinador revisa y gestiona las alertas desde este módulo.

**Historial de Convivencia**: Registra y consulta las anotaciones del observador de todos los estudiantes con filtros por fecha y grado.

**Supervisión de Citas**: Gestiona las citas entre docentes/coordinadores y acudientes.

**Secuencia de Promoción**: Configura los criterios para promover estudiantes al siguiente grado.

**Esquemas de Calificación**: Define cómo se calculan las notas finales (pesos por período, redondeos, escala).

**Generar Certificados**: Produce certificados de estudio para estudiantes seleccionados en formato PDF.

## ESTILO DE RESPUESTA
- Responde siempre en español, de forma clara y amigable.
- Usa listas y pasos numerados para explicar procesos.
- Si el usuario pregunta cómo hacer algo, da los pasos exactos con el nombre del menú o sección.
- Solo usa herramientas de datos (promedios, conteos, etc.) cuando el usuario pida explícitamente esa información.
- Cuando uses una herramienta, presenta el resultado de forma legible con contexto.
- Si no sabes algo específico de la institución, di honestamente que no tienes esa información disponible.
"""
        elif hasattr(user, 'rol') and user.rol == 'docente':
            tools_disponibles = {
                'obtener_resumen_cursos_docente': obtener_resumen_cursos_docente,
                'obtener_estudiantes_riesgo_docente': obtener_estudiantes_riesgo_docente,
            }
            instrucciones_sistema = f"""
Eres HALU, el asistente oficial de la plataforma de gestión escolar HALU, ayudando al docente {user.get_full_name()} en '{institucion.nombre}'.

## TU PROPÓSITO PRINCIPAL
Eres una guía experta de la plataforma. Enseña al docente cómo usar cada módulo y responde sus dudas sobre la plataforma. Solo usa herramientas de datos cuando el usuario pida explícitamente información sobre sus cursos o estudiantes.

## MÓDULOS DEL DOCENTE Y CÓMO FUNCIONAN

### 🏠 PANEL PRINCIPAL (Dashboard)
Tu página de inicio muestra: cursos asignados, planes pendientes, deberes activos y notificaciones recientes.

### 🤖 PLANEADOR DE CLASES (IA)
- Accede desde "Centro de Gestión" → "Planeador de Clases (IA)".
- Selecciona un curso y la IA genera un plan de clase completo basado en la malla curricular.
- Puedes personalizar el plan generado antes de guardarlo.
- Los planes generados quedan guardados en el historial del planeador.

### 📅 MIS PLANES SEMANALES
- Accede desde "Centro de Gestión" → "Mis Planes Semanales".
- Crea un plan para la semana seleccionando curso, semana y describiendo las actividades.
- **Flujo de estados**: Borrador → Enviado (para revisión del coordinador) → Aprobado o Con Observaciones.
- Para enviar al coordinador: abre el plan y usa el botón "Enviar para revisión".
- Si tiene observaciones, puedes editarlo y volver a enviarlo.

### 🏷️ CATEGORÍAS DE ACTIVIDAD
- En "Centro de Gestión" → "Categorías de Actividad" ves los tipos de evaluación disponibles.
- Estas categorías las define el coordinador (Talleres, Quices, Exámenes, etc.) con su peso en porcentaje.

### 📝 DEFINIR ACTIVIDADES (ACTIVIDADES CALIFICABLES)
- En "Centro de Gestión" → "Definir Actividades" creas actividades evaluables para tus cursos.
- Cada actividad tiene: nombre, categoría, fecha, valor máximo y descripción.
- Las actividades aparecen en el libro de notas para calificar estudiantes.

### 📚 GESTIONAR DEBERES
- En "Centro de Gestión" → "Gestionar Deberes" creas tareas para que los estudiantes entreguen.
- Cada deber tiene: título, descripción, fecha de entrega y curso asignado.
- Los estudiantes ven los deberes desde su panel y pueden marcarlos como entregados.

### 🏆 GESTIONAR DESCRIPTORES
- En "Centro de Gestión" → "Gestionar Descriptores" ves y creas descriptores de logro para tus materias.
- Los descriptores describen qué se espera que el estudiante logre en el período.
- Selecciona materia, grado y período al crear un descriptor.

### 🧠 EVALUACIONES CON IA (CUESTIONARIOS)
- En "Centro de Gestión" → "Evaluaciones con IA" la IA genera cuestionarios/exámenes automáticamente.
- Elige el tema, el grado y el tipo de preguntas (opción múltiple, verdadero/falso, etc.).
- Los cuestionarios generados puedes editarlos y asignarlos a cursos.

### 📖 LIBRO DE NOTAS
- En "Centro de Gestión" → "Libro de Notas" registras las calificaciones de tus estudiantes.
- Selecciona el curso, luego verás la lista de estudiantes con columnas por actividad.
- Haz clic en una celda para ingresar la nota. Los cambios se guardan automáticamente.
- Para grados cualitativos (preescolar), el libro muestra los logros por dimensión.

### 🖼️ GALERÍA 3D
- En "Centro de Gestión" → "Galería 3D" puedes subir y ver recursos visuales educativos en 3D.

### 📁 MATERIALES DE APOYO
- En "Centro de Gestión" → "Materiales de Apoyo" subes archivos (PDFs, videos, links) para tus estudiantes.
- Los materiales quedan disponibles para los estudiantes del curso asignado.

### 🎖️ MENCIONES Y HONORES
- En "Centro de Gestión" → "Menciones y Honores" puedes otorgar reconocimientos a estudiantes destacados.
- Elige el estudiante, el tipo de mención y el período.

### 👁️ OBSERVADOR
- En "Centro de Gestión" → "Observador" registras anotaciones de comportamiento o situaciones especiales de estudiantes.
- Selecciona el estudiante, el tipo de anotación (positiva, negativa, informativa) y escribe la observación.
- Estas anotaciones son visibles para el coordinador y se acumulan en el historial de convivencia.

### 📊 REPORTES
- "Reporte Nota Mínima": muestra estudiantes por debajo de la nota mínima aprobatoria en un curso.
- "Reporte Global de Riesgo": vista general de todos los cursos con estudiantes en riesgo académico.

### 🕐 MI DISPONIBILIDAD
- En "Mi Disponibilidad" registras tus horarios libres para que el optimizador de horarios los tenga en cuenta.

### 📋 HISTORIAL DE LECCIONES
- En "Historial de Lecciones" ves el registro de todas las clases dictadas (lecciones diarias).

### 👥 ASISTIR EN OTRO CURSO
- Permite tomar asistencia en un curso que no sea el tuyo (reemplazos o cobertura).

## ESTILO DE RESPUESTA
- Responde siempre en español, de forma amigable y motivadora.
- Da pasos numerados y claros cuando expliques cómo hacer algo.
- Solo usa herramientas de datos cuando el usuario pida explícitamente información de sus cursos o estudiantes en riesgo.
- Si no sabes algo, sé honesto y sugiere consultar al coordinador.
"""
        elif hasattr(user, 'rol') and user.rol == 'estudiante':
            tools_disponibles = {
                'obtener_tareas_pendientes_estudiante': obtener_tareas_pendientes_estudiante,
                'obtener_resumen_notas_estudiante': obtener_resumen_notas_estudiante,
            }
            instrucciones_sistema = f"""
Eres HALU, el asistente oficial de la plataforma escolar, ayudando al estudiante {user.get_full_name()} en '{institucion.nombre}'.

## TU PROPÓSITO PRINCIPAL
Eres el guía personal del estudiante en la plataforma. Explica cómo usar cada sección, motívalo y ayúdalo a encontrar lo que necesita. Solo usa herramientas de datos cuando pida ver sus notas o deberes pendientes.

## SECCIONES DEL ESTUDIANTE Y CÓMO FUNCIONAN

### 🏠 MI PANEL (Dashboard)
Tu página principal muestra un resumen de: próximas actividades, deberes pendientes, horario del día y notificaciones. Es tu punto de partida.

### 📅 MI HORARIO
Desde "Mi Horario" (en el menú lateral o en "Mi Panel" sección horario) puedes ver las clases de toda la semana organizadas por día y hora.

### 📆 MI AGENDA
En "Mi Agenda" aparecen los eventos importantes: exámenes, entrega de deberes, actividades especiales.

### 📄 MI BOLETÍN
- En "Mi Boletín" puedes ver tu boletín de calificaciones del período actual.
- Muestra tus notas por materia con el desglose por tipo de actividad.
- Si quieres ver boletines de períodos anteriores, el coordinador puede generarlos.

### 💻 E-LEARNING
- En "E-learning" accedes al catálogo de cursos virtuales disponibles.
- Puedes inscribirte en cursos y ver tu progreso en cada uno.
- Los cursos tienen lecciones, videos y evaluaciones en línea.

### 📬 NOTIFICACIONES
- El ícono de campana en la barra superior muestra tus notificaciones recientes.
- Recibirás notificaciones cuando un docente califica una actividad, te asigna un deber o deja una observación.

### 💬 MENSAJES
- Puedes enviar y recibir mensajes con docentes y acudientes desde el ícono de chat.

### 👤 MI PERFIL
- En "Mi Perfil" (menú arriba a la derecha) puedes actualizar tu foto y datos personales.
- También puedes cambiar tu contraseña desde el menú de usuario.

## ESTILO DE RESPUESTA
- Habla de forma amigable, cercana y motivadora.
- Explica los pasos de forma sencilla sin tecnicismos.
- Si el estudiante pide que hagas su tarea, guíalo con preguntas para que aprenda, no le des la respuesta directa.
- Solo consulta notas o deberes cuando el estudiante lo pida explícitamente.
"""
        elif hasattr(user, 'rol') and user.rol == 'familiar':
            tools_disponibles = {
                'obtener_resumen_hijos_familiar': obtener_resumen_hijos_familiar,
            }
            instrucciones_sistema = f"""
Eres HALU, el asistente oficial de la plataforma escolar, ayudando a {user.get_full_name()}, familiar de estudiantes en '{institucion.nombre}'.

## TU PROPÓSITO PRINCIPAL
Orienta al acudiente sobre cómo usar la plataforma para hacer seguimiento a sus hijos. Solo consulta datos cuando lo pida explícitamente.

## SECCIONES DEL PORTAL FAMILIAR Y CÓMO FUNCIONAN

### 👨‍👩‍👧 MIS ESTUDIANTES
- En "Mis Estudiantes" ves la lista de estudiantes vinculados a tu cuenta.
- Haz clic en un estudiante para ver su resumen: notas, asistencia y deberes pendientes.

### 📄 VER BOLETÍN
- Desde el perfil del estudiante puedes acceder a su boletín de calificaciones del período actual.
- Muestra las notas por materia y el promedio general.

### ✅ ASISTENCIA
- Puedes consultar el registro de asistencia de tu hijo: días presentes, ausentes y tardanzas.

### 📬 NOTIFICACIONES
- Recibes notificaciones automáticas cuando hay cambios importantes: nuevas notas, deberes asignados, observaciones del docente.
- El ícono de campana en la barra superior muestra tus notificaciones.

### 💬 MENSAJES
- Puedes enviar mensajes directamente a los docentes de tus hijos desde el ícono de chat.
- Los docentes pueden responderte desde su panel.

### 👤 MI PERFIL
- En "Mi Perfil" puedes actualizar tus datos de contacto y foto.
- Para cambiar la contraseña, usa el menú de usuario (tu nombre en la esquina superior derecha).

## ESTILO DE RESPUESTA
- Habla de forma cordial, clara y tranquilizadora.
- Explica los procesos paso a paso.
- Destaca cómo la plataforma ayuda a estar conectado con la educación de sus hijos.
- Solo consulta datos de sus hijos cuando lo pida explícitamente.
"""
        else:
            instrucciones_sistema = f"Eres HALU, el asistente virtual amigable de la plataforma escolar en '{institucion.nombre}'. Responde en español de forma amigable y ayuda al usuario a navegar la plataforma."

        model_kwargs = {'model_name': 'gemini-2.5-flash'}
        if tools_disponibles:
            model_kwargs['tools'] = list(tools_disponibles.values())

        model = genai.GenerativeModel(**model_kwargs)
        chat = model.start_chat(history=historial_previo)

        mensaje_enviar = pregunta
        if not historial_previo:
            mensaje_enviar = f"{instrucciones_sistema}\n\nPregunta del usuario: {pregunta}"

        response = chat.send_message(mensaje_enviar)

        # Loop de herramientas — máx. 6 iteraciones para evitar bucles infinitos
        for _ in range(6):
            fc_part = _primera_function_call(response)
            if not fc_part:
                break

            tool_name = fc_part.function_call.name
            tool_args = {}
            if hasattr(fc_part.function_call, 'args'):
                for key in fc_part.function_call.args:
                    tool_args[key] = fc_part.function_call.args[key]

            if tool_name not in tools_disponibles:
                break

            tool_function = tools_disponibles[tool_name]
            co_vars = tool_function.__code__.co_varnames
            if 'institucion_id' in co_vars and 'institucion_id' not in tool_args:
                tool_args['institucion_id'] = institucion.id
            if 'docente_usuario_id' in co_vars and 'docente_usuario_id' not in tool_args:
                tool_args['docente_usuario_id'] = request.user.id
            if 'estudiante_usuario_id' in co_vars and 'estudiante_usuario_id' not in tool_args:
                tool_args['estudiante_usuario_id'] = request.user.id
            if 'familiar_usuario_id' in co_vars and 'familiar_usuario_id' not in tool_args:
                tool_args['familiar_usuario_id'] = request.user.id

            try:
                tool_result = tool_function(**tool_args)
            except Exception as e:
                tool_result = f"Error al obtener datos: {str(e)}"

            response = chat.send_message(
                glm.Part(
                    function_response=glm.FunctionResponse(
                        name=tool_name,
                        response={'resultado': str(tool_result)}
                    )
                )
            )

        # Extraer texto de forma segura (response.text falla si hay function_call parts)
        texto_final = _extraer_texto(response)
        if not texto_final:
            response = chat.send_message(
                "Por favor, presenta los resultados obtenidos en un texto claro y amigable para el usuario."
            )
            texto_final = _extraer_texto(response) or "No pude generar una respuesta. Por favor intenta reformular tu pregunta."

        # Historial: solo partes de texto para el frontend
        nuevo_historial = []
        for message in chat.history:
            textos = [p.text for p in message.parts if hasattr(p, 'text') and p.text]
            if textos:
                nuevo_historial.append({
                    "role": message.role,
                    "parts": [{"text": "\n".join(textos)}]
                })

        return JsonResponse({'respuesta': texto_final, 'historial': nuevo_historial})

    except Exception as e:
        logger.error(f"Error inesperado en asistente_halu_api: {e}", exc_info=True)
        return JsonResponse({'respuesta': f"Ocurrió un error interno en la IA: {str(e)}. Por favor, avisa a soporte."}, status=500)


def _primera_function_call(response):
    """Devuelve el primer part con function_call en la respuesta, o None."""
    try:
        if not response.candidates:
            return None
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'function_call') and part.function_call and part.function_call.name:
                return part
    except Exception:
        pass
    return None


def _extraer_texto(response):
    """Extrae texto de la respuesta de Gemini sin fallar si hay function_call parts."""
    try:
        if not response.candidates:
            return None
        texts = [
            p.text for p in response.candidates[0].content.parts
            if hasattr(p, 'text') and p.text
        ]
        return '\n'.join(texts) if texts else None
    except Exception:
        return None

@login_required
def redirigir_a_libro_de_notas(request, curso_pk):
    """
    Vista inteligente que actúa como un despachador.
    Revisa el tipo de evaluación del curso y redirige al docente
    a la vista de calificación correcta (cuantitativa o cualitativa).
    """
    # 1. Obtenemos el curso y su grado para verificar el tipo de evaluación
    curso = get_object_or_404(
        Curso.objects.select_related('grado'), 
        pk=curso_pk
    )

    # 2. Lógica de seguridad: solo el docente del curso o un admin pueden acceder
    if not (request.user.is_staff or (hasattr(request.user, 'docente') and request.user.docente in curso.docentes_asignados.all())):
        messages.error(request, "No tienes permiso para acceder a este curso.")
        return redirect('gestion_academica:dashboard_docente')

    # 3. ¡LA LÓGICA CLAVE! Leemos el campo del modelo Grado
    if curso.grado.tipo_evaluacion == 'CUALITATIVO':
        # Si es cualitativo, redirigimos a la vista de evaluación de logros
        return redirect('gestion_academica:evaluar_logros_curso', curso_pk=curso.pk)
    else:
        # Por defecto, o si es cuantitativo, redirigimos al libro de notas numérico
        return redirect('gestion_academica:docente_libro_de_notas_por_curso', curso_pk=curso.pk)

@login_required
def gestionar_curso_cualitativo(request, curso_pk):
    curso = get_object_or_404(Curso.objects.select_related('grado'), pk=curso_pk)
    
    # Doble verificación de seguridad
    if curso.grado.tipo_evaluacion != 'CUALITATIVO':
        messages.error(request, "Esta sección es solo para cursos de evaluación cualitativa.")
        return redirect('gestion_academica:dashboard_docente')

    context = {
        'titulo_pagina': f"Gestionar Curso: {curso.materia.nombre_materia} ({curso.grado.nombre})",
        'curso': curso
    }
    return render(request, 'gestion_academica/gestion_curso_cualitativo.html', context)

class DimensionListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = DimensionDesarrollo
    template_name = 'gestion_academica/dimension_lista.html'
    context_object_name = 'dimensiones'
    permission_required = 'gestion_academica.view_dimensiondesarrollo' # Necesitarás crear este permiso

    def get_queryset(self):
        return get_filtered_queryset(self.model, self.request.user).order_by('orden')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Gestionar Dimensiones de Desarrollo (Preescolar)"
        return context

class DimensionCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = DimensionDesarrollo
    form_class = DimensionDesarrolloForm
    template_name = 'gestion_academica/dimension_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_dimensiones')
    permission_required = 'gestion_academica.add_dimensiondesarrollo'

    def form_valid(self, form):
        form.instance.institucion = self.request.user.institucion_asociada
        messages.success(self.request, "Dimensión creada exitosamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Crear Nueva Dimensión"
        return context

class DimensionUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = DimensionDesarrollo
    form_class = DimensionDesarrolloForm
    template_name = 'gestion_academica/dimension_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_dimensiones')
    permission_required = 'gestion_academica.change_dimensiondesarrollo'

    def get_queryset(self):
        return get_filtered_queryset(self.model, self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Dimensión actualizada exitosamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = f"Editar Dimensión: {self.object.nombre}"
        return context

class DimensionDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = DimensionDesarrollo
    template_name = 'gestion_academica/confirmar_eliminar_generico.html'
    success_url = reverse_lazy('gestion_academica:lista_dimensiones')
    permission_required = 'gestion_academica.delete_dimensiondesarrollo'
    context_object_name = 'object'

    def get_queryset(self):
        return get_filtered_queryset(self.model, self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, f"La dimensión '{self.object.nombre}' ha sido eliminada.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Confirmar Eliminación de Dimensión"
        context['mensaje_confirmacion'] = f"¿Estás seguro de que deseas eliminar la dimensión '{self.object.nombre}'? Todos los logros asociados perderán esta categoría."
        context['url_cancelar'] = reverse_lazy('gestion_academica:lista_dimensiones')
        return context    

class EscalaCualitativaListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = EscalaCualitativa
    template_name = 'gestion_academica/escala_cualitativa_lista.html'
    context_object_name = 'escalas'
    permission_required = 'gestion_academica.view_escalacualitativa'

    def get_queryset(self):
        return get_filtered_queryset(self.model, self.request.user).order_by('orden')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Gestionar Escala Cualitativa (Preescolar)"
        return context

class EscalaCualitativaCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = EscalaCualitativa
    form_class = EscalaCualitativaForm
    template_name = 'gestion_academica/escala_cualitativa_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_escala_cualitativa')
    permission_required = 'gestion_academica.add_escalacualitativa'

    def form_valid(self, form):
        form.instance.institucion = self.request.user.institucion_asociada
        messages.success(self.request, "Nuevo nivel de escala creado exitosamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Crear Nuevo Nivel de Escala"
        return context

class EscalaCualitativaUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = EscalaCualitativa
    form_class = EscalaCualitativaForm
    template_name = 'gestion_academica/escala_cualitativa_formulario.html'
    success_url = reverse_lazy('gestion_academica:lista_escala_cualitativa')
    permission_required = 'gestion_academica.change_escalacualitativa'

    def get_queryset(self):
        return get_filtered_queryset(self.model, self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Nivel de escala actualizado exitosamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = f"Editar Nivel: {self.object.nombre_escala}"
        return context

class EscalaCualitativaDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = EscalaCualitativa
    template_name = 'gestion_academica/confirmar_eliminar_generico.html'
    success_url = reverse_lazy('gestion_academica:lista_escala_cualitativa')
    permission_required = 'gestion_academica.delete_escalacualitativa'
    context_object_name = 'object'

    def get_queryset(self):
        return get_filtered_queryset(self.model, self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, f"El nivel de escala '{self.object.nombre_escala}' ha sido eliminado.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Confirmar Eliminación de Nivel de Escala"
        context['mensaje_confirmacion'] = f"¿Estás seguro de que deseas eliminar el nivel '{self.object.nombre_escala}'?"
        context['url_cancelar'] = reverse_lazy('gestion_academica:lista_escala_cualitativa')
        return context        

class LogroListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = LogroPreescolar
    template_name = 'gestion_academica/logro_lista.html'
    context_object_name = 'logros'
    permission_required = 'gestion_academica.view_logropreescolar' # <-- CORREGIDO

    def get_queryset(self):
        return get_filtered_queryset(self.model, self.request.user).select_related('materia', 'periodo').order_by('-periodo__año_escolar', 'materia__nombre_materia')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Mis Logros de Aprendizaje (Preescolar)"
        return context

class LogroCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = LogroPreescolar
    form_class = LogroPreescolarForm
    template_name = 'gestion_academica/logro_formulario.html'
    success_url = reverse_lazy('gestion_academica:logro_lista')
    permission_required = 'gestion_academica.add_logropreescolar' # <-- CORREGIDO

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.institucion = self.request.user.institucion_asociada
        messages.success(self.request, "Logro de Preescolar creado exitosamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Crear Nuevo Logro de Preescolar"
        return context

class LogroUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = LogroPreescolar
    form_class = LogroPreescolarForm
    template_name = 'gestion_academica/logro_formulario.html'
    success_url = reverse_lazy('gestion_academica:logro_lista')
    permission_required = 'gestion_academica.change_logropreescolar' # <-- CORREGIDO

    def get_queryset(self):
        return get_filtered_queryset(self.model, self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, "Logro de Preescolar actualizado exitosamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_formulario'] = "Editar Logro de Preescolar"
        return context

class LogroDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = LogroPreescolar
    template_name = 'gestion_academica/confirmar_eliminar_generico.html'
    success_url = reverse_lazy('gestion_academica:logro_lista')
    permission_required = 'gestion_academica.delete_logropreescolar' # <-- CORREGIDO
    context_object_name = 'object'

    def get_queryset(self):
        return get_filtered_queryset(self.model, self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, "El logro de Preescolar ha sido eliminado.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo_pagina'] = "Confirmar Eliminación de Logro"
        context['mensaje_confirmacion'] = f"¿Estás seguro de que deseas eliminar este logro?"
        context['url_cancelar'] = reverse_lazy('gestion_academica:logro_lista')
        return context       

@login_required
def boletin_descriptivo_preescolar_pdf(request, estudiante_pk, periodo_pk):
    """
    Genera un boletín en PDF CUALITATIVO para un estudiante de Preescolar.
    VERSIÓN FINAL: La vista prepara todos los datos para que la plantilla sea simple.
    """
    # 1. Obtención de datos y seguridad (se mantiene tu lógica)
    try:
        estudiante = Estudiante.objects.select_related(
            'usuario', 'grado_actual', 'institucion'
        ).get(pk=estudiante_pk)
        periodo = PeriodoAcademico.objects.get(
            pk=periodo_pk, institucion=estudiante.institucion
        )
    except (Estudiante.DoesNotExist, PeriodoAcademico.DoesNotExist):
        messages.error(request, "El estudiante o periodo solicitado no es válido.")
        return redirect('gestion_academica:inicio_academico')

    # (Tu lógica de permisos se mantiene)
    if not (request.user.pk == estudiante.usuario.pk or request.user.is_staff or (hasattr(request.user, 'familiar') and request.user.familiar.estudiantes_asociados.filter(pk=estudiante_pk).exists())):
        messages.error(request, "No tienes permiso para ver este boletín.")
        return redirect('gestion_academica:inicio_academico')

    # --- INICIO DE LA LÓGICA DE CONSULTA CORREGIDA ---
    
    # 2. Obtenemos las evaluaciones del estudiante para este periodo
    evaluaciones_del_estudiante = EvaluacionLogroPreescolar.objects.filter(
        estudiante=estudiante,
        logro__periodo=periodo
    ).select_related('estado')
    
    # Creamos un mapa para buscar rápidamente la evaluación de cada logro
    evaluaciones_map = {ev.logro_id: ev.estado for ev in evaluaciones_del_estudiante}

    # 3. Obtenemos las Dimensiones y, para cada una, sus logros correspondientes
    dimensiones_con_logros = DimensionDesarrollo.objects.filter(
        institucion=estudiante.institucion
    ).prefetch_related(
        Prefetch(
            'logros_preescolar',
            queryset=LogroPreescolar.objects.filter(
                periodo=periodo,
                materia__cursos__grado=estudiante.grado_actual
            ).distinct(),
            to_attr='logros_de_la_dimension'
        )
    ).order_by('orden')
    
    # 4. *** EL PASO CLAVE ***
    #    Añadimos la evaluación directamente a cada objeto 'logro'
    for dimension in dimensiones_con_logros:
        for logro in dimension.logros_de_la_dimension:
            # .get() devuelve la evaluación si existe, o None si no existe (sin dar error)
            logro.evaluacion = evaluaciones_map.get(logro.id)

    # --- FIN DE LA LÓGICA DE CONSULTA CORREGIDA ---

    # 5. Obtenemos datos adicionales (tu lógica original)
    escala_cualitativa = EscalaCualitativa.objects.filter(institucion=estudiante.institucion).order_by('orden')
    observacion_obj = ObservacionBoletin.objects.filter(estudiante=estudiante, periodo=periodo).first()
    director_de_grupo = DirectorCurso.objects.select_related('docente__usuario').filter(
        grado=estudiante.grado_actual, periodo_academico=periodo
    ).first()

    # 6. Construimos el contexto final
    context = {
        'institucion': estudiante.institucion,
        'periodo': periodo,
        'estudiante': estudiante,
        'dimensiones_data': dimensiones_con_logros,
        'escala_cualitativa': escala_cualitativa,
        'director_de_grupo': director_de_grupo,
        'observaciones': observacion_obj.observacion if observacion_obj else "No hay observaciones registradas.",
        'fecha_emision': timezone.now(),
    }

    # 7. Renderizamos el PDF
    template_path = 'gestion_academica/boletin_descriptivo_preescolar.html'
    template = get_template(template_path)
    html = template.render(context)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Boletin_Descriptivo_{estudiante.usuario.username}.pdf"'
    
    pisa_status = pisa.CreatePDF(html, dest=response, link_callback=link_callback)
    
    if pisa_status.err:
        return HttpResponse('Ocurrió un error al generar el PDF <pre>' + html + '</pre>')
        
    return response

@login_required
def planeacion_clases_view(request):
    """
    Vista principal para el módulo de planeación de clases.
    AHORA: Crea la planeación, la pone a generar y redirige al detalle.
    """
    try:
        docente = request.user.docente
    except AttributeError:
        messages.error(request, "Acceso denegado. Esta sección es solo para docentes.")
        return redirect('gestion_academica:inicio_academico')

    if request.method == 'POST':
        form = PlaneacionClaseForm(request.POST, user=request.user)
        if form.is_valid():
            # 1. Crea la instancia pero no la guardes aún en la base de datos
            planeacion = form.save(commit=False)
            planeacion.docente = docente
            
            # --- INICIO DE LA CORRECCIÓN CLAVE ---
            # 2. Establece el estado a 'GENERANDO' inmediatamente
            planeacion.estado_generacion = PlaneacionClase.EstadoGeneracion.GENERANDO
            
            # 3. Guarda la planeación en la base de datos. Ahora se crea con el estado correcto.
            planeacion.save()

            # 4. Llama a la tarea de Celery para que comience a trabajar
            from .tasks import generar_contenido_planeacion_task
            generar_contenido_planeacion_task.delay(planeacion.pk)
            
            # 5. Redirige al usuario DIRECTAMENTE a la página de detalle
            messages.info(request, "La generación de la planeación ha comenzado. La página se actualizará automáticamente.")
            return redirect('gestion_academica:planeacion_detalle', pk=planeacion.pk) 
            # --- FIN DE LA CORRECCIÓN CLAVE ---

    else:
        form = PlaneacionClaseForm(user=request.user)

    planeaciones_existentes = PlaneacionClase.objects.filter(docente=docente).select_related('curso__materia', 'curso__grado')

    context = {
        'titulo_pagina': "Planeador de Clases con IA",
        'form': form,
        'planeaciones': planeaciones_existentes
    }
    return render(request, 'gestion_academica/planeacion_clases.html', context)
  

@login_required
def planeacion_detalle_view(request, pk):
    """
    Muestra el detalle de una planeación y lanza la tarea de Celery
    para generar el contenido con IA.
    """
    planeacion = get_object_or_404(PlaneacionClase, pk=pk, docente=request.user.docente)

    # Si la petición es POST, significa que el usuario hizo clic en "Generar" o "Reintentar"
    if request.method == 'POST':
        # Cambiamos el estado a 'GENERANDO' inmediatamente para que el usuario vea el feedback
        planeacion.estado_generacion = PlaneacionClase.EstadoGeneracion.GENERANDO
        planeacion.error_generacion = None
        planeacion.save()

        # Despachamos la tarea a Celery. Esto es instantáneo.
        generar_contenido_planeacion_task.delay(planeacion.id)
        
        messages.info(request, "La IA ha comenzado a generar tu planeación. La página se actualizará automáticamente cuando esté lista.")
        # Redirigimos de vuelta a la misma página para mostrar el estado "Generando..."
        return redirect('gestion_academica:planeacion_detalle', pk=pk)

    context = {
        'titulo_pagina': f"Planeación: {planeacion.titulo}",
        'planeacion': planeacion,
    }
    return render(request, 'gestion_academica/planeacion_detalle.html', context)


@login_required
@require_POST # Esta vista solo acepta peticiones POST para mayor seguridad
def cancelar_generacion_planeacion(request, pk):
    """
    Permite al docente cancelar una tarea de generación de planeación
    que se ha quedado atascada en el estado 'GENERANDO'.
    """
    planeacion = get_object_or_404(PlaneacionClase, pk=pk, docente=request.user.docente)

    # Solo actuamos si la planeación está efectivamente "generando"
    if planeacion.estado_generacion == PlaneacionClase.EstadoGeneracion.GENERANDO:
        planeacion.estado_generacion = PlaneacionClase.EstadoGeneracion.FALLIDO
        planeacion.error_generacion = "El proceso de generación fue cancelado manualmente por el usuario."
        planeacion.save()
        messages.warning(request, "El proceso de generación de la planeación ha sido detenido.")
    else:
        messages.info(request, "Esta planeación no se estaba generando activamente.")

    return redirect('gestion_academica:planeacion_detalle', pk=planeacion.pk)    

@login_required
@never_cache
def get_planeacion_status_api(request, pk):
    """Endpoint de polling para el modal del planeador IA.

    Devuelve estado + datos suficientes para que el frontend muestre un toast
    informativo al completarse (o un mensaje de error detallado al fallar) sin
    necesidad de recargar antes para "descubrir" qué pasó.
    """
    try:
        planeacion = PlaneacionClase.objects.get(pk=pk)

        if not request.user.is_superuser:
            if not hasattr(request.user, 'docente') or planeacion.docente_id != request.user.docente.pk:
                return JsonResponse({'status': 'FORBIDDEN'}, status=403)

        estado = str(planeacion.estado_generacion or "").strip().upper()
        detalles_count = planeacion.detalles_clase.count()

        data = {
            'status': estado,
            'detalles_count': detalles_count,
            'error_generacion': planeacion.error_generacion or "",
            'titulo': planeacion.titulo,
            'duracion_clases': planeacion.duracion_clases,
        }

        # Mensaje listo para mostrarse como toast en el frontend
        if estado == "COMPLETADO":
            data['mensaje'] = (
                f"¡Planeación generada con éxito! Se crearon "
                f"{detalles_count} clase{'s' if detalles_count != 1 else ''} para '{planeacion.titulo}'."
            )
        elif estado == "FALLIDO":
            data['mensaje'] = (
                f"La generación falló: {planeacion.error_generacion or 'error desconocido'}."
            )
        elif estado == "GENERANDO":
            data['mensaje'] = "La IA sigue procesando tu planeación. Por favor espera…"
        else:
            data['mensaje'] = "Pendiente de iniciar la generación."

        return JsonResponse(data)
    except PlaneacionClase.DoesNotExist:
        return JsonResponse({'status': 'NOT_FOUND'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'ERROR', 'message': str(e)}, status=500)

@login_required
def generar_planeacion_pdf(request, pk):
    """
    Genera un documento PDF para una planeación de clase específica.
    """
    try:
        # Buscamos la planeación, asegurándonos de que pertenezca al docente logueado
        planeacion = get_object_or_404(PlaneacionClase, pk=pk, docente=request.user.docente)
        
        # Obtenemos los detalles de la clase asociados
        detalles = planeacion.detalles_clase.all()

        # Preparamos el contexto para la plantilla del PDF
        context = {
            'planeacion': planeacion,
            'detalles': detalles,
            'institucion': planeacion.institucion,
        }

        template_path = 'gestion_academica/pdfs/planeacion_pdf.html'
        template = get_template(template_path)
        html = template.render(context)

        # Creamos el PDF en memoria
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="planeacion_{planeacion.titulo}.pdf"'
        
        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(html, dest=pdf_buffer)

        if pisa_status.err:
            return HttpResponse('Ocurrió un error al generar el PDF <pre>' + html + '</pre>')

        response.write(pdf_buffer.getvalue())
        return response

    except Exception as e:
        logger.error(f"Error al generar el PDF de la planeación {pk}: {e}", exc_info=True)
        messages.error(request, "No se pudo generar el PDF de la planeación.")
        return redirect('gestion_academica:planeacion_detalle', pk=pk)



@login_required
@require_POST # Esta vista solo se puede llamar con un método POST para seguridad
def anadir_planeacion_a_lecciones(request, pk):
    """
    Activa el proceso de crear los registros de LeccionDiaria a partir de una planeación.
    """
    planeacion = get_object_or_404(PlaneacionClase, pk=pk, docente=request.user.docente)
    
    # Llamamos a la función del utils.py que hace todo el trabajo
    lecciones_creadas, mensaje = crear_lecciones_diarias_desde_planeacion(planeacion.id)
    
    if lecciones_creadas > 0:
        messages.success(request, mensaje)
    else:
        messages.error(request, mensaje)
        
    return redirect('gestion_academica:planeacion_detalle', pk=planeacion.pk)


@login_required
@permission_required('gestion_academica.view_bloquehorario', raise_exception=True)
def gestion_horarios_view(request):
    """
    Muestra una vista organizada de todos los horarios de la institución,
    agrupados por Nivel de Escolaridad y Grado, en una parrilla correcta.
    """
    institucion = request.user.institucion_asociada
    
    # Obtenemos los niveles y grados para la navegación/filtros
    niveles = NivelEscolaridad.objects.filter(institucion=institucion).order_by('pk')
    
    # Lógica de filtrado
    grado_seleccionado = None
    grado_id = request.GET.get('grado_id')
    if grado_id:
        grado_seleccionado = get_object_or_404(Grado, pk=grado_id, institucion=institucion)

    horario_grid = {}
    horas_del_dia = []
    
    if grado_seleccionado:
        bloques = BloqueHorario.objects.filter(
            curso__grado=grado_seleccionado
        ).select_related('curso__materia', 'aula').order_by('hora_inicio', 'dia_semana')

        # --- INICIO DE LA LÓGICA CLAVE ---
        # 1. Obtenemos todas las franjas horarias únicas del día
        horas_del_dia = sorted(list(set(b.hora_inicio for b in bloques)))
        
        # 2. Creamos un mapa para acceso rápido: {(hora, dia): bloque}
        bloques_map = {(b.hora_inicio, b.dia_semana): b for b in bloques}
        
        # 3. Construimos la parrilla (grid) que la plantilla usará
        for hora in horas_del_dia:
            horario_grid[hora] = {}
            for dia in range(5): # 0=Lunes, 1=Martes, ..., 4=Viernes
                horario_grid[hora][dia] = bloques_map.get((hora, dia))
        # --- FIN DE LA LÓGICA CLAVE ---

    context = {
        'titulo_pagina': "Gestión de Horarios por Grado",
        'niveles_escolaridad': niveles,
        'grados': Grado.objects.filter(institucion=institucion).order_by('orden'),
        'grado_seleccionado': grado_seleccionado,
        'horario_grid': horario_grid,
        'horas_del_dia': horas_del_dia,
        'dias_semana': range(5) # Pasamos un rango de 0 a 4
    }
    return render(request, 'gestion_academica/gestion_horarios.html', context)

@login_required
def seleccionar_curso_para_lecciones(request):
    """
    Muestra al docente una lista de sus cursos para que elija
    de cuál quiere ver el historial de lecciones.
    """
    try:
        docente = request.user.docente
        periodo_activo = PeriodoAcademico.objects.filter(institucion=docente.institucion, activo=True).first()
        if periodo_activo:
            cursos = Curso.objects.filter(docentes_asignados=docente, periodo_academico=periodo_activo)
        else:
            cursos = Curso.objects.none()
    except AttributeError:
        messages.error(request, "Acceso denegado.")
        return redirect('gestion_academica:inicio_academico')

    context = {
        'titulo_pagina': "Seleccionar Curso para Ver Lecciones",
        'cursos': cursos
    }
    return render(request, 'gestion_academica/seleccionar_curso_lecciones.html', context)


@login_required
def lista_lecciones_diarias(request, curso_pk):
    """
    Muestra todas las lecciones diarias registradas para un curso específico.
    """
    curso = get_object_or_404(Curso, pk=curso_pk)
    # Validamos que el docente que solicita tenga permiso sobre este curso
    if not curso.docentes_asignados.filter(pk=request.user.docente.pk).exists():
        messages.error(request, "No tienes permiso para ver las lecciones de este curso.")
        return redirect('gestion_academica:seleccionar_curso_para_lecciones')

    lecciones = LeccionDiaria.objects.filter(curso=curso).order_by('fecha')

    context = {
        'titulo_pagina': f"Historial de Lecciones para {curso}",
        'curso': curso,
        'lecciones': lecciones
    }
    return render(request, 'gestion_academica/lista_lecciones_diarias.html', context)    


@login_required
def detalle_leccion(request, leccion_pk):
    """
    Muestra el detalle de una lección diaria con lógica de permisos y depuración.
    """
    leccion = get_object_or_404(LeccionDiaria, pk=leccion_pk)
    curso = leccion.curso
    user = request.user

    # --- DEPURACIÓN ---
    print("======== DETALLE LECCIÓN DEBUG ========")
    print("Usuario:", user.username)
    print("Es superusuario:", user.is_superuser)
    print("Rol:", getattr(user, 'rol', 'No definido'))
    print("Curso:", curso)
    print("Curso.grado:", curso.grado)

    if hasattr(user, 'estudiante'):
        print("Usuario tiene perfil estudiante.")
        print("Estudiante.grado_actual:", user.estudiante.grado_actual)
    else:
        print("Usuario NO tiene perfil estudiante.")

    if hasattr(user, 'docente'):
        print("Usuario tiene perfil docente.")
    else:
        print("Usuario NO tiene perfil docente.")

    # --- LÓGICA DE PERMISOS ---
    tiene_permiso = False

    if user.is_superuser:
        tiene_permiso = True
        print("Permiso concedido: Superusuario.")
    elif getattr(user, 'rol', None) == 'docente':
        tiene_permiso = True
        print("Permiso concedido: Rol docente.")
    elif getattr(user, 'rol', None) == 'estudiante' and hasattr(user, 'estudiante'):
        if user.estudiante.grado_actual == curso.grado:
            tiene_permiso = True
            print("Permiso concedido: Estudiante del mismo grado.")
        else:
            print("Permiso denegado: Estudiante de otro grado.")
    else:
        print("Permiso denegado: No cumple ninguna condición.")

    if not tiene_permiso:
        messages.error(request, "No tienes permiso para acceder a esta lección.")
        print("Redirigiendo a 'inicio_academico'")
        return redirect('gestion_academica:inicio_academico')

    # --- FORMULARIO ---
    if getattr(user, 'rol', None) == 'docente' and request.method == 'POST':
        form = LeccionDiariaIaForm(request.POST, request.FILES, instance=leccion)
        if form.is_valid():
            form.save()
            messages.success(request, "Lección actualizada exitosamente.")
            return redirect('gestion_academica:lista_lecciones_diarias', curso_pk=curso.pk)
    else:
        form = LeccionDiariaIaForm(instance=leccion)

    docente = getattr(leccion, 'docente', None)

    context = {
        'titulo_pagina': "Detalle de Lección",
        'form': form,
        'leccion': leccion,
        'curso': curso,
        'docente': docente,
    }
    return render(request, 'gestion_academica/detalle_leccion_ia.html', context)


@login_required
@permission_required('gestion_academica.view_usuario', raise_exception=True) # Permiso para ver usuarios
def lista_usuarios_view(request):
    """
    Muestra una lista centralizada de todos los usuarios de la institución,
    con filtros por rol y un buscador.
    """
    institucion = request.user.institucion_asociada
    
    # Obtenemos los parámetros de filtrado y búsqueda desde la URL
    rol_filtrado = request.GET.get('rol', '')
    query = request.GET.get('q', '')

    # Empezamos con todos los usuarios de la institución
    usuarios_list = Usuario.objects.filter(institucion_asociada=institucion)

    # Aplicamos el filtro por rol si se ha seleccionado uno
    if rol_filtrado:
        usuarios_list = usuarios_list.filter(rol=rol_filtrado)

    # Aplicamos el filtro de búsqueda si se ha escrito algo
    if query:
        usuarios_list = usuarios_list.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(username__icontains=query) |
            Q(email__icontains=query)
        )

    context = {
        'titulo_pagina': "Gestión de Usuarios",
        'usuarios': usuarios_list.order_by('last_name', 'first_name'),
        'roles': Usuario.ROLES, # Pasamos la lista de roles para los botones de filtro
        'rol_actual': rol_filtrado,
        'query_actual': query,
    }
    return render(request, 'gestion_academica/lista_usuarios.html', context)


@login_required
@permission_required('gestion_academica.change_usuario', raise_exception=True)
def editar_usuario_view(request, user_pk):
    """
    Permite a un administrador editar los detalles y la contraseña de un usuario.
    VERSIÓN MEJORADA: También obtiene el perfil del estudiante si aplica.
    """
    user_to_edit = get_object_or_404(Usuario, pk=user_pk)
    
    # --- INICIO DE LA LÓGICA AÑADIDA ---
    # Buscamos el perfil de estudiante solo si el rol del usuario es 'estudiante'
    estudiante_profile = None
    if user_to_edit.rol == 'estudiante':
        try:
            # La relación OneToOne desde Usuario a Estudiante es 'estudiante'
            estudiante_profile = user_to_edit.estudiante 
        except Estudiante.DoesNotExist:
            # En caso de que haya alguna inconsistencia de datos
            estudiante_profile = None
    # --- FIN DE LA LÓGICA AÑADIDA ---
    
    if request.method == 'POST':
        # Verificamos qué formulario se envió
        if 'update_details' in request.POST:
            user_form = UserEditForm(request.POST, instance=user_to_edit)
            password_form = UserPasswordChangeForm()
            if user_form.is_valid():
                user_form.save()
                messages.success(request, f"Los datos de '{user_to_edit.get_full_name()}' han sido actualizados.")
                return redirect('gestion_academica:lista_usuarios')
        
        elif 'change_password' in request.POST:
            password_form = UserPasswordChangeForm(request.POST)
            user_form = UserEditForm(instance=user_to_edit)
            if password_form.is_valid():
                new_password = password_form.cleaned_data['new_password1']
                user_to_edit.set_password(new_password)
                user_to_edit.save()
                messages.success(request, f"La contraseña de '{user_to_edit.get_full_name()}' ha sido cambiada exitosamente.")
                return redirect('gestion_academica:lista_usuarios')
    else:
        user_form = UserEditForm(instance=user_to_edit)
        password_form = UserPasswordChangeForm()

    context = {
        'titulo_pagina': f"Editando Usuario: {user_to_edit.get_full_name()}",
        'user_to_edit': user_to_edit,
        'user_form': user_form,
        'password_form': password_form,
        'estudiante_profile': estudiante_profile, # Pasamos el perfil a la plantilla
    }
    return render(request, 'gestion_academica/editar_usuario.html', context)

@login_required
def pasar_lista_view(request, curso_pk):
    """
    Muestra la lista de estudiantes de un curso y permite al docente
    actualizar su estado de asistencia para la fecha actual.
    VERSIÓN CORREGIDA: Refuerza la seguridad para sistemas multi-institución.
    """
    institucion = request.user.institucion_asociada
    
    # --- INICIO DE LA CORRECCIÓN DE SEGURIDAD ---
    # 1. Filtramos el curso por la institución del usuario desde el principio.
    #    Esto previene que un usuario de una institución acceda a datos de otra.
    curso_qs = Curso.objects.filter(institucion=institucion)
    curso = get_object_or_404(curso_qs, pk=curso_pk)
    # --- FIN DE LA CORRECCIÓN ---

    hoy = timezone.now().date()
    
    # 2. La lógica de permisos ahora es una segunda capa de seguridad.
    if not (request.user.is_superuser or (hasattr(request.user, 'docente') and request.user.docente in curso.docentes_asignados.all())):
        messages.error(request, "No tienes permiso para pasar lista en este curso.")
        return redirect('gestion_academica:dashboard_docente')

    if request.method == 'POST':
        for key, value in request.POST.items():
            if key.startswith('estado_'):
                asistencia_id = int(key.split('_')[1])
                try:
                    # Nos aseguramos de que el registro de asistencia también pertenezca a la institución.
                    asistencia = RegistroAsistencia.objects.get(pk=asistencia_id, institucion=institucion)
                    if asistencia.estado != value:
                        asistencia.estado = value
                        asistencia.registrado_por = request.user
                        asistencia.save()
                except RegistroAsistencia.DoesNotExist:
                    continue
        messages.success(request, "La lista de asistencia ha sido actualizada.")
        return redirect('gestion_academica:pasar_lista', curso_pk=curso.pk)

    # 3. Aseguramos que la lista de estudiantes también esté filtrada por la institución.
    estudiantes = Estudiante.objects.filter(grado_actual=curso.grado, activo=True, institucion=institucion)
    
    asistencias_hoy = []
    for est in estudiantes:
        registro, created = RegistroAsistencia.objects.get_or_create(
            estudiante=est,
            curso=curso,
            fecha__date=hoy,
            defaults={
                'estado': 'AUSENTE',
                'institucion': curso.institucion,
                'registrado_por': request.user
            }
        )
        asistencias_hoy.append(registro)

    context = {
        'titulo_pagina': f"Pasar Lista: {curso}",
        'curso': curso,
        'asistencias': asistencias_hoy,
        'fecha': hoy,
        'estados': RegistroAsistencia.ESTADOS
    }
    return render(request, 'gestion_academica/pasar_lista.html', context)    


class MaterialRefuerzoView(LoginRequiredMixin, View):
    template_name = 'gestion_academica/material_refuerzo.html'

    def get(self, request, actividad_pk):
        try:
            estudiante = request.user.estudiante
        except Estudiante.DoesNotExist:
            raise PermissionDenied

        actividad = get_object_or_404(ActividadCalificable, pk=actividad_pk, institucion=estudiante.institucion)
        
        # Lógica de búsqueda (similar a la señal)
        recursos_sugeridos = ArchivoPlanAcademico.objects.filter(
            institucion=estudiante.institucion,
            temas_relacionados__icontains=actividad.titulo
        ).distinct()

        context = {
            'titulo_pagina': f"Material de Refuerzo para {actividad.titulo}",
            'actividad': actividad,
            'recursos': recursos_sugeridos
        }
        return render(request, self.template_name, context)

class HistorialEntregasView(LoginRequiredMixin, View):
    template_name = 'gestion_academica/historial_entregas.html'

    def get(self, request, *args, **kwargs):
        docente = request.user.docente
        institucion = request.user.institucion_asociada
        periodo_activo = PeriodoAcademico.objects.filter(activo=True, institucion=institucion).first()

        todas_las_entregas = EntregaDeber.objects.none()
        todos_los_intentos = IntentoCuestionario.objects.none()

        if periodo_activo:
            cursos_del_docente = Curso.objects.filter(docentes_asignados=docente, periodo_academico=periodo_activo)
            
            # 1. Obtenemos TODAS las entregas de deberes de los cursos del docente
            todas_las_entregas = EntregaDeber.objects.filter(
                deber__curso__in=cursos_del_docente,
            ).select_related('deber__curso', 'estudiante__usuario').order_by('-fecha_entrega_real')

            # 2. Obtenemos TODOS los intentos de cuestionario FINALIZADOS
            todos_los_intentos = IntentoCuestionario.objects.filter(
                cuestionario__actividad_calificable__curso__in=cursos_del_docente,
                estado='FINALIZADO',
            ).select_related(
                'estudiante__usuario', 
                'cuestionario__actividad_calificable__curso'
            ).distinct().order_by('-fecha_fin')

        context = {
            'titulo_pagina': 'Historial de Entregas y Evaluaciones',
            'entregas': todas_las_entregas,
            'intentos': todos_los_intentos
        }
        
        return render(request, self.template_name, context)

class SincronizarPermisosView(LoginRequiredMixin, View):
    template_name = 'gestion_academica/sincronizar_permisos.html'

    def get(self, request, *args, **kwargs):
        # El método GET no necesita cambios, ya funciona bien.
        if not request.user.is_staff:
            raise PermissionDenied

        grupos_gestionables = Group.objects.all().order_by('name')
        
        context = {
            'titulo_pagina': 'Sincronización de Permisos por Rol',
            'grupos': grupos_gestionables
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
            
        grupo_id = request.POST.get('grupo_id')
        if not grupo_id:
            messages.error(request, "No se especificó un grupo para sincronizar.")
            return redirect('gestion_academica:sincronizar_permisos')

        try:
            grupo = Group.objects.get(pk=grupo_id)
            institucion = request.user.institucion_asociada

            # --- INICIO DE LA CORRECCIÓN CLAVE ---
            # 1. Usamos un diccionario para mapear de forma segura el nombre del grupo al rol.
            #    ¡Ajusta las claves si tus grupos se llaman diferente!
            rol_map = {
                'estudiantes': 'estudiante',
                'docentes': 'docente',
                'coordinadores': 'coordinador',
                'administradores': 'administrador',
                'familiares': 'familiar',
                # Añade más mapeos si tienes otros grupos
            }
            
            # 2. Buscamos el rol correspondiente en nuestro mapa.
            rol_a_buscar = rol_map.get(grupo.name.lower())

            if not rol_a_buscar:
                messages.error(request, f"No se pudo determinar el rol para el grupo '{grupo.name}'. Asegúrate de que esté configurado en la vista.")
                return redirect('gestion_academica:sincronizar_permisos')
            
            # 3. Buscamos a todos los usuarios con ese rol que aún no están en el grupo.
            usuarios_a_sincronizar = Usuario.objects.filter(
                institucion_asociada=institucion,
                rol=rol_a_buscar
            ).exclude(groups=grupo)

            # 4. Añadimos los usuarios encontrados al grupo.
            if usuarios_a_sincronizar.exists():
                # El método .add() puede recibir múltiples objetos a la vez.
                grupo.user_set.add(*usuarios_a_sincronizar)
                messages.success(request, f"¡Sincronización completa! Se añadieron {usuarios_a_sincronizar.count()} usuario(s) al grupo '{grupo.name}'.")
            else:
                messages.info(request, f"No se encontraron nuevos usuarios con el rol '{rol_a_buscar}' para añadir al grupo '{grupo.name}'. Ya están todos sincronizados.")
            
            # --- FIN DE LA CORRECCIÓN CLAVE ---

        except Group.DoesNotExist:
            messages.error(request, "El grupo especificado no existe.")
        except Exception as e:
            messages.error(request, f"Ocurrió un error inesperado: {e}")
        
        return redirect('gestion_academica:sincronizar_permisos')      


class MarcarNotificacionLeidaView(LoginRequiredMixin, APIView):
    
    def post(self, request, *args, **kwargs):
        notificacion_id = request.data.get('notificacion_id')

        if not notificacion_id:
            return JsonResponse({'status': 'error', 'message': 'Falta el ID de la notificación.'}, status=400)

        try:
            # Buscamos la notificación, asegurándonos de que pertenezca al usuario logueado por seguridad.
            notificacion = Notificacion.objects.get(pk=notificacion_id, destinatario=request.user)
            
            # Actualizamos el estado si no ha sido leída.
            if not notificacion.leido:
                notificacion.leido = True
                notificacion.fecha_leido = timezone.now()
                notificacion.save()

            return JsonResponse({'status': 'success'})

        except Notificacion.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Notificación no encontrada o no tienes permiso.'}, status=404)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


class EjecutarAnalisisComportamientoView(LoginRequiredMixin, APIView): # <-- Cambiado a APIView
    def post(self, request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied

        # Llamamos a la tarea y OBTENEMOS SU ID
        task = analizar_comportamiento_task.delay(request.user.id)
        
        # Devolvemos el ID de la tarea al frontend
        return JsonResponse({'task_id': task.id}, status=202)


# Añade esta nueva vista completa
class AnalisisStatusView(LoginRequiredMixin, APIView):
    def get(self, request, *args, **kwargs):
        task_id = request.GET.get('task_id')
        if not task_id:
            return JsonResponse({'status': 'error', 'message': 'No se proporcionó un ID de tarea.'}, status=400)

        task_result = AsyncResult(task_id)

        return JsonResponse({
            'task_id': task_id,
            'status': task_result.status,
            'result': task_result.result if task_result.ready() else None
        })


class GenerarResumenEstudianteIAView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, estudiante_pk, periodo_pk):
        estudiante = get_object_or_404(Estudiante, pk=estudiante_pk)
        periodo = get_object_or_404(PeriodoAcademico, pk=periodo_pk)

        # --- INICIO DE LA CORRECCIÓN DE PERMISOS ---
        user = request.user
        tiene_permiso = False

        # Un superusuario o un staff de la misma institución siempre tienen permiso
        if user.is_superuser or (user.is_staff and user.institucion_asociada == estudiante.institucion):
            tiene_permiso = True
        
        # Un docente tiene permiso si es el director de ese grupo en ese periodo
        elif hasattr(user, 'docente'):
            if DirectorCurso.objects.filter(
                docente=user.docente, 
                grado=estudiante.grado_actual, 
                periodo_academico=periodo
            ).exists():
                tiene_permiso = True

        if not tiene_permiso:
            return Response({'error': 'No tienes permiso para generar un resumen para este estudiante.'}, status=403)
        # --- FIN DE LA CORRECCIÓN DE PERMISOS ---
            
        estudiante = get_object_or_404(Estudiante, pk=estudiante_pk, institucion=request.user.institucion_asociada)
        periodo = get_object_or_404(PeriodoAcademico, pk=periodo_pk, institucion=request.user.institucion_asociada)
        
        # 2. Recopilación de Datos del Estudiante
        
        # a) Rendimiento Académico
        cursos = Curso.objects.filter(grado=estudiante.grado_actual, periodo_academico=periodo).select_related('materia')
        notas_texto = ""
        materias_rendimiento_bajo = []
        materias_rendimiento_alto = []
        nota_minima = estudiante.institucion.nota_minima_aprobacion or Decimal('3.0')

        for curso in cursos:
            estado = calcular_estado_academico_curso(curso, estudiante)
            nota_final = estado.get('nota_final_ponderada')
            if nota_final is not None:
                notas_texto += f"- {curso.materia.nombre_materia}: {nota_final:.2f}\n"
                if nota_final < nota_minima:
                    materias_rendimiento_bajo.append(curso.materia.nombre_materia)
                elif nota_final >= 4.5:
                    materias_rendimiento_alto.append(curso.materia.nombre_materia)

        # b) Asistencia
        inasistencias = RegistroAsistencia.objects.filter(
            estudiante=estudiante, curso__periodo_academico=periodo, estado='AUSENTE'
        ).count()

        # c) Comportamiento (Observador)
        anotaciones = AnotacionObservador.objects.filter(
            estudiante=estudiante, fecha_hora__range=(periodo.fecha_inicio, periodo.fecha_fin)
        ).order_by('-fecha_hora')[:5]
        anotaciones_texto = "\n".join([f"- {a.descripcion}" for a in anotaciones])

        # 3. Construcción del Prompt para la IA
        prompt = f"""
        Actúa como un experimentado director de grupo llamado HALU. Estás redactando una observación para el boletín de un estudiante.
        Sé profesional, constructivo y empático. Usa un lenguaje formal pero cercano.

        Aquí tienes los datos del estudiante '{estudiante.usuario.get_full_name()}' para el '{periodo.nombre}':

        Rendimiento Académico (Notas finales por materia):
        {notas_texto if notas_texto else "No hay calificaciones registradas."}

        Materias con rendimiento destacado: {', '.join(materias_rendimiento_alto) or 'Ninguna'}.
        Materias con rendimiento bajo (por debajo de {nota_minima}): {', '.join(materias_rendimiento_bajo) or 'Ninguna'}.

        Registro de Asistencia:
        - Total de inasistencias en el periodo: {inasistencias}.

        Observaciones de Comportamiento Recientes:
        {anotaciones_texto if anotaciones_texto else "No hay anotaciones recientes."}

        Basado en TODOS estos datos, redacta un párrafo de resumen (máximo 120 palabras) que describa de forma integral el desempeño del estudiante. Destaca sus fortalezas, menciona sus áreas de mejora de forma constructiva y, si aplica, conecta su comportamiento o asistencia con su rendimiento académico. Finaliza con una nota de motivación.
        """

        try:
            # Llamada a la IA y respuesta
            api_key = institucion_google_api_key(estudiante.institucion)
            if not api_key:
                return Response(
                    {'status': 'error', 'message': 'La institución no tiene configurada la API key de Google (Gemini).'},
                    status=500,
                )
            genai.configure(api_key=api_key)
            
            # --- CORRECCIÓN: De GenerativaModel a GenerativeModel ---
            model = genai.GenerativeModel('gemini-2.5-flash')
            # --- FIN DE LA CORRECCIÓN ---
            
            response = model.generate_content(prompt) # El prompt se construye con la lógica anterior
            
            return Response({'status': 'success', 'resumen': response.text})
        except Exception as e:
            return Response({'status': 'error', 'message': f"Error al contactar la IA: {e}"}, status=500)


@login_required
@require_POST
def api_sugerir_nombre_idioma(request):
    """
    Recibe el nombre de una materia en español y el idioma destino,
    devuelve el nombre sugerido por Gemini en ese idioma.
    Usado por el botón '✨ Sugerir con IA' en el formulario de materias.
    """
    try:
        data = json.loads(request.body)
        nombre_es = data.get('nombre_es', '').strip()
        idioma = data.get('idioma', 'Inglés').strip()
        if not nombre_es:
            return JsonResponse({'error': 'Nombre vacío.'}, status=400)

        institucion = getattr(request.user, 'institucion_asociada', None)
        if not institucion:
            return JsonResponse({'error': 'Sin institución asociada.'}, status=403)

        api_key = institucion_google_api_key(institucion)
        if not api_key:
            return JsonResponse({'error': 'La institución no tiene configurada la API key de Google (Gemini).'}, status=500)

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')

        prompt = (
            f"Eres un experto en nomenclatura educativa. "
            f"Traduce el nombre de esta materia escolar al {idioma}, "
            f"siguiendo la convención usada en colegios bilingües de Colombia. "
            f"Responde ÚNICAMENTE con el nombre traducido, sin explicaciones ni puntuación extra.\n\n"
            f"Materia en español: {nombre_es}"
        )
        response = model.generate_content(prompt)
        nombre_sugerido = response.text.strip().strip('"').strip("'")
        return JsonResponse({'nombre_sugerido': nombre_sugerido})

    except Exception as e:
        return JsonResponse({'error': f'Error al contactar la IA: {e}'}, status=500)


@login_required
@require_POST
def api_sugerir_nombres_idioma_masivo(request):
    """
    Recibe una lista de PKs de materias sin nombre en idioma secundario
    y devuelve sugerencias para todas en una sola llamada a Gemini.
    Usado por el botón 'Sugerir para todas' en la lista de materias.
    """
    try:
        data = json.loads(request.body)
        pks = data.get('pks', [])
        idioma = data.get('idioma', 'Inglés').strip()

        institucion = getattr(request.user, 'institucion_asociada', None)
        if not institucion:
            return JsonResponse({'error': 'Sin institución asociada.'}, status=403)

        materias = Materia.objects.filter(pk__in=pks, institucion=institucion)
        if not materias.exists():
            return JsonResponse({'error': 'No se encontraron materias.'}, status=400)

        api_key = institucion_google_api_key(institucion)
        if not api_key:
            return JsonResponse({'error': 'La institución no tiene configurada la API key de Google (Gemini).'}, status=500)

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')

        lista = '\n'.join([f'- {m.pk}: {m.nombre_materia}' for m in materias])
        prompt = (
            f"Eres un experto en nomenclatura educativa de colegios bilingües en Colombia.\n"
            f"Traduce cada nombre de materia al {idioma}, usando la convención oficial de colegios bilingües.\n"
            f"Responde ÚNICAMENTE en formato JSON: {{\"<pk>\": \"<nombre traducido>\", ...}}. Sin texto adicional.\n\n"
            f"Materias:\n{lista}"
        )
        response = model.generate_content(prompt)
        texto = response.text.strip()
        # Limpiar posibles bloques de código markdown
        if texto.startswith('```'):
            texto = texto.split('```')[1]
            if texto.startswith('json'):
                texto = texto[4:]
        sugerencias = json.loads(texto.strip())
        return JsonResponse({'sugerencias': sugerencias})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'La IA devolvió una respuesta inesperada. Intenta de nuevo.'}, status=500)
    except Exception as e:
        return JsonResponse({'error': f'Error al contactar la IA: {e}'}, status=500)


@login_required
@require_POST
def api_guardar_nombres_idioma_masivo(request):
    """Guarda los nombres en idioma secundario sugeridos por IA para múltiples materias."""
    try:
        data = json.loads(request.body)
        sugerencias = data.get('sugerencias', {})  # {pk: nombre_sugerido}
        institucion = getattr(request.user, 'institucion_asociada', None)
        if not institucion:
            return JsonResponse({'error': 'Sin institución asociada.'}, status=403)

        actualizadas = 0
        for pk_str, nombre in sugerencias.items():
            try:
                materia = Materia.objects.get(pk=int(pk_str), institucion=institucion)
                if nombre and not materia.nombre_idioma_secundario:
                    materia.nombre_idioma_secundario = nombre.strip()
                    materia.save(update_fields=['nombre_idioma_secundario'])
                    actualizadas += 1
            except (Materia.DoesNotExist, ValueError):
                continue

        return JsonResponse({'actualizadas': actualizadas})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


class OptimizadorHorariosView(LoginRequiredMixin, View):
    template_name = 'gestion_academica/optimizador_horarios.html'

    def get(self, request, *args, **kwargs):
        # El método GET se mantiene exactamente igual
        if not request.user.is_staff or request.user.rol not in ['coordinador', 'administrador']:
            raise PermissionDenied("No tienes permiso para acceder a esta herramienta.")

        institucion = request.user.institucion_asociada
        periodo_activo = PeriodoAcademico.objects.filter(institucion=institucion, activo=True).first()
        
        grados = Grado.objects.filter(institucion=institucion).order_by('orden')
        
        context = {
            'titulo_pagina': 'Optimizador de Horarios con IA',
            'periodo_activo': periodo_activo,
            'grados': grados,
            'grado_seleccionado': None,
            'docentes_disponibles': [],
            'cursos_a_programar': [],
            'aulas_disponibles': []
        }

        grado_id = request.GET.get('grado_id')
        if grado_id:
            grado_seleccionado = get_object_or_404(Grado, pk=grado_id, institucion=institucion)
            context['grado_seleccionado'] = grado_seleccionado
            
            if periodo_activo:
                cursos_del_grado = Curso.objects.filter(periodo_academico=periodo_activo, grado=grado_seleccionado)
                context['cursos_a_programar'] = cursos_del_grado.select_related('materia', 'grado').order_by('materia__nombre_materia')
                docentes_ids = cursos_del_grado.values_list('docentes_asignados', flat=True)
                context['docentes_disponibles'] = Docente.objects.filter(pk__in=set(docentes_ids)).prefetch_related('disponibilidades').order_by('usuario__last_name')
                context['aulas_disponibles'] = Aula.objects.filter(institucion=institucion).order_by('nombre')

        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        periodo_activo = PeriodoAcademico.objects.filter(institucion=request.user.institucion_asociada, activo=True).first()
        
        # --- INICIO DE LA CORRECCIÓN ---
        # Leemos el cuerpo de la petición y lo decodificamos como JSON
        try:
            data = json.loads(request.body)
            grado_pk = data.get('grado_pk')
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Cuerpo de la petición inválido.'}, status=400)
        # --- FIN DE LA CORRECCIÓN ---

        if not periodo_activo or not grado_pk:
            return JsonResponse({'status': 'error', 'message': 'Falta el periodo activo o el grado.'}, status=400)

        task = generar_propuesta_horario_task.delay(
            periodo_pk=periodo_activo.pk, 
            institucion_id=request.user.institucion_asociada.pk,
            grado_pk=grado_pk
        )
        
        return JsonResponse({'task_id': task.id}, status=202)
               

class GuardarHorarioView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied

        try:
            horario_data = request.data.get('horario')
            periodo_pk = request.data.get('periodo_pk')
            # --- NUEVO: Obtenemos el grado para un borrado más seguro ---
            grado_pk = request.data.get('grado_pk')

            if not all([horario_data, periodo_pk, grado_pk]):
                return Response({'status': 'error', 'message': 'Faltan datos (horario, periodo o grado).'}, status=400)

            with transaction.atomic():
                # Borramos solo los bloques del grado y periodo específicos
                cursos_del_grado = Curso.objects.filter(periodo_academico_id=periodo_pk, grado_id=grado_pk)
                BloqueHorario.objects.filter(curso__in=cursos_del_grado).delete()

                # --- INICIO DE LA CORRECCIÓN CLAVE ---
                for evento in horario_data:
                    # Creamos los nuevos bloques SIN el campo 'docente'
                    BloqueHorario.objects.create(
                        curso=get_object_or_404(Curso, pk=evento['curso_id']),
                        aula=get_object_or_404(Aula, pk=evento['aula_id']),
                        dia_semana=int(evento['dia_semana']),
                        hora_inicio=evento['hora_inicio'],
                        hora_fin=evento['hora_fin'],
                        institucion=request.user.institucion_asociada
                        # El campo 'docente' se elimina de aquí
                    )
                # --- FIN DE LA CORRECCIÓN CLAVE ---
            
            return Response({'status': 'success', 'message': '¡Horario guardado y publicado exitosamente!'})

        except Exception as e:
            return Response({'status': 'error', 'message': str(e)}, status=500)     


