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
from django.utils.translation import gettext as _
import json
import logging
from django.views.generic import DetailView
from google import genai
from google.genai import types
from google.api_core import exceptions as google_exceptions

from finanzas.institucion_credentials import google_api_key as institucion_google_api_key

from .models import (
    Cuestionario, PreguntaCuestionario, OpcionPregunta, 
    IntentoCuestionario, RespuestaEstudiante
)
# Importamos SOLO lo que necesitamos de la otra app.
from gestion_academica.models import Calificacion, ActividadCalificable
from gestion_academica.utils import estudiante_en_curso_actividad, docente_asignado_a_actividad
from gestion_academica.decorators import redirect_si_moroso_estudiante, estudiante_esta_al_dia

logger = logging.getLogger(__name__)


def _normalizar_texto(s):
    """Normaliza para comparar respuestas: minúsculas, sin tildes ni espacios sobrantes."""
    import unicodedata as _ud
    s = (str(s) if s is not None else '').strip().lower()
    return ''.join(c for c in _ud.normalize('NFD', s) if _ud.category(c) != 'Mn')


class CuestionarioListView(LoginRequiredMixin, ListView):
    model = Cuestionario
    template_name = 'cuestionarios/cuestionario_lista.html'
    context_object_name = 'cuestionarios'
    paginate_by = 15

    def get_queryset(self):
        user = self.request.user
        qs = Cuestionario.objects.select_related(
            'actividad_calificable',
            'creado_por',
        ).prefetch_related('preguntas')
        if user.is_superuser:
            return qs
        inst = getattr(user, 'institucion_asociada', None)
        if not inst:
            return Cuestionario.objects.none()
        return qs.filter(institucion=inst)


class EditorCuestionarioView(LoginRequiredMixin, View):
    template_name = 'cuestionarios/editor.html'
    
    def get(self, request, actividad_pk):
        if request.user.is_superuser:
            actividad = get_object_or_404(ActividadCalificable, pk=actividad_pk)
        else:
            actividad = get_object_or_404(
                ActividadCalificable,
                pk=actividad_pk,
                curso__docentes_asignados=request.user.docente,
            )
        
        cuestionario, created = Cuestionario.objects.get_or_create(
            actividad_calificable=actividad,
            defaults={
                'creado_por': request.user,
                'institucion': getattr(request.user, 'institucion_asociada', None) or actividad.institucion,
                'titulo': actividad.titulo
            }
        )
        
        return render(request, self.template_name, {
            'actividad': actividad,
            'cuestionario': cuestionario,
            'titulo_pagina': _("Editor: %(actividad_titulo)s") % {'actividad_titulo': actividad.titulo}
        })


class CuestionarioAPIView(LoginRequiredMixin, View):

    def get(self, request, actividad_pk):
        actividad = get_object_or_404(
            ActividadCalificable.objects.select_related('curso', 'institucion'),
            pk=actividad_pk,
        )
        # puede_ver_respuestas: quién tiene derecho a recibir la hoja de respuestas
        # (es_correcta / respuesta_correcta_abierta). Un estudiante NO debe recibirla
        # mientras resuelve; solo si el docente habilitó 'mostrar_respuestas'.
        puede_ver_respuestas = False
        es_estudiante = False
        if request.user.is_superuser:
            puede_ver_respuestas = True
        elif hasattr(request.user, 'docente') and docente_asignado_a_actividad(request.user, actividad):
            puede_ver_respuestas = True
        elif hasattr(request.user, 'estudiante') and estudiante_en_curso_actividad(
            request.user.estudiante, actividad
        ):
            es_estudiante = True
        elif (
            request.user.is_staff
            and getattr(request.user, 'institucion_asociada_id', None) == actividad.institucion_id
        ):
            puede_ver_respuestas = True
        else:
            return JsonResponse({'error': 'No autorizado.'}, status=403)

        cuestionario = get_object_or_404(
            Cuestionario,
            actividad_calificable_id=actividad_pk,
            institucion_id=actividad.institucion_id,
        )

        # El estudiante solo ve las respuestas correctas si el docente las habilitó.
        if es_estudiante and cuestionario.mostrar_respuestas:
            puede_ver_respuestas = True

        preguntas = []
        for p in cuestionario.preguntas.order_by('orden'):
            pregunta_data = {
                'id': p.id,
                'enunciado': p.enunciado,
                'tipo': p.tipo,
                'puntaje': p.puntaje,
                'orden': p.orden,
                'retroalimentacion': p.retroalimentacion,
                'imagen_url': p.imagen.url if p.imagen else None,
                'imagen_path': p.imagen.name if p.imagen else None,
                'imagen_alt': p.imagen_alt or '',
                'imagen_descripcion': p.imagen_descripcion or '',
                'audio_url': p.audio.url if p.audio else None,
                'audio_path': p.audio.name if p.audio else None,
                'audio_transcripcion': p.audio_transcripcion or '',
            }
            if puede_ver_respuestas:
                pregunta_data['respuesta_correcta_abierta'] = p.respuesta_correcta_abierta

            # "Completar": las respuestas correctas van marcadas como [[respuesta]].
            # Al estudiante que RESUELVE nunca se le envían (aunque el docente
            # haya activado "mostrar respuestas al finalizar", eso es para la
            # pantalla de resultados, no mientras resuelve): se enmascaran a [[]].
            if p.tipo == 'completar' and es_estudiante:
                import re as _re
                pregunta_data['enunciado'] = _re.sub(r'\[\[.*?\]\]', '[[]]', p.enunciado or '')

            if p.tipo in ['opcion_multiple', 'seleccion_multiple', 'verdadero_falso', 'emparejamiento', 'clasificar']:
                pregunta_data['opciones'] = [
                    {
                        'id': op.id,
                        'texto': op.texto,
                        'emparejamiento': op.emparejamiento,
                        'orden': op.orden,
                        # es_correcta solo para quien puede ver la hoja de respuestas
                        **({'es_correcta': op.es_correcta} if puede_ver_respuestas else {}),
                    }
                    for op in p.opciones.order_by('orden')
                ]

            # "Clasificar": el estudiante recibe los ítems (texto) y la lista de
            # categorías (barajadas), SIN saber a qué categoría va cada ítem.
            if p.tipo == 'clasificar':
                import random as _rnd
                cats = list(dict.fromkeys(
                    op.emparejamiento for op in p.opciones.all() if op.emparejamiento
                ))
                _rnd.shuffle(cats)
                pregunta_data['categorias'] = cats
                if es_estudiante:
                    for o in pregunta_data.get('opciones', []):
                        o.pop('emparejamiento', None)

            # "Etiquetar": cada opción es un marcador (texto=etiqueta correcta,
            # emparejamiento="x,y" en % sobre la imagen, orden=índice).
            if p.tipo == 'etiquetar':
                import random as _rnd3
                marcadores, etiquetas = [], []
                for op in p.opciones.order_by('orden'):
                    coords = (op.emparejamiento or '0,0').split(',')
                    try:
                        mx, my = float(coords[0]), float(coords[1])
                    except (ValueError, IndexError):
                        mx, my = 0.0, 0.0
                    marcadores.append({'orden': op.orden, 'x': mx, 'y': my})
                    etiquetas.append(op.texto)
                pregunta_data['marcadores'] = marcadores
                if es_estudiante:
                    # Solo posiciones + banco de etiquetas barajado (sin la respuesta).
                    _rnd3.shuffle(etiquetas)
                    pregunta_data['etiquetas'] = etiquetas
                else:
                    # Docente/editor: opciones completas para poder editarlas.
                    pregunta_data['opciones'] = [
                        {'id': op.id, 'texto': op.texto, 'emparejamiento': op.emparejamiento, 'orden': op.orden}
                        for op in p.opciones.order_by('orden')
                    ]

            # "Hotspot": cada opción es una zona correcta (emparejamiento="x,y,r"
            # en % sobre la imagen; texto=nombre opcional). El estudiante hace clic
            # sobre la imagen; nunca recibe las coordenadas de las zonas.
            if p.tipo == 'hotspot':
                zonas = []
                for op in p.opciones.order_by('orden'):
                    partes = (op.emparejamiento or '0,0,8').split(',')
                    try:
                        zx, zy = float(partes[0]), float(partes[1])
                        zr = float(partes[2]) if len(partes) > 2 else 8.0
                    except (ValueError, IndexError):
                        zx, zy, zr = 0.0, 0.0, 8.0
                    zonas.append({'orden': op.orden, 'x': zx, 'y': zy, 'r': zr, 'texto': op.texto})
                if es_estudiante:
                    # Solo el número de zonas a marcar (los clics permitidos), sin posiciones.
                    pregunta_data['num_zonas'] = len(zonas)
                else:
                    pregunta_data['zonas'] = zonas
                    pregunta_data['opciones'] = [
                        {'id': op.id, 'texto': op.texto, 'emparejamiento': op.emparejamiento, 'orden': op.orden}
                        for op in p.opciones.order_by('orden')
                    ]

            # "Ordenar": cada opción es un paso (texto) con su posición correcta (orden).
            # El estudiante recibe los pasos barajados y debe ordenarlos.
            if p.tipo == 'ordenar':
                import random as _rnd4
                pasos = [
                    {'id': op.id, 'texto': op.texto, 'orden': op.orden}
                    for op in p.opciones.order_by('orden')
                ]
                if es_estudiante:
                    solo_textos = [x['texto'] for x in pasos]
                    _rnd4.shuffle(solo_textos)
                    pregunta_data['pasos'] = solo_textos
                else:
                    pregunta_data['opciones'] = pasos

            # "Mapa conceptual": cada opción es un concepto (nodo). Las conexiones
            # correctas se guardan en emparejamiento como índices (orden) de los
            # nodos vecinos, separados por comas. El estudiante recibe solo los
            # nodos (sin conexiones) y debe relacionarlos.
            if p.tipo == 'mapa_conceptual':
                nodos = [
                    {'id': op.id, 'texto': op.texto, 'orden': op.orden,
                     'emparejamiento': op.emparejamiento}
                    for op in p.opciones.order_by('orden')
                ]
                if es_estudiante:
                    pregunta_data['nodos'] = [
                        {'orden': n['orden'], 'texto': n['texto']} for n in nodos
                    ]
                else:
                    pregunta_data['opciones'] = nodos

            # "Respuesta numérica": cada opción es un valor válido (texto) con su
            # tolerancia (emparejamiento). Al estudiante NUNCA se le envía el valor.
            if p.tipo == 'respuesta_numerica' and not es_estudiante:
                pregunta_data['opciones'] = [
                    {'id': op.id, 'texto': op.texto, 'emparejamiento': op.emparejamiento, 'orden': op.orden}
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
            if request.user.is_superuser:
                actividad = get_object_or_404(ActividadCalificable, pk=actividad_pk)
            else:
                actividad = get_object_or_404(
                    ActividadCalificable,
                    pk=actividad_pk,
                    curso__docentes_asignados=request.user.docente,
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
                    'institucion': getattr(request.user, 'institucion_asociada', None) or actividad.institucion,
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
                    respuesta_correcta_abierta=pregunta_data.get('respuesta_correcta_abierta'),
                    # La imagen/audio se suben aparte y aquí solo se re-referencia su ruta
                    # (no se vuelve a subir el archivo). Ver SubirImagenPreguntaView /
                    # SubirAudioPreguntaView. La descripción (alt) y la transcripción se
                    # conservan (carry-through) para no perderlas ni re-gastar IA al guardar.
                    imagen=(pregunta_data.get('imagen_path') or None),
                    imagen_alt=(pregunta_data.get('imagen_alt') or ''),
                    imagen_descripcion=(pregunta_data.get('imagen_descripcion') or ''),
                    audio=(pregunta_data.get('audio_path') or None),
                    audio_transcripcion=(pregunta_data.get('audio_transcripcion') or ''),
                )
                
                # 4. Creamos las opciones para cada pregunta.
                if pregunta.tipo in ['opcion_multiple', 'seleccion_multiple', 'verdadero_falso', 'emparejamiento', 'clasificar', 'etiquetar', 'hotspot', 'ordenar', 'mapa_conceptual', 'respuesta_numerica']:
                    for opcion_data in pregunta_data.get('opciones', []):
                        texto_val = (opcion_data.get('texto') or '').strip()
                        emp_val = opcion_data.get('emparejamiento')
                        orden_val = opcion_data.get('orden', 0)
                        # En "hotspot" el nombre de la zona es opcional: se completa
                        # con uno por defecto (el campo texto no admite vacío). Las
                        # filas de hotspot sin coordenadas se descartan.
                        if pregunta.tipo == 'hotspot':
                            if not emp_val:
                                continue
                            if not texto_val:
                                texto_val = f"Zona {orden_val + 1}"
                        # Filas totalmente vacías (sin texto) se ignoran para no romper
                        # el guardado con opciones en blanco.
                        elif not texto_val:
                            continue
                        OpcionPregunta.objects.create(
                            pregunta=pregunta,
                            texto=texto_val,
                            emparejamiento=emp_val,
                            es_correcta=opcion_data.get('es_correcta', False),
                            orden=orden_val,
                        )
            
            return JsonResponse({
                'status': 'success',
                'message': 'Cuestionario guardado correctamente',
            })
            
        except Exception as e:
            logger.exception("Error al guardar cuestionario: %s", e)
            return JsonResponse({
                'status': 'error',
                'message': 'Ocurrió un error al guardar el cuestionario. Inténtalo de nuevo.'
            }, status=400)


class SubirImagenPreguntaView(LoginRequiredMixin, View):
    """Sube la imagen/gráfico de una pregunta y devuelve su ruta y URL. El
    editor guarda esa ruta en el JSON del cuestionario (no reenvía el archivo)."""

    def post(self, request, actividad_pk):
        actividad = get_object_or_404(ActividadCalificable, pk=actividad_pk)
        if not (request.user.is_superuser or (
            hasattr(request.user, 'docente') and docente_asignado_a_actividad(request.user, actividad)
        )):
            return JsonResponse({'error': 'No autorizado.'}, status=403)

        archivo = request.FILES.get('imagen')
        if not archivo:
            return JsonResponse({'error': 'No se recibió ninguna imagen.'}, status=400)
        if archivo.size > 5 * 1024 * 1024:
            return JsonResponse({'error': 'La imagen supera el tamaño máximo (5 MB).'}, status=400)
        ext = (archivo.name.rsplit('.', 1)[-1] if '.' in archivo.name else '').lower()
        if ext not in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
            return JsonResponse({'error': 'Formato no permitido. Usa JPG, PNG, GIF o WEBP.'}, status=400)

        import uuid
        from django.core.files.storage import default_storage
        nombre = f"cuestionarios/preguntas/{actividad_pk}/{uuid.uuid4().hex}.{ext}"
        path = default_storage.save(nombre, archivo)
        return JsonResponse({'path': path, 'url': default_storage.url(path)})


class SubirAudioPreguntaView(LoginRequiredMixin, View):
    """Sube el audio de apoyo de una pregunta y devuelve su ruta y URL. El editor
    guarda esa ruta en el JSON del cuestionario (no reenvía el archivo)."""

    def post(self, request, actividad_pk):
        actividad = get_object_or_404(ActividadCalificable, pk=actividad_pk)
        if not (request.user.is_superuser or (
            hasattr(request.user, 'docente') and docente_asignado_a_actividad(request.user, actividad)
        )):
            return JsonResponse({'error': 'No autorizado.'}, status=403)

        archivo = request.FILES.get('audio')
        if not archivo:
            return JsonResponse({'error': 'No se recibió ningún audio.'}, status=400)
        if archivo.size > 20 * 1024 * 1024:
            return JsonResponse({'error': 'El audio supera el tamaño máximo (20 MB).'}, status=400)
        ext = (archivo.name.rsplit('.', 1)[-1] if '.' in archivo.name else '').lower()
        if ext not in ('mp3', 'wav', 'ogg', 'oga', 'm4a', 'aac', 'webm', 'opus'):
            return JsonResponse({'error': 'Formato no permitido. Usa MP3, WAV, OGG, M4A, AAC o WEBM.'}, status=400)

        import uuid
        from django.core.files.storage import default_storage
        nombre = f"cuestionarios/preguntas/audio/{actividad_pk}/{uuid.uuid4().hex}.{ext}"
        path = default_storage.save(nombre, archivo)
        return JsonResponse({'path': path, 'url': default_storage.url(path)})


class ToggleCuestionarioActivoView(LoginRequiredMixin, View):

    def post(self, request, cuestionario_id):
        if request.user.is_superuser:
            cuestionario = get_object_or_404(Cuestionario, pk=cuestionario_id)
        else:
            inst = getattr(request.user, 'institucion_asociada', None)
            if not inst:
                return JsonResponse({'error': 'No autorizado.'}, status=403)
            cuestionario = get_object_or_404(
                Cuestionario,
                pk=cuestionario_id,
                creado_por=request.user,
                institucion=inst,
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
        redir = redirect_si_moroso_estudiante(request)
        if redir:
            return redir
        if not hasattr(request.user, 'estudiante'):
            messages.error(request, _("Solo los estudiantes pueden iniciar esta evaluación."))
            return redirect('gestion_academica:inicio_academico')

        actividad = get_object_or_404(
            ActividadCalificable.objects.select_related('curso', 'institucion'),
            pk=actividad_pk,
        )
        if not estudiante_en_curso_actividad(request.user.estudiante, actividad):
            messages.error(request, _("No tienes acceso a esta actividad."))
            return redirect('gestion_academica:dashboard_estudiante')

        cuestionario = get_object_or_404(Cuestionario, actividad_calificable=actividad)

        context = {
            'actividad': actividad,
            'cuestionario': cuestionario,
            'titulo_pagina': _("Iniciar: %(cuestionario_titulo)s") % {'cuestionario_titulo': cuestionario.titulo}
        }
        return render(request, 'cuestionarios/iniciar_cuestionario.html', context)

    def post(self, request, actividad_pk):
        """
        Crea un nuevo intento SOLO SI el estudiante no ha superado el límite de intentos
        o si se le ha habilitado un intento extra.
        """
        redir = redirect_si_moroso_estudiante(request)
        if redir:
            return redir
        if not hasattr(request.user, 'estudiante'):
            messages.error(request, _("Solo los estudiantes pueden iniciar esta evaluación."))
            return redirect('gestion_academica:inicio_academico')

        estudiante = request.user.estudiante
        actividad = get_object_or_404(
            ActividadCalificable.objects.select_related('curso', 'institucion'),
            pk=actividad_pk,
        )
        if not estudiante_en_curso_actividad(estudiante, actividad):
            messages.error(request, _("No tienes acceso a esta actividad."))
            return redirect('gestion_academica:dashboard_estudiante')

        cuestionario = get_object_or_404(
            Cuestionario,
            actividad_calificable_id=actividad_pk,
            institucion_id=actividad.institucion_id,
        )
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
            messages.error(request, _("Has alcanzado el límite de %(cuestionario_intento)s intento(s) para este cuestionario.") % {'cuestionario_intento': cuestionario.intentos_permitidos})
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
        redir = redirect_si_moroso_estudiante(request)
        if redir:
            return redir
        if not hasattr(request.user, 'estudiante'):
            messages.error(request, _("Solo los estudiantes pueden resolver cuestionarios aquí."))
            return redirect('gestion_academica:inicio_academico')
        intento = get_object_or_404(
            IntentoCuestionario.objects.select_related(
                'cuestionario__actividad_calificable__curso',
                'cuestionario__actividad_calificable__institucion',
            ),
            pk=intento_pk,
            estudiante=request.user.estudiante,
            estado='EN_PROGRESO',
        )
        actividad = intento.cuestionario.actividad_calificable
        if not estudiante_en_curso_actividad(request.user.estudiante, actividad):
            messages.error(request, _("No tienes acceso a este intento."))
            return redirect('gestion_academica:dashboard_estudiante')
        # Tiempo extra por accesibilidad (Ola 2): si el estudiante tiene un perfil
        # activo con tiempo_extra_pct, se amplía el temporizador de este intento.
        tiempo_limite = intento.cuestionario.tiempo_limite or 0
        tiempo_limite_efectivo = tiempo_limite
        try:
            perfil = request.user.estudiante.perfil_accesibilidad
        except Exception:
            perfil = None
        if tiempo_limite and perfil and perfil.activo and perfil.tiempo_extra_pct:
            tiempo_limite_efectivo = int(round(tiempo_limite * (1 + perfil.tiempo_extra_pct / 100.0)))
        # Auto-simplificar enunciados (Ola 2 → Ola 3): si el perfil del estudiante
        # pide "enunciados simplificados" (o "lectura fácil"), la versión en lectura
        # fácil se muestra sola, sin que el estudiante tenga que pulsar el botón.
        # Reutiliza el enunciado_simple cacheado en cada pregunta (no gasta créditos
        # de más). El botón manual sigue disponible para todos.
        auto_simplificar = bool(
            perfil and perfil.activo and (perfil.enunciado_simplificado or perfil.easy_read)
        )
        # Si el estudiante usa lectura por voz (lector de pantalla), las preguntas
        # basadas en imagen (etiquetar) se abren directamente en su modo accesible
        # de lista, que se puede responder sin ver ni tocar la imagen.
        auto_modo_accesible = bool(perfil and perfil.activo and perfil.tts_default)
        context = {
            'intento': intento,
            'cuestionario': intento.cuestionario,
            'tiempo_limite_efectivo': tiempo_limite_efectivo,
            'auto_simplificar': auto_simplificar,
            'auto_modo_accesible': auto_modo_accesible,
            'titulo_pagina': _("Resolviendo: %(intento_cuestionario)s") % {'intento_cuestionario': intento.cuestionario.titulo}
        }
        return render(request, 'cuestionarios/resolver_cuestionario.html', context)

# Reemplaza tu ResolverCuestionarioAPIView existente con esta versión mejorada
class ResolverCuestionarioAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, intento_pk):
        if not hasattr(request.user, 'estudiante'):
            return Response({'error': 'Solo estudiantes pueden enviar respuestas.'}, status=status.HTTP_403_FORBIDDEN)

        if getattr(request.user, 'rol', None) == 'estudiante':
            al_dia, _ = estudiante_esta_al_dia(request)
            if not al_dia:
                return Response(
                    {'error': 'El portal está bloqueado por mensualidades vencidas.'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        intento = get_object_or_404(IntentoCuestionario, pk=intento_pk, estudiante=request.user.estudiante)
        actividad = ActividadCalificable.objects.select_related('curso').get(
            pk=intento.cuestionario.actividad_calificable_id
        )
        if not estudiante_en_curso_actividad(request.user.estudiante, actividad):
            return Response({'error': 'No autorizado.'}, status=status.HTTP_403_FORBIDDEN)

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

                elif tipo_pregunta in ('emparejamiento', 'clasificar'):
                    # Clasificar reutiliza el mismo formato: cada ítem (texto)
                    # debe quedar en su categoría (emparejamiento).
                    pares_correctos_db = set(pregunta.opciones.values_list('texto', 'emparejamiento'))
                    pares_enviados_data = respuesta_enviada.get('respuesta_emparejamiento', [])
                    pares_enviados = set((p['texto'], p['emparejamiento']) for p in pares_enviados_data)
                    if pares_correctos_db and pares_correctos_db == pares_enviados:
                        puntaje_pregunta = pregunta.puntaje

                elif tipo_pregunta == 'completar':
                    # Las respuestas correctas están marcadas en el enunciado como [[respuesta]].
                    # Se califica proporcional a los espacios acertados (comparación
                    # sin distinguir mayúsculas/acentos ni espacios sobrantes).
                    import re as _re, unicodedata as _ud

                    def _norm(s):
                        s = (s or '').strip().lower()
                        return ''.join(
                            c for c in _ud.normalize('NFD', s) if _ud.category(c) != 'Mn'
                        )

                    correctas = _re.findall(r'\[\[(.*?)\]\]', pregunta.enunciado or '')
                    enviadas = respuesta_enviada.get('respuesta_completar', []) or []
                    if correctas:
                        aciertos = sum(
                            1 for i, c in enumerate(correctas)
                            if i < len(enviadas) and _norm(enviadas[i]) == _norm(c)
                        )
                        puntaje_pregunta = round(pregunta.puntaje * (aciertos / len(correctas)), 2)

                elif tipo_pregunta == 'etiquetar':
                    # correctas: {orden_marcador: etiqueta}. enviadas: {orden: etiqueta puesta}.
                    correctas = {op.orden: op.texto for op in pregunta.opciones.all()}
                    enviadas = respuesta_enviada.get('respuesta_etiquetar', {}) or {}
                    if correctas:
                        aciertos = sum(
                            1 for k, v in correctas.items()
                            if _normalizar_texto(enviadas.get(str(k), '')) == _normalizar_texto(v)
                        )
                        puntaje_pregunta = round(pregunta.puntaje * (aciertos / len(correctas)), 2)

                elif tipo_pregunta == 'hotspot':
                    # Zonas correctas: emparejamiento="x,y,r" en %. El estudiante envía
                    # una lista de clics [{x,y}]. Se cuenta cada zona que reciba al menos
                    # un clic dentro de su radio. Calificación proporcional a las zonas.
                    zonas = []
                    for op in pregunta.opciones.all():
                        partes = (op.emparejamiento or '0,0,8').split(',')
                        try:
                            zx, zy = float(partes[0]), float(partes[1])
                            zr = float(partes[2]) if len(partes) > 2 else 8.0
                        except (ValueError, IndexError):
                            continue
                        zonas.append((zx, zy, zr))
                    clics = respuesta_enviada.get('respuesta_hotspot', []) or []
                    if zonas:
                        aciertos = 0
                        for (zx, zy, zr) in zonas:
                            for c in clics:
                                try:
                                    cx, cy = float(c.get('x')), float(c.get('y'))
                                except (TypeError, ValueError):
                                    continue
                                if ((cx - zx) ** 2 + (cy - zy) ** 2) ** 0.5 <= zr:
                                    aciertos += 1
                                    break
                        puntaje_pregunta = round(pregunta.puntaje * (aciertos / len(zonas)), 2)

                elif tipo_pregunta == 'ordenar':
                    # correctas: lista de textos en el orden correcto. enviadas: lista del
                    # estudiante. Calificación proporcional por posiciones acertadas.
                    correctas = [op.texto for op in pregunta.opciones.order_by('orden')]
                    enviadas = respuesta_enviada.get('respuesta_ordenar', []) or []
                    if correctas:
                        aciertos = sum(
                            1 for i, c in enumerate(correctas)
                            if i < len(enviadas) and _normalizar_texto(enviadas[i]) == _normalizar_texto(c)
                        )
                        puntaje_pregunta = round(pregunta.puntaje * (aciertos / len(correctas)), 2)

                elif tipo_pregunta == 'mapa_conceptual':
                    # Conexiones correctas: en cada opción, emparejamiento = índices
                    # (orden) de nodos vecinos, separados por comas. Se arma un conjunto
                    # de aristas no dirigidas. El estudiante envía respuesta_mapa=[[a,b],…].
                    correctas = set()
                    for op in pregunta.opciones.all():
                        for parte in (op.emparejamiento or '').split(','):
                            parte = parte.strip()
                            if parte == '':
                                continue
                            try:
                                vecino = int(parte)
                            except ValueError:
                                continue
                            if vecino != op.orden:
                                correctas.add(frozenset((op.orden, vecino)))
                    enviadas_raw = respuesta_enviada.get('respuesta_mapa', []) or []
                    enviadas = set()
                    for par in enviadas_raw:
                        try:
                            a, b = int(par[0]), int(par[1])
                        except (TypeError, ValueError, IndexError):
                            continue
                        if a != b:
                            enviadas.add(frozenset((a, b)))
                    if correctas:
                        aciertos = len(correctas & enviadas)
                        sobrantes = len(enviadas - correctas)
                        # Penaliza conexiones de más para desincentivar "conectar todo".
                        fraccion = max(0, aciertos - sobrantes) / len(correctas)
                        puntaje_pregunta = round(pregunta.puntaje * min(1.0, fraccion), 2)

                elif tipo_pregunta == 'respuesta_numerica':
                    # Correcto si el número del estudiante cae dentro de ±tolerancia de
                    # ALGÚN valor válido. Acepta coma o punto decimal.
                    def _num(s):
                        try:
                            return float(str(s).strip().replace(',', '.'))
                        except (TypeError, ValueError):
                            return None
                    enviado = _num(respuesta_enviada.get('respuesta_numerica'))
                    if enviado is not None:
                        for op in pregunta.opciones.all():
                            valor = _num(op.texto)
                            if valor is None:
                                continue
                            tol = _num(op.emparejamiento) or 0.0
                            if abs(enviado - valor) <= abs(tol):
                                puntaje_pregunta = pregunta.puntaje
                                break

            puntaje_total += puntaje_pregunta

            # Esta línea ahora usará el modelo RespuestaEstudiante correcto de la app 'cuestionarios'
            respuesta_obj = RespuestaEstudiante.objects.create(
                intento=intento,
                pregunta=pregunta,
                texto_respuesta=(
                    (respuesta_enviada.get('texto_respuesta')
                     or respuesta_enviada.get('respuesta_numerica'))
                    if respuesta_enviada else None
                ),
                respuesta_emparejamiento=(
                    (respuesta_enviada.get('respuesta_emparejamiento')
                     or respuesta_enviada.get('respuesta_etiquetar')
                     or respuesta_enviada.get('respuesta_hotspot')
                     or respuesta_enviada.get('respuesta_ordenar')
                     or respuesta_enviada.get('respuesta_mapa'))
                    if respuesta_enviada else None
                ),
                respuesta_completar=respuesta_enviada.get('respuesta_completar') if respuesta_enviada else None,
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

        messages.success(request, _("Se ha habilitado un intento adicional para el estudiante %(intento_estudiante)s.") % {'intento_estudiante': intento.estudiante})
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
        context['titulo_pagina'] = _("Revisión de %(estudiante)s") % {'estudiante': intento.estudiante}
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

        messages.success(request, _('La calificación ha sido actualizada correctamente.'))
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
        
        messages.success(request, _("El intento de '%(estudiante_nombre)s' en el cuestionario '%(cuestionario_titulo)s' ha sido eliminado exitosamente.") % {'estudiante_nombre': estudiante_nombre, 'cuestionario_titulo': cuestionario_titulo})
        
        # Redirigimos de vuelta al historial
        return redirect(reverse_lazy('gestion_academica:historial_entregas'))   
    

class GenerarPreguntasIAView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, cuestionario_pk):
        logger.debug("GenerarPreguntasIAView inicio cuestionario_pk=%s", cuestionario_pk)
        try:
            if request.user.is_superuser:
                cuestionario = get_object_or_404(
                    Cuestionario.objects.select_related('actividad_calificable__curso', 'institucion'),
                    pk=cuestionario_pk,
                )
            else:
                cuestionario = get_object_or_404(
                    Cuestionario.objects.select_related('actividad_calificable__curso'),
                    pk=cuestionario_pk,
                    creado_por=request.user,
                )
                if not docente_asignado_a_actividad(request.user, cuestionario.actividad_calificable):
                    return JsonResponse(
                        {'status': 'error', 'message': 'No autorizado para modificar este cuestionario.'},
                        status=403,
                    )
            api_key = institucion_google_api_key(cuestionario.institucion)
            if not api_key:
                return JsonResponse(
                    {'status': 'error', 'message': 'La institución no tiene configurada la API key de Google (Gemini).'},
                    status=500,
                )
            # Tope de IA: si la institución superó su límite del mes, no generamos.
            from finanzas import ia as _ia_gate
            _ok_ia, _msg_ia = _ia_gate.puede_usar_ia(cuestionario.institucion)
            if not _ok_ia:
                return JsonResponse({'status': 'error', 'message': _msg_ia}, status=200)
            data = request.data
            logger.debug("GenerarPreguntasIA datos keys=%s", list(data.keys()) if hasattr(data, "keys") else type(data))

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
            logger.debug("GenerarPreguntasIA prompt (primeros 120 chars): %s...", prompt[:120])

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=_ia_gate._MODELO_GEMINI,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            # Registrar consumo de IA (tokens + costo) para el tope y el panel.
            try:
                _um = getattr(response, 'usage_metadata', None)
                _ia_gate.registrar_uso(
                    cuestionario.institucion, _ia_gate._MODELO_GEMINI,
                    getattr(_um, 'prompt_token_count', 0) or 0,
                    getattr(_um, 'candidates_token_count', 0) or 0,
                )
            except Exception:
                pass

            logger.debug("GenerarPreguntasIA respuesta IA longitud=%s", len(response.text or ""))

            json_text = response.text.strip().replace("```json", "").replace("```", "")
            respuesta_parseada = json.loads(json_text)

            if isinstance(respuesta_parseada, dict) and 'evaluacion' in respuesta_parseada:
                lista_de_preguntas = respuesta_parseada['evaluacion']
                logger.debug("GenerarPreguntasIA: lista bajo clave 'evaluacion'")
            else:
                lista_de_preguntas = respuesta_parseada

            logger.info("GenerarPreguntasIA: %s preguntas a persistir", len(lista_de_preguntas))

            with transaction.atomic():
                orden_actual = cuestionario.preguntas.count()
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
            logger.info("GenerarPreguntasIA: guardado OK cuestionario_pk=%s", cuestionario_pk)
            return JsonResponse({'status': 'success', 'message': f'¡Se han añadido {len(lista_de_preguntas)} preguntas nuevas al cuestionario!'})

        except google_exceptions.ResourceExhausted as e:
            logger.warning("GenerarPreguntasIA cuota agotada: %s", e)
            return JsonResponse({
                'status': 'error',
                'message': 'La cuota de la API de IA está agotada por ahora. Espera unos minutos e inténtalo de nuevo, o verifica el plan de facturación de la API key en Google AI Studio.'
            }, status=429)
        except json.JSONDecodeError as e:
            logger.warning("GenerarPreguntasIA JSON inválido: %s", e, exc_info=True)
            return JsonResponse({'status': 'error', 'message': 'La IA devolvió una respuesta en formato inválido. Intenta de nuevo.'}, status=400)
        except Exception as e:
            logger.exception("GenerarPreguntasIA error: %s", e)
            return JsonResponse({'status': 'error', 'message': 'Error inesperado al generar preguntas. Inténtalo de nuevo.'}, status=500)

class SugerirCalificacionIAView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, respuesta_pk):
        try:
            # Seguridad: Verificamos que el docente tenga permiso sobre este intento
            respuesta = get_object_or_404(
                RespuestaEstudiante.objects.select_related(
                    'pregunta',
                    'intento__cuestionario__actividad_calificable__curso__institucion',
                ),
                pk=respuesta_pk,
                intento__cuestionario__actividad_calificable__curso__docentes_asignados=request.user.docente
            )

            pregunta = respuesta.pregunta
            if pregunta.tipo != 'texto_libre':
                return JsonResponse({'status': 'error', 'message': 'Esta función solo está disponible para preguntas de texto libre.'}, status=400)

            institucion = respuesta.intento.cuestionario.actividad_calificable.curso.institucion
            api_key = institucion_google_api_key(institucion)
            if not api_key:
                return JsonResponse(
                    {'status': 'error', 'message': 'La institución no tiene configurada la API key de Google (Gemini).'},
                    status=500,
                )
            from finanzas import ia as _ia_gate
            _ok_ia, _msg_ia = _ia_gate.puede_usar_ia(institucion)
            if not _ok_ia:
                return JsonResponse({'status': 'error', 'message': _msg_ia}, status=200)

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
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=_ia_gate._MODELO_GEMINI,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            try:
                _um = getattr(response, 'usage_metadata', None)
                _ia_gate.registrar_uso(
                    institucion, _ia_gate._MODELO_GEMINI,
                    getattr(_um, 'prompt_token_count', 0) or 0,
                    getattr(_um, 'candidates_token_count', 0) or 0,
                )
            except Exception:
                pass

            json_text = response.text.strip().replace("```json", "").replace("```", "")
            sugerencia = json.loads(json_text)
            return JsonResponse({'status': 'success', 'data': sugerencia})

        except google_exceptions.ResourceExhausted:
            logger.warning("SugerirCalificacionIA cuota agotada")
            return JsonResponse({
                'status': 'error',
                'message': 'La cuota de la API de IA está agotada. Espera unos minutos e inténtalo de nuevo.'
            }, status=429)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'La IA devolvió una respuesta en formato inválido.'}, status=400)
        except Exception as e:
            logger.exception("SugerirCalificacionIA error: %s", e)
            return JsonResponse({'status': 'error', 'message': 'Error inesperado al generar la sugerencia. Inténtalo de nuevo.'}, status=500)

# ═══════════════════════════════════════════════════════════════════════════════
#  Accesibilidad (Ola 3) — IA de apoyo: lectura fácil y descripción de imágenes
# ═══════════════════════════════════════════════════════════════════════════════
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .ia_accesibilidad import simplificar_texto, describir_imagen, describir_imagen_detallada


def _institucion_de_pregunta(pregunta):
    act = pregunta.cuestionario.actividad_calificable
    return getattr(act, 'institucion', None)


@login_required
@require_POST
def simplificar_enunciado_ia(request, pregunta_pk):
    """Devuelve el enunciado en 'lectura fácil'. Se calcula UNA vez con IA y se
    cachea en la pregunta para reutilizarlo con todos los estudiantes."""
    pregunta = get_object_or_404(
        PreguntaCuestionario.objects.select_related(
            'cuestionario__actividad_calificable__institucion'
        ),
        pk=pregunta_pk,
    )
    institucion = _institucion_de_pregunta(pregunta)
    actividad = pregunta.cuestionario.actividad_calificable
    # Aislamiento multi-institución + acceso real a la actividad (salvo superusuario):
    # 1) mismo colegio; 2) que sea su curso (estudiante) o esté asignado (docente) o
    #    sea personal de la institución. Evita fugas y gasto de créditos ajenos.
    if not request.user.is_superuser:
        if getattr(request.user, 'institucion_asociada_id', None) != getattr(institucion, 'pk', None):
            return HttpResponseForbidden("No autorizado.")
        tiene_acceso = False
        if hasattr(request.user, 'estudiante') and estudiante_en_curso_actividad(request.user.estudiante, actividad):
            tiene_acceso = True
        elif hasattr(request.user, 'docente') and docente_asignado_a_actividad(request.user, actividad):
            tiene_acceso = True
        elif request.user.is_staff:
            tiene_acceso = True
        if not tiene_acceso:
            return HttpResponseForbidden("No autorizado.")

    if pregunta.enunciado_simple:
        return JsonResponse({'ok': True, 'texto': pregunta.enunciado_simple, 'cache': True})

    # En "completar" el enunciado guarda las respuestas en [[...]]: se enmascaran
    # antes de enviarlas a la IA para no filtrarlas al estudiante.
    texto_fuente = pregunta.enunciado or ''
    if pregunta.tipo == 'completar':
        import re as _re
        texto_fuente = _re.sub(r'\[\[.*?\]\]', '____', texto_fuente)

    ok, resultado = simplificar_texto(institucion, texto_fuente)
    if ok:
        pregunta.enunciado_simple = resultado
        pregunta.save(update_fields=['enunciado_simple'])
        return JsonResponse({'ok': True, 'texto': resultado, 'cache': False})
    return JsonResponse({'ok': False, 'message': resultado}, status=200)


@login_required
@require_POST
def generar_alt_cuestionario_ia(request, cuestionario_pk):
    """Genera con IA la descripción (alt) de las imágenes del cuestionario que
    aún no la tengan. Acción del docente/coordinador (un botón, sin comandos)."""
    cuestionario = get_object_or_404(
        Cuestionario.objects.select_related('actividad_calificable__institucion'),
        pk=cuestionario_pk,
    )
    actividad = cuestionario.actividad_calificable
    if not (request.user.is_superuser or docente_asignado_a_actividad(request.user, actividad)):
        return HttpResponseForbidden("No autorizado.")

    institucion = getattr(actividad, 'institucion', None)
    generadas, fallidas, ultimo_error = 0, 0, ''
    for p in cuestionario.preguntas.all():
        if not p.imagen or p.imagen_alt:
            continue
        ok, resultado = describir_imagen(institucion, p.imagen)
        if ok:
            p.imagen_alt = resultado
            p.save(update_fields=['imagen_alt'])
            generadas += 1
        else:
            fallidas += 1
            ultimo_error = resultado

    if generadas == 0 and fallidas == 0:
        return JsonResponse({'ok': True, 'message': 'No hay imágenes pendientes de describir.', 'generadas': 0})
    if generadas == 0 and fallidas:
        return JsonResponse({'ok': False, 'message': ultimo_error or 'No se pudo generar la descripción.'}, status=200)
    return JsonResponse({
        'ok': True,
        'generadas': generadas,
        'fallidas': fallidas,
        'message': f'Descripciones generadas: {generadas}.' + (f' No se pudieron generar: {fallidas}.' if fallidas else ''),
    })


@login_required
@require_POST
def generar_audiodescripcion_cuestionario_ia(request, cuestionario_pk):
    """Genera con IA la AUDIO-DESCRIPCIÓN detallada de las imágenes del
    cuestionario que aún no la tengan (para estudiantes que no ven la imagen).
    Acción del docente/coordinador (un botón, sin comandos)."""
    cuestionario = get_object_or_404(
        Cuestionario.objects.select_related('actividad_calificable__institucion'),
        pk=cuestionario_pk,
    )
    actividad = cuestionario.actividad_calificable
    if not (request.user.is_superuser or docente_asignado_a_actividad(request.user, actividad)):
        return HttpResponseForbidden("No autorizado.")

    institucion = getattr(actividad, 'institucion', None)
    generadas, fallidas, ultimo_error = 0, 0, ''
    for p in cuestionario.preguntas.all():
        if not p.imagen or p.imagen_descripcion:
            continue
        ok, resultado = describir_imagen_detallada(institucion, p.imagen)
        if ok:
            p.imagen_descripcion = resultado
            p.save(update_fields=['imagen_descripcion'])
            generadas += 1
        else:
            fallidas += 1
            ultimo_error = resultado

    if generadas == 0 and fallidas == 0:
        return JsonResponse({'ok': True, 'message': 'No hay imágenes pendientes de audio-describir.', 'generadas': 0})
    if generadas == 0 and fallidas:
        return JsonResponse({'ok': False, 'message': ultimo_error or 'No se pudo generar la audio-descripción.'}, status=200)
    return JsonResponse({
        'ok': True,
        'generadas': generadas,
        'fallidas': fallidas,
        'message': f'Audio-descripciones generadas: {generadas}.' + (f' No se pudieron generar: {fallidas}.' if fallidas else ''),
    })


@login_required
@require_POST
def generar_transcripcion_cuestionario_ia(request, cuestionario_pk):
    """Genera con IA la transcripción (subtítulo) de los audios del cuestionario
    que aún no la tengan. Acción del docente/coordinador (un botón, sin comandos)."""
    import mimetypes
    from .ia_accesibilidad import _ia  # compuerta central (tope + medición)

    cuestionario = get_object_or_404(
        Cuestionario.objects.select_related('actividad_calificable__institucion'),
        pk=cuestionario_pk,
    )
    actividad = cuestionario.actividad_calificable
    if not (request.user.is_superuser or docente_asignado_a_actividad(request.user, actividad)):
        return HttpResponseForbidden("No autorizado.")

    institucion = getattr(actividad, 'institucion', None)
    generadas, fallidas, ultimo_error = 0, 0, ''
    for p in cuestionario.preguntas.all():
        if not p.audio or p.audio_transcripcion:
            continue
        try:
            with p.audio.open('rb') as fh:
                data = fh.read()
            mime = mimetypes.guess_type(p.audio.name)[0] or 'audio/mpeg'
        except Exception:
            fallidas += 1
            ultimo_error = 'No se pudo leer el audio.'
            continue
        ok, resultado = _ia.transcribir_audio(institucion, data, mime)
        if ok:
            p.audio_transcripcion = resultado
            p.save(update_fields=['audio_transcripcion'])
            generadas += 1
        else:
            fallidas += 1
            ultimo_error = resultado

    if generadas == 0 and fallidas == 0:
        return JsonResponse({'ok': True, 'message': 'No hay audios pendientes de transcribir.', 'generadas': 0})
    if generadas == 0 and fallidas:
        return JsonResponse({'ok': False, 'message': ultimo_error or 'No se pudo generar la transcripción.'}, status=200)
    return JsonResponse({
        'ok': True,
        'generadas': generadas,
        'fallidas': fallidas,
        'message': f'Transcripciones generadas: {generadas}.' + (f' No se pudieron generar: {fallidas}.' if fallidas else ''),
    })
