"""Modelos del módulo Simulacros Saber (ICFES / Pruebas Saber).

Arquitectura multi-institución:
  * BancoPregunta con institucion=NULL + es_publica=True → preguntas de la plataforma, visibles para todas.
  * BancoPregunta con institucion=X → preguntas privadas de esa institución.
  * Simulacro siempre tiene institucion (pertenece a una institución específica).
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class BancoPregunta(models.Model):

    class GradoNivel(models.TextChoices):
        GRADO_3  = "GRADO_3",  "Saber 3°"
        GRADO_5  = "GRADO_5",  "Saber 5°"
        GRADO_7  = "GRADO_7",  "Saber 7°"
        GRADO_9  = "GRADO_9",  "Saber 9°"
        GRADO_11 = "GRADO_11", "Saber 11°"

    class Area(models.TextChoices):
        LECTURA_CRITICA    = "LECTURA_CRITICA",    "Lectura Crítica"
        MATEMATICAS        = "MATEMATICAS",        "Matemáticas"
        CIENCIAS_NATURALES = "CIENCIAS_NATURALES", "Ciencias Naturales"
        SOCIALES           = "SOCIALES",           "Ciencias Sociales y Ciudadanas"
        INGLES             = "INGLES",             "Inglés"
        LENGUAJE           = "LENGUAJE",           "Lenguaje"
        FILOSOFIA          = "FILOSOFIA",          "Filosofía"

    class Dificultad(models.TextChoices):
        BASICO = "BASICO", "Básico"
        MEDIO  = "MEDIO",  "Medio"
        ALTO   = "ALTO",   "Alto"

    # Multi-tenant: null = pública de la plataforma
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='banco_preguntas',
        verbose_name="Institución",
    )
    es_publica = models.BooleanField(
        default=False,
        verbose_name="Pregunta pública",
        help_text="Visible para todas las instituciones (preguntas de la plataforma)",
    )

    grado_nivel       = models.CharField(max_length=10, choices=GradoNivel.choices, verbose_name="Prueba / Grado")
    area              = models.CharField(max_length=20, choices=Area.choices, verbose_name="Área")
    competencia       = models.CharField(max_length=120, blank=True, verbose_name="Competencia")
    componente        = models.CharField(max_length=120, blank=True, verbose_name="Componente")
    enunciado         = models.TextField(verbose_name="Enunciado")
    imagen_url        = models.URLField(blank=True, verbose_name="URL imagen (opcional)")
    nivel_dificultad  = models.CharField(max_length=10, choices=Dificultad.choices, default=Dificultad.MEDIO, verbose_name="Dificultad")
    explicacion       = models.TextField(blank=True, verbose_name="Explicación de la respuesta")
    fuente            = models.CharField(max_length=200, blank=True, verbose_name="Fuente", help_text="Ej: ICFES Saber 11 2019-1")

    creado_por    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='preguntas_creadas')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pregunta del Banco"
        verbose_name_plural = "Banco de Preguntas"
        ordering = ['grado_nivel', 'area', 'pk']

    def __str__(self):
        return f"[{self.get_grado_nivel_display()} · {self.get_area_display()}] {self.enunciado[:70]}"

    @property
    def opcion_correcta(self):
        return self.opciones.filter(es_correcta=True).first()


class OpcionPregunta(models.Model):

    class Letra(models.TextChoices):
        A = "A", "A"
        B = "B", "B"
        C = "C", "C"
        D = "D", "D"

    pregunta   = models.ForeignKey(BancoPregunta, on_delete=models.CASCADE, related_name='opciones')
    letra      = models.CharField(max_length=1, choices=Letra.choices)
    texto      = models.TextField(verbose_name="Texto")
    es_correcta = models.BooleanField(default=False)

    class Meta:
        ordering = ['letra']
        unique_together = [['pregunta', 'letra']]

    def __str__(self):
        return f"{self.letra}. {self.texto[:60]}"


class Simulacro(models.Model):

    class Estado(models.TextChoices):
        BORRADOR   = "BORRADOR",   "Borrador"
        PUBLICADO  = "PUBLICADO",  "Publicado"
        CERRADO    = "CERRADO",    "Cerrado"

    institucion    = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE, related_name='simulacros')
    docente        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='simulacros_creados')
    titulo         = models.CharField(max_length=200, verbose_name="Título")
    descripcion    = models.TextField(blank=True, verbose_name="Instrucciones")
    grado_nivel    = models.CharField(max_length=10, choices=BancoPregunta.GradoNivel.choices, verbose_name="Dirigido a")
    tiempo_minutos = models.PositiveIntegerField(default=60, verbose_name="Tiempo (min)")
    fecha_inicio   = models.DateTimeField(verbose_name="Disponible desde")
    fecha_cierre   = models.DateTimeField(verbose_name="Cierra el")
    preguntas      = models.ManyToManyField(BancoPregunta, through='PreguntaSimulacro', blank=True)
    estado         = models.CharField(max_length=10, choices=Estado.choices, default=Estado.BORRADOR)
    mostrar_respuestas = models.BooleanField(default=True, verbose_name="Mostrar respuestas al terminar")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Simulacro"
        verbose_name_plural = "Simulacros"
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"{self.titulo} [{self.get_estado_display()}]"

    @property
    def total_preguntas(self):
        return self.preguntas.count()

    def esta_disponible(self):
        ahora = timezone.now()
        return self.estado == self.Estado.PUBLICADO and self.fecha_inicio <= ahora <= self.fecha_cierre


class PreguntaSimulacro(models.Model):
    simulacro = models.ForeignKey(Simulacro, on_delete=models.CASCADE)
    pregunta  = models.ForeignKey(BancoPregunta, on_delete=models.CASCADE)
    orden     = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden']
        unique_together = [['simulacro', 'pregunta']]


class IntentoSimulacro(models.Model):
    simulacro    = models.ForeignKey(Simulacro, on_delete=models.CASCADE, related_name='intentos')
    estudiante   = models.ForeignKey('gestion_academica.Estudiante', on_delete=models.CASCADE, related_name='intentos_simulacro')
    institucion  = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)
    inicio       = models.DateTimeField(auto_now_add=True)
    fin          = models.DateTimeField(null=True, blank=True)
    puntaje      = models.FloatField(null=True, blank=True, verbose_name="Puntaje (%)")
    completado   = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Intento de Simulacro"
        ordering = ['-inicio']
        unique_together = [['simulacro', 'estudiante']]

    def calcular_y_guardar_puntaje(self):
        total = self.respuestas.count()
        correctas = self.respuestas.filter(es_correcta=True).count()
        self.puntaje = round((correctas / total * 100), 1) if total else 0
        self.completado = True
        self.fin = timezone.now()
        self.save(update_fields=['puntaje', 'completado', 'fin'])
        return self.puntaje


class RespuestaSimulacro(models.Model):
    intento        = models.ForeignKey(IntentoSimulacro, on_delete=models.CASCADE, related_name='respuestas')
    pregunta       = models.ForeignKey(BancoPregunta, on_delete=models.CASCADE)
    opcion_elegida = models.ForeignKey(OpcionPregunta, on_delete=models.SET_NULL, null=True, blank=True)
    es_correcta    = models.BooleanField(default=False)

    class Meta:
        unique_together = [['intento', 'pregunta']]
