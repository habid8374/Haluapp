# cursos/models.py
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from gestion_academica.models import Estudiante
from finanzas.models import InstitucionEducativa, ConceptoPago

class Curso(models.Model):
    institucion = models.ForeignKey(InstitucionEducativa, on_delete=models.CASCADE, related_name='cursos_virtuales')
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField()
    imagen_portada = models.ImageField(upload_to='cursos/portadas/', null=True, blank=True)
    precio = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    duracion_horas = models.PositiveIntegerField(default=0, help_text="Duración en horas para el certificado")
    # Vinculamos con finanzas para saber qué cobrar
    concepto_pago_asociado = models.ForeignKey(ConceptoPago, on_delete=models.SET_NULL, null=True, blank=True)
    publicado = models.BooleanField(default=False)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre

class Modulo(models.Model):
    curso = models.ForeignKey(Curso, related_name='modulos', on_delete=models.CASCADE)
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    orden = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['orden']

    def __str__(self):
        return f"{self.curso.nombre} - {self.titulo}"

class Material(models.Model):
    TIPO_CHOICES = (
        ('PDF', 'Documento PDF'),
        ('VIDEO', 'Video YouTube'),
        ('ENLACE', 'Enlace Externo'),
    )
    modulo = models.ForeignKey(Modulo, related_name='materiales', on_delete=models.CASCADE)
    titulo = models.CharField(max_length=200)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    archivo = models.FileField(upload_to='cursos/materiales/', null=True, blank=True)
    enlace = models.URLField(null=True, blank=True, help_text="URL del video de YouTube o enlace externo")
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden']

class Evaluacion(models.Model):
    modulo = models.OneToOneField(Modulo, related_name='evaluacion', on_delete=models.CASCADE)
    titulo = models.CharField(max_length=200)
    porcentaje_aprobacion = models.PositiveIntegerField(default=60, help_text="Puntaje mínimo de 0 a 100 para aprobar")
    intentos_permitidos = models.PositiveIntegerField(default=3, help_text="0 para ilimitados")

class Pregunta(models.Model):
    evaluacion = models.ForeignKey(Evaluacion, related_name='preguntas', on_delete=models.CASCADE)
    texto = models.TextField()
    puntos = models.PositiveIntegerField(default=10)

class Opcion(models.Model):
    pregunta = models.ForeignKey(Pregunta, related_name='opciones', on_delete=models.CASCADE)
    texto = models.CharField(max_length=200)
    es_correcta = models.BooleanField(default=False)

# --- Control de Progreso y Acceso ---

class InscripcionCurso(models.Model):
    estudiante = models.ForeignKey(Estudiante, related_name='cursos_inscritos', on_delete=models.CASCADE)
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE)
    fecha_inscripcion = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)
    progreso_porcentaje = models.FloatField(default=0.0)

    def verificar_completado(self):
        # Lógica para verificar si completó todos los módulos y actualizar progreso
        pass
    
    @property
    def estado_avance(self):
        if self.progreso_porcentaje >= 100:
            return "Certificado"
        elif self.progreso_porcentaje > 0:
            return "En Curso"
        return "Pendiente por ingresar"

    class Meta:
        unique_together = ('estudiante', 'curso')

class ProgresoModulo(models.Model):
    inscripcion = models.ForeignKey(InscripcionCurso, related_name='progresos_modulos', on_delete=models.CASCADE)
    modulo = models.ForeignKey(Modulo, on_delete=models.CASCADE)
    completado = models.BooleanField(default=False)
    fecha_completado = models.DateTimeField(null=True, blank=True)
    # Aquí guardamos si pasó la prueba
    aprobado = models.BooleanField(default=False)
    intentos_usados = models.PositiveIntegerField(default=0)
    mejor_nota = models.FloatField(default=0.0)

    class Meta:
        unique_together = ('inscripcion', 'modulo')
