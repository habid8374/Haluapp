# gestion_academica/serializers.py
from rest_framework import serializers
from .models import Pregunta, Opcion, ActividadCalificable

class EventoCalendarioSerializer(serializers.Serializer):
    """
    Un serializer flexible para eventos de FullCalendar.
    Acepta diferentes tipos de eventos (recurrentes y de día único).
    """
    # Campos comunes a todos los eventos
    title = serializers.CharField()
    color = serializers.CharField(required=False)
    url = serializers.URLField(required=False)
    description = serializers.CharField(required=False)
    allDay = serializers.BooleanField(required=False)

    # Campos para eventos de día único (ej. tareas, exámenes)
    start = serializers.CharField(required=False) # Se cambia a CharField para aceptar 'YYYY-MM-DD'
    end = serializers.CharField(required=False)

    # Campos para eventos recurrentes (ej. horario de clases)
    daysOfWeek = serializers.ListField(child=serializers.IntegerField(), required=False)
    startTime = serializers.TimeField(format='%H:%M:%S', required=False)
    endTime = serializers.TimeField(format='%H:%M:%S', required=False)

    class Meta:
        fields = '__all__'

class OpcionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Opcion
        fields = ['id', 'texto'] # NUNCA envíes 'es_correcta' al estudiante

class PreguntaSerializer(serializers.ModelSerializer):
    opciones = OpcionSerializer(many=True, read_only=True)
    class Meta:
        model = Pregunta
        fields = ['id', 'enunciado', 'tipo', 'opciones']

class ActividadInteractivaSerializer(serializers.ModelSerializer):
    preguntas = PreguntaSerializer(many=True, read_only=True)
    class Meta:
        model = ActividadCalificable
        fields = ['id', 'titulo', 'descripcion', 'preguntas']     

# --- Serializer para Enviar Respuestas (actualizado) ---
class EnviarRespuestaSerializer(serializers.Serializer):
    """
    Serializer para validar los datos de una respuesta enviada por el estudiante.
    Ahora incluye el campo para respuestas de texto.
    """
    pregunta_id = serializers.IntegerField()
    opcion_id = serializers.IntegerField(required=False, allow_null=True)
    texto_respuesta = serializers.CharField(required=False, allow_blank=True, allow_null=True)           

