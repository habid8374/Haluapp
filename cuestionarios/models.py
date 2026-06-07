# cuestionarios/models.py

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

class Cuestionario(models.Model):
    # ... (Tu modelo Cuestionario se mantiene igual) ...
    actividad_calificable = models.OneToOneField(
        'gestion_academica.ActividadCalificable',
        on_delete=models.CASCADE,
        related_name='cuestionario'
    )
    titulo = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True)
    tiempo_limite = models.PositiveIntegerField(
        default=30,
        help_text="Duración en minutos (0 para ilimitado)"
    )
    intentos_permitidos = models.PositiveIntegerField(
        default=5,
        help_text="Máximo de veces que el estudiante puede presentar el cuestionario (recomendado 3–5).",
    )
    activo = models.BooleanField(default=True)
    mostrar_respuestas = models.BooleanField(
        default=False,
        help_text="Mostrar respuestas correctas al finalizar"
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa',
        on_delete=models.CASCADE
    )

    def clean(self):
        if self.tiempo_limite > 240:  # Máximo 4 horas
            raise ValidationError("El tiempo límite no puede exceder 240 minutos")
        if self.intentos_permitidos > 10:
            raise ValidationError("Los intentos no pueden ser más de 10")

    def save(self, *args, **kwargs):
        if not self.institucion_id:
            self.institucion = self.actividad_calificable.institucion
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.titulo

    class Meta:
        verbose_name = "Cuestionario"
        verbose_name_plural = "Cuestionarios"
        ordering = ['-fecha_creacion']
        permissions = [
            ("can_toggle_active", "Puede activar/desactivar cuestionarios"),
        ]

class PreguntaCuestionario(models.Model):
    # ▼▼▼ INICIO DE LA MODIFICACIÓN ▼▼▼
    TIPOS_PREGUNTA = [
        ('opcion_multiple', 'Opción Única'),
        ('seleccion_multiple', 'Selección Múltiple'),
        ('verdadero_falso', 'Verdadero/Falso'),
        ('texto_libre', 'Texto Libre'),
        ('emparejamiento', 'Emparejamiento'),
    ]
    # ▲▲▲ FIN DE LA MODIFICACIÓN ▲▲▲
    
    cuestionario = models.ForeignKey(
        Cuestionario,
        on_delete=models.CASCADE,
        related_name='preguntas'
    )
    enunciado = models.TextField()
    tipo = models.CharField(
        max_length=20,
        choices=TIPOS_PREGUNTA,
        default='opcion_multiple'
    )
    puntaje = models.PositiveIntegerField(default=1)
    orden = models.PositiveIntegerField(default=0)
    retroalimentacion = models.TextField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    respuesta_correcta_abierta = models.TextField(
        blank=True,
        null=True,
        verbose_name="Rúbrica o Respuesta Correcta (para preguntas abiertas)",
        help_text="Para preguntas de texto libre, describe aquí la respuesta ideal o los puntos clave que el estudiante debe mencionar."
    )

    def __str__(self):
        return f"{self.enunciado[:50]}..." if len(self.enunciado) > 50 else self.enunciado

    class Meta:
        ordering = ['orden']
        unique_together = ['cuestionario', 'orden']
        verbose_name = "Pregunta"
        verbose_name_plural = "Preguntas"


class OpcionPregunta(models.Model):
    pregunta = models.ForeignKey(
        'PreguntaCuestionario', # Usar string para evitar importaciones circulares si es necesario
        on_delete=models.CASCADE,
        related_name='opciones'
    )
    texto = models.CharField(max_length=500, help_text="Para Emparejamiento, este es el primer elemento del par.")
    
    # --- CAMPO CORREGIDO Y CONSOLIDADO ---
    # Este campo guardará el texto correspondiente para las preguntas de emparejamiento.
    # Se ha renombrado de 'respuesta' a 'emparejamiento' para mayor claridad.
    emparejamiento = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Solo para preguntas de emparejamiento: la respuesta con la que se debe emparejar este texto."
    )
    # --- FIN DE LA CORRECCIÓN ---

    es_correcta = models.BooleanField(default=False)
    orden = models.PositiveIntegerField(default=0)

    def clean(self):
        tipo = self.pregunta.tipo

        if tipo == 'opcion_multiple':
            opciones_correctas = self.pregunta.opciones.filter(es_correcta=True)
            if self.pk:
                opciones_correctas = opciones_correctas.exclude(pk=self.pk)
            if self.es_correcta and opciones_correctas.exists():
                raise ValidationError("Solo puede haber una respuesta correcta para preguntas de Opción Única.")
        
        if tipo == 'emparejamiento' and self.texto and not self.emparejamiento:
            raise ValidationError("En preguntas de emparejamiento, cada opción debe tener una respuesta asociada.")

        if tipo == 'verdadero_falso':
            # Esta validación se puede manejar mejor en el formulario o en la vista del admin
            # para evitar complejidad en el guardado de la primera opción.
            pass

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.texto[:50]}... ({'✓' if self.es_correcta else '✗'})"

    class Meta:
        ordering = ['orden']
        verbose_name = "Opción"
        verbose_name_plural = "Opciones"

class IntentoCuestionario(models.Model):
    """
    Registra cada intento de un estudiante de resolver un cuestionario.
    """
    ESTADOS = [
        ('EN_PROGRESO', 'En Progreso'),
        ('FINALIZADO', 'Finalizado'),
    ]
    cuestionario = models.ForeignKey(Cuestionario, on_delete=models.CASCADE, related_name='intentos')
    estudiante = models.ForeignKey('gestion_academica.Estudiante', on_delete=models.CASCADE, related_name='intentos_cuestionarios')
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    puntaje_obtenido = models.FloatField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='EN_PROGRESO')
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)
    intento_extra_habilitado = models.BooleanField(
        default=False, 
        help_text="Si se marca, permite al estudiante realizar un intento adicional."
    )

    def save(self, *args, **kwargs):
        if not self.institucion_id:
            self.institucion = self.cuestionario.institucion
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Intento de {self.estudiante} en {self.cuestionario.titulo}"

class RespuestaEstudiante(models.Model):
    """
    Guarda la respuesta específica de un estudiante a una pregunta en un intento.
    """
    intento = models.ForeignKey(IntentoCuestionario, on_delete=models.CASCADE, related_name='respuestas')
    pregunta = models.ForeignKey(PreguntaCuestionario, on_delete=models.CASCADE)
    # Para opción única, selección múltiple y V/F
    opciones_seleccionadas = models.ManyToManyField(OpcionPregunta, blank=True)
    # Para texto libre
    texto_respuesta = models.TextField(blank=True, null=True)
    # Para emparejamiento, guardamos un JSON con los pares
    respuesta_emparejamiento = models.JSONField(null=True, blank=True)
    puntaje_obtenido = models.FloatField(default=0)
    porcentaje_similitud = models.PositiveIntegerField(
        null=True, blank=True, 
        verbose_name="Porcentaje de Similitud (%)"
    )
    alerta_plagio = models.BooleanField(
        default=False, 
        verbose_name="Alerta de Posible Plagio"
    )

    def __str__(self):
        return f"Respuesta a '{self.pregunta}' en intento {self.intento.id}"     


        
        