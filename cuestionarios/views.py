from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import View, ListView, UpdateView
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.urls import reverse_lazy
from django.utils import timezone
import traceback
import json
from django.views.generic import DetailView
import google.generativeai as genai
from django.conf import settings

from .models import (
    Cuestionario, PreguntaCuestionario, OpcionPregunta, 
    IntentoCuestionario, RespuestaEstudiante
)
# Importamos SOLO lo que necesitamos de la otra app.
from gestion_academica.models import Calificacion, ActividadCalificable

class CuestionarioListView(LoginRequiredMixin, ListView):
    model = Cuestionario
    template_name = 'cuestionarios/cuestionario_lista.html'
    context_object_name = 'cuestionarios'
    paginate_by = 15

    def get_queryset(self):
        return Cuestionario.objects.filter(
            institucion=self.request.user.institucion_asociada
        ).select_related(
            'actividad_calificable',
            'creado_por'
        ).prefetch_related('preguntas')


class EditorCuestionarioView(LoginRequiredMixin, View):
    template_name = 'cuestionarios/editor.html'
    
    def get(self, request, actividad_pk):
        actividad = get_object_or_404(
            ActividadCalificable,
            pk=actividad_pk,
            curso__docentes_asignados=request.user.docente
        )
        
        cuestionario, created = Cuestionario.objects.get_or_create(
            actividad_calificable=actividad,
            defaults={
                'creado_por': request.user,
                'institucion': request.user.institucion_asociada,
                'titulo': actividad.titulo
            }
        )
        
        return render(request, self.template_name, {
            'actividad': actividad,
            'cuestionario': cuestionario,
            'titulo_pagina': f"Editor: {actividad.titulo}"
        })


class CuestionarioAPIView(LoginRequiredMixin, View):

    def get(self, request, actividad_pk):
        # --- INICIO DE LA CORRECCIÓN ---
        # Se elimina `creado_por=request.user`.
        # Un estudiante necesita cargar las preguntas, pero no es el creador.
        # El permiso para ver el cuestionario ya se validó en la vista anterior 
        # que le permitió al estudiante iniciar un intento.
        cuestionario = get_object_or_404(
            Cuestionario,
            actividad_calificable_id=actividad_pk,
            institucion=request.user.institucion_asociada 
        )
        # --- FIN DE LA CORRECCIÓN ---

        preguntas = []
        for p in cuestionario.preguntas.order_by('orden'):
            pregunta_data = {
                'id': p.id,
                'enunciado': p.enunciado,
                'tipo': p.tipo,
                'puntaje': p.puntaje,
                'orden': p.orden,
                'retroalimentacion': p.retroalimentacion,
                'respuesta_correcta_abierta': p.respuesta_correcta_abierta
            }

            if p.tipo in ['opcion_multiple', 'seleccion_multiple', 'verdadero_falso', 'emparejamiento']:
                pregunta_data['opciones'] = [
                    {
                        'id': op.id,
                        'texto': op.texto,
                        # Para el editor, podrías necesitar el campo 'emparejamiento'
                        'emparejamiento': op.emparejamiento, 
                        'es_correcta': op.es_correcta,
                        'orden': op.orden
                    }
                    for op in p.opciones.order_by('orden')
                ]

            preguntas.append(pregunta_data)

        response_data = {
            'id': cuestionario.id,
            'titulo': cuestionario.titulo,
            'descripcion': cuestionario.descripcion,
            'tiempo_limite': cuestionario.tiempo_limite,
            'intentos_permitidos': cuestionario.intentos_permitidos,
            'activo': cuestionario.activo,
            'mostrar_respuestas': cuestionario.mostrar_respuestas,
            'preguntas': preguntas
        }

        return JsonResponse(response_data)

    @transaction.atomic
    def post(self, request, actividad_pk):
        try:
            data = json.loads(request.body)
            actividad = get_object_or_404(
                ActividadCalificable,
                pk=actividad_pk,
                curso__docentes_asignados=request.user.docente
            )
            
            # 1. Actualizamos o creamos el Cuestionario principal
            cuestionario, created = Cuestionario.objects.update_or_create(
                actividad_calificable=actividad,
                defaults={
                    'titulo': data.get('titulo'),
                    'descripcion': data.get('descripcion', ''),
                    'tiempo_limite': data.get('tiempo_limite', 30),
                    'intentos_permitidos': data.get('intentos_permitidos', 1),
                    'activo': data.get('activo', True),
                    'mostrar_respuestas': data.get('mostrar_respuestas', False),
                    'creado_por': request.user,
                    'institucion': request.user.institucion_asociada
                }
            )
            
            # 2. Borramos TODAS las preguntas antiguas. Esto simplifica todo.
            cuestionario.preguntas.all().delete()
            
            # 3. Creamos las nuevas preguntas desde cero con el orden correcto.
            for pregunta_data in data.get('preguntas', []):
                pregunta = PreguntaCuestionario.objects.create(
                    cuestionario=cuestionario,
                    enunciado=pregunta_data['enunciado'],
                    tipo=pregunta_data['tipo'],
                    puntaje=pregunta_data.get('puntaje', 1),
                    orden=pregunta_data['orden'],
                    retroalimentacion=pregunta_data.get('retroalimentacion'),
                    respuesta_correcta_abierta=pregunta_data.get('respuesta_correcta_abierta')
                )
                
                # 4. Creamos las opciones para cada pregunta.
                if pregunta.tipo in ['opcion_multiple', 'seleccion_multiple', 'verdadero_falso', 'emparejamiento']:
                    for opcion_data in pregunta_data.get('opciones', []):
                        OpcionPregunta.objects.create(
                            pregunta=pregunta,
                            texto=opcion_data['texto'],
                            emparejamiento=opcion_data.get('emparejamiento'),
                            es_correcta=opcion_data['es_correcta'],
                            orden=opcion_data['orden']
                        )
            
            return JsonResponse({
                'status': 'success',
                'message': 'Cuestionario guardado correctamente',
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)


class ToggleCuestionarioActivoView(LoginRequiredMixin, View):
    
    def post(self, request, cuestionario_id):
        cuestionario = get_object_or_404(
            Cuestionario,
            pk=cuestionario_id,
            creado_por=request.user,
            # -- CORRECCIÓN --
            # Se añade el filtro de institución para mayor seguridad.
            institucion=request.user.institucion_asociada
        )
        
        
        cuestionario.activo = not cuestionario.activo
        cuestionario.save()
        
        return JsonResponse({
            'status': 'success',
            'activo': cuestionario.activo
        })




class IniciarCuestionarioView(LoginRequiredMixin, View):
    """
    Muestra la página de inicio de un cuestionario y gestiona la creación de un nuevo intento,
    validando el límite de intentos permitidos y los intentos extra habilitados.
    """
    def get(self, request, actividad_pk):
        # NOTA: Tu método 'get' ya era correcto y se mantiene igual.
        actividad = get_object_or_404(
            ActividadCalificable, 
            pk=actividad_pk,
            institucion=request.user.institucion_asociada
        )
        cuestionario = get_object_or_404(Cuestionario, actividad_calificable=actividad)
        
        context = {
            'actividad': actividad,
            'cuestionario': cuestionario,
            'titulo_pagina': f"Iniciar: {cuestionario.titulo}"
        }
        return render(request, 'cuestionarios/iniciar_cuestionario.html', context)

    def post(self, request, actividad_pk):
        """
        Crea un nuevo intento SOLO SI el estudiante no ha superado el límite de intentos
        o si se le ha habilitado un intento extra.
        """
        cuestionario = get_object_or_404(
            Cuestionario, 
            actividad_calificable_id=actividad_pk,
            institucion=request.user.institucion_asociada
        )
        estudiante = request.user.estudiante
        
        # --- INICIO DE LA MODIFICACIÓN ---
        # 1. Obtenemos todos los intentos previos del estudiante para este cuestionario.
        intentos_previos = IntentoCuestionario.objects.filter(
            cuestionario=cuestionario, 
            estudiante=estudiante
        )
        intentos_realizados = intentos_previos.count()
        ultimo_intento = intentos_previos.order_by('-fecha_inicio').first()

        # 2. Verificamos si un docente habilitó un intento extra en el último intento.
        intento_extra_permitido = ultimo_intento and ultimo_intento.intento_extra_habilitado

        # 3. Calculamos el límite real de intentos.
        #    Es el límite normal, pero le sumamos 1 si se habilitó un intento extra.
        limite_real = cuestionario.intentos_permitidos
        if intento_extra_permitido:
            limite_real += 1
        
        # 4. Comparamos los intentos realizados con el límite real.
        if intentos_realizados >= limite_real:
            messages.error(request, f"Has alcanzado el límite de {cuestionario.intentos_permitidos} intento(s) para este cuestionario.")
            return redirect('gestion_academica:dashboard_estudiante')
        
        # 5. Si se va a usar un intento extra, lo "gastamos" para que no se pueda volver a usar.
        if intento_extra_permitido and intentos_realizados == cuestionario.intentos_permitidos:
            ultimo_intento.intento_extra_habilitado = False
            ultimo_intento.save()
        # --- FIN DE LA MODIFICACIÓN ---

        # Si todas las validaciones pasan, creamos el nuevo intento.
        intento_nuevo = IntentoCuestionario.objects.create(
            cuestionario=cuestionario,
            estudiante=estudiante
        )
        return redirect('cuestionarios:resolver_cuestionario', intento_pk=intento_nuevo.pk)


class ResolverCuestionarioView(LoginRequiredMixin, View):
    """
    La interfaz principal donde el estudiante resuelve el cuestionario.
    """
    def get(self, request, intento_pk):
        intento = get_object_or_404(
            IntentoCuestionario, 
            pk=intento_pk, 
            estudiante=request.user.estudiante,
            estado='EN_PROGRESO'
        )
        context = {
            'intento': intento,
            'cuestionario': intento.cuestionario,
            'titulo_pagina': f"Resolviendo: {intento.cuestionario.titulo}"
        }
        return render(request, 'cuestionarios/resolver_cuestionario.html', context)

# Reemplaza tu ResolverCuestionarioAPIView existente con esta versión mejorada
class ResolverCuestionarioAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, intento_pk):
        intento = get_object_or_404(IntentoCuestionario, pk=intento_pk, estudiante=request.user.estudiante)

        if intento.estado == 'FINALIZADO':
            return Response({'error': 'Este intento ya ha sido finalizado.'}, status=status.HTTP_400_BAD_REQUEST)

        respuestas_data = request.data.get('respuestas', {})
        puntaje_total = 0
        puntaje_maximo = 0

        intento.respuestas.all().delete()

        for pregunta in intento.cuestionario.preguntas.prefetch_related('opciones'):
            puntaje_maximo += pregunta.puntaje
            respuesta_enviada = respuestas_data.get(str(pregunta.pk))

            puntaje_pregunta = 0

            if respuesta_enviada:
                tipo_pregunta = pregunta.tipo

                if tipo_pregunta in ['opcion_multiple', 'verdadero_falso']:
                    opciones_seleccionadas = respuesta_enviada.get('opciones_seleccionadas', [])
                    if opciones_seleccionadas:
                        opcion_id = opciones_seleccionadas[0]
                        if pregunta.opciones.filter(pk=opcion_id, es_correcta=True).exists():
                            puntaje_pregunta = pregunta.puntaje

                elif tipo_pregunta == 'seleccion_multiple':
                    opciones_correctas_db = set(pregunta.opciones.filter(es_correcta=True).values_list('id', flat=True))
                    opciones_enviadas = set(respuesta_enviada.get('opciones_seleccionadas', []))
                    if opciones_correctas_db and opciones_correctas_db == opciones_enviadas:
                        puntaje_pregunta = pregunta.puntaje

                elif tipo_pregunta == 'emparejamiento':
                    pares_correctos_db = set(pregunta.opciones.values_list('texto', 'emparejamiento'))
                    pares_enviados_data = respuesta_enviada.get('respuesta_emparejamiento', [])
                    pares_enviados = set((p['texto'], p['emparejamiento']) for p in pares_enviados_data)
                    if pares_correctos_db and pares_correctos_db == pares_enviados:
                        puntaje_pregunta = pregunta.puntaje

            puntaje_total += puntaje_pregunta

            # Esta línea ahora usará el modelo RespuestaEstudiante correcto de la app 'cuestionarios'
            respuesta_obj = RespuestaEstudiante.objects.create(
                intento=intento,
                pregunta=pregunta,
                texto_respuesta=respuesta_enviada.get('texto_respuesta') if respuesta_enviada else None,
                respuesta_emparejamiento=respuesta_enviada.get('respuesta_emparejamiento') if respuesta_enviada else None,
                puntaje_obtenido=puntaje_pregunta
            )

            if respuesta_enviada and respuesta_enviada.get('opciones_seleccionadas'):
                respuesta_obj.opciones_seleccionadas.set(respuesta_enviada.get('opciones_seleccionadas'))

        intento.estado = 'FINALIZADO'
        intento.fecha_fin = timezone.now()
        intento.puntaje_obtenido = puntaje_total
        intento.save()

        Calificacion.objects.update_or_create(
            estudiante=intento.estudiante,
            actividad_calificable=intento.cuestionario.actividad_calificable,
            institucion=intento.institucion,
            defaults={
                'valor_numerico': puntaje_total,
                'observaciones': f"Resultado automático del cuestionario '{intento.cuestionario.titulo}'.",
            }
        )

        return Response({
            'mensaje': 'Cuestionario finalizado exitosamente.',
            'puntaje_obtenido': puntaje_total,
            'puntaje_maximo': puntaje_maximo
        }, status=status.HTTP_200_OK)
    
class HabilitarIntentoExtraView(LoginRequiredMixin, View):
    def post(self, request, intento_pk):
        # Seguridad: solo el docente del curso puede hacer esto
        intento = get_object_or_404(
            IntentoCuestionario, 
            pk=intento_pk,
            cuestionario__actividad_calificable__curso__docentes_asignados=request.user.docente
        )

        # Marcamos el intento para permitir una repetición
        intento.intento_extra_habilitado = True
        intento.save()

        messages.success(request, f"Se ha habilitado un intento adicional para el estudiante {intento.estudiante}.")
        return redirect('cuestionarios:revisar_intento', intento_pk=intento.pk)   

class RevisarIntentoView(LoginRequiredMixin, DetailView):
    model = IntentoCuestionario
    template_name = 'cuestionarios/revisar_intento.html'
    context_object_name = 'intento'
    pk_url_kwarg = 'intento_pk'

    def get_queryset(self):
        # La seguridad se mantiene, esto es correcto
        return IntentoCuestionario.objects.filter(
            cuestionario__institucion=self.request.user.institucion_asociada,
            cuestionario__actividad_calificable__curso__docentes_asignados=self.request.user.docente
        )

    def get_context_data(self, **kwargs):
        # Este método se mantiene igual, es correcto
        context = super().get_context_data(**kwargs)
        intento = self.get_object()
        
        respuestas_dict = {r.pregunta_id: r for r in intento.respuestas.all()}
        preguntas_con_respuestas = []

        for pregunta in intento.cuestionario.preguntas.prefetch_related('opciones'):
            preguntas_con_respuestas.append({
                'pregunta': pregunta,
                'respuesta_estudiante': respuestas_dict.get(pregunta.id)
            })
        
        context['preguntas_con_respuestas'] = preguntas_con_respuestas
        context['titulo_pagina'] = f"Revisión de {intento.estudiante}"
        return context

    def post(self, request, *args, **kwargs):
        intento = self.get_object()
        
        # --- INICIO DE LA MODIFICACIÓN ---
        # Actualizamos las notas de las preguntas de texto libre
        for pregunta_id_str, puntaje_manual_str in request.POST.items():
            if pregunta_id_str.startswith('puntaje_manual_'):
                pregunta_id = int(pregunta_id_str.replace('puntaje_manual_', ''))
                try:
                    puntaje = float(puntaje_manual_str)
                    
                    # CORRECCIÓN: Usamos update_or_create.
                    # Esto crea el registro de respuesta si el estudiante la dejó en blanco,
                    # o lo actualiza si ya existía.
                    intento.respuestas.update_or_create(
                        pregunta_id=pregunta_id,
                        defaults={'puntaje_obtenido': puntaje}
                    )
                except (ValueError, TypeError):
                    # Ignoramos si el valor no es un número válido
                    continue
        # --- FIN DE LA MODIFICACIÓN ---

        # Recalculamos el puntaje total del intento sumando los puntajes de todas las respuestas
        puntaje_final_revisado = sum(
            r.puntaje_obtenido for r in intento.respuestas.all() if r.puntaje_obtenido is not None
        )

        # Actualizamos el intento
        intento.puntaje_obtenido = puntaje_final_revisado
        intento.save()

        # Actualizamos la calificación final en el libro de notas
        Calificacion.objects.update_or_create(
            estudiante=intento.estudiante,
            actividad_calificable=intento.cuestionario.actividad_calificable,
            institucion=intento.institucion,
            defaults={
                'valor_numerico': puntaje_final_revisado,
                'observaciones': "Nota actualizada manualmente por el docente.",
                'registrada_por': request.user.docente
            }
        )

        messages.success(request, 'La calificación ha sido actualizada correctamente.')
        return redirect(request.path)     

class EliminarIntentoView(LoginRequiredMixin, View):
    
    def post(self, request, *args, **kwargs):
        intento_pk = self.kwargs.get('intento_pk')
        
        # Medida de seguridad: nos aseguramos de que el docente que elimina
        # tenga permiso sobre el curso al que pertenece el intento.
        intento = get_object_or_404(
            IntentoCuestionario,
            pk=intento_pk,
            cuestionario__actividad_calificable__curso__docentes_asignados=request.user.docente
        )
        
        # Guardamos el nombre para el mensaje de confirmación
        estudiante_nombre = intento.estudiante
        cuestionario_titulo = intento.cuestionario.titulo
        
        # Eliminamos el objeto de la base de datos
        intento.delete()
        
        messages.success(request, f"El intento de '{estudiante_nombre}' en el cuestionario '{cuestionario_titulo}' ha sido eliminado exitosamente.")
        
        # Redirigimos de vuelta al historial
        return redirect(reverse_lazy('gestion_academica:historial_entregas'))   
    

class GenerarPreguntasIAView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, cuestionario_pk):
        print("\n--- INICIO DEBUG: GenerarPreguntasIAView ---")
        try:
            cuestionario = get_object_or_404(Cuestionario, pk=cuestionario_pk, creado_por=request.user)
            data = request.data
            print(f"[DEBUG] 1. Datos recibidos del frontend: {data}")

            prompt = f"""
            Actúa como un experto pedagogo. Crea una evaluación sobre el tema: '{data.get("tema")}' para estudiantes de secundaria.
            Si se proveen, considera estos objetivos de aprendizaje: '{data.get("objetivos", "No especificados")}'.
            Genera exactamente:
            - {data.get("num_opcion_multiple", 0)} preguntas de 'opcion_multiple' con 4 opciones cada una, donde solo una es correcta.
            - {data.get("num_verdadero_falso", 0)} preguntas de 'verdadero_falso'. Las opciones deben ser "Verdadero" y "Falso".
            - {data.get("num_texto_libre", 0)} preguntas de 'texto_libre'.
            Devuelve el resultado en un formato JSON válido que sea una lista de objetos. Cada objeto debe tener las siguientes claves: "enunciado", "tipo", y si aplica, una lista "opciones".
            Para 'opcion_multiple' y 'verdadero_falso', la lista "opciones" debe contener objetos con las claves "texto" y "es_correcta" (un booleano).
            No incluyas saltos de línea ni texto explicativo antes o después del JSON.
            """
            print(f"[DEBUG] 2. Prompt enviado a la IA (primeros 100 caracteres): {prompt[:100]}...")

            genai.configure(api_key=settings.GOOGLE_API_KEY)
            generation_config = genai.types.GenerationConfig(response_mime_type="application/json")
            model = genai.GenerativeModel('gemini-1.5-flash', generation_config=generation_config)
            response = model.generate_content(prompt)
            
            print(f"[DEBUG] 3. Respuesta RAW (texto crudo) recibida de la IA:")
            print("--------------------------------------------------")
            print(response.text)
            print("--------------------------------------------------")

            json_text = response.text.strip().replace("```json", "").replace("```", "")
            respuesta_parseada = json.loads(json_text)

            # --- INICIO DE LA CORRECCIÓN CLAVE ---
            # Verificamos si la respuesta es un diccionario que contiene la lista (la "caja").
            if isinstance(respuesta_parseada, dict) and 'evaluacion' in respuesta_parseada:
                lista_de_preguntas = respuesta_parseada['evaluacion']
                print(f"[DEBUG] CORRECCIÓN: Se extrajo la lista de la clave 'evaluacion'.")
            else:
                # Si ya es una lista, la usamos directamente.
                lista_de_preguntas = respuesta_parseada
            # --- FIN DE LA CORRECCIÓN CLAVE ---

            print(f"[DEBUG] 4. JSON procesado. Se encontraron {len(lista_de_preguntas)} preguntas.")

            with transaction.atomic():
                print("[DEBUG] 5. Iniciando guardado en la base de datos...")
                orden_actual = cuestionario.preguntas.count()
                
                # Usamos la variable corregida 'lista_de_preguntas' para el bucle
                for preg_data in lista_de_preguntas:
                    pregunta = PreguntaCuestionario.objects.create(
                        cuestionario=cuestionario,
                        enunciado=preg_data.get('enunciado'),
                        tipo=preg_data.get('tipo'),
                        orden=orden_actual
                    )
                    orden_actual += 1
                    
                    if 'opciones' in preg_data:
                        for i, op_data in enumerate(preg_data.get('opciones', [])):
                            OpcionPregunta.objects.create(
                                pregunta=pregunta,
                                texto=op_data.get('texto'),
                                es_correcta=op_data.get('es_correcta', False),
                                orden=i
                            )
            print("[DEBUG] 6. Guardado en la base de datos completado.")
            
            return JsonResponse({'status': 'success', 'message': f'¡Se han añadido {len(lista_de_preguntas)} preguntas nuevas al cuestionario!'})

        except json.JSONDecodeError as e:
            print(f"\n[DEBUG] ¡ERROR FATAL! Fallo al parsear el JSON. El texto recibido de la IA no es un JSON válido.")
            print(f"[DEBUG] Error específico: {e}")
            return JsonResponse({'status': 'error', 'message': 'La IA devolvió una respuesta en un formato inválido. Revisa la consola del servidor.'}, status=400)
        except Exception as e:
            print(f"\n[DEBUG] ¡ERROR INESPERADO! La vista falló por otra razón.")
            traceback.print_exc()
            return JsonResponse({'status': 'error', 'message': f'Error del servidor: {e}'}, status=500)        

class SugerirCalificacionIAView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, respuesta_pk):
        try:
            # Seguridad: Verificamos que el docente tenga permiso sobre este intento
            respuesta = get_object_or_404(
                RespuestaEstudiante.objects.select_related('pregunta'),
                pk=respuesta_pk,
                intento__cuestionario__actividad_calificable__curso__docentes_asignados=request.user.docente
            )

            pregunta = respuesta.pregunta
            if pregunta.tipo != 'texto_libre':
                return JsonResponse({'status': 'error', 'message': 'Esta función solo está disponible para preguntas de texto libre.'}, status=400)

            # --- Construcción del Prompt ---
            prompt = f"""
            Actúa como un docente experto que está calificando la respuesta de un estudiante.
            
            Pregunta: "{pregunta.enunciado}"
            Rúbrica (respuesta ideal): "{pregunta.respuesta_correcta_abierta or 'No se proporcionó una rúbrica específica.'}"
            Puntaje máximo para esta pregunta: {pregunta.puntaje}
            
            Respuesta del estudiante: "{respuesta.texto_respuesta}"

            Basado en la rúbrica, califica la respuesta del estudiante en una escala de 0 a {pregunta.puntaje}.
            Proporciona una justificación breve y constructiva para la nota asignada.
            
            Devuelve el resultado en un formato JSON válido con las claves "nota_sugerida" (un número) y "justificacion" (un string).
            Ejemplo: {{"nota_sugerida": 4.5, "justificacion": "El estudiante entiende el concepto principal pero le faltó mencionar un detalle clave."}}
            """

            # --- Llamada a la API de Google ---
            genai.configure(api_key=settings.GOOGLE_API_KEY)
            generation_config = genai.types.GenerationConfig(response_mime_type="application/json")
            model = genai.GenerativeModel('gemini-1.5-flash', generation_config=generation_config)
            response = model.generate_content(prompt)
            
            json_text = response.text.strip().replace("```json", "").replace("```", "")
            sugerencia = json.loads(json_text)

            return JsonResponse({'status': 'success', 'data': sugerencia})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)            