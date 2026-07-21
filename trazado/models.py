"""
Pizarra de Trazado de Letras — actividad por curso (canvas interactivo).

El docente arma un tablero con letras/números/palabras para trazar; cada
plantilla muestra el texto en gris claro como guía y el niño dibuja encima con
el dedo. Al terminar cada trazo se guarda como imagen para que el docente lo
revise. Como el trazo es subjetivo, la nota es por COMPLETAR (terminar todas las
plantillas = nota máxima); el docente puede ajustar en el libro tras revisar los
dibujos.

Multi-institución: TODO se filtra por `institucion`.
"""
from django.conf import settings
from django.db import models


class TableroTrazado(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', 'Borrador'
        PUBLICADO = 'PUBLICADO', 'Publicado'
        CERRADO = 'CERRADO', 'Cerrado'

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='tableros_trazado', verbose_name="Institución",
    )
    curso = models.ForeignKey(
        'gestion_academica.Curso', on_delete=models.CASCADE,
        related_name='tableros_trazado', verbose_name="Curso",
    )
    titulo = models.CharField(max_length=200, verbose_name="Título")
    instrucciones = models.TextField(blank=True, default='', verbose_name="Instrucciones")

    tipo_actividad = models.ForeignKey(
        'gestion_academica.TipoActividad', on_delete=models.PROTECT,
        verbose_name="Categoría (para el libro de notas)",
    )
    nota_maxima = models.DecimalField(
        max_digits=4, decimal_places=2, default=5.0, verbose_name="Nota máxima",
    )
    actividad_calificable = models.OneToOneField(
        'gestion_academica.ActividadCalificable', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='tablero_trazado',
    )

    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.BORRADOR,
        verbose_name="Estado",
    )
    fecha_inicio = models.DateTimeField(null=True, blank=True, verbose_name="Disponible desde")
    fecha_fin = models.DateTimeField(null=True, blank=True, verbose_name="Plazo final")
    fecha_cierre = models.DateTimeField(null=True, blank=True, verbose_name="Cierre")

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='tableros_trazado_creados',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = "Tablero de trazado"
        verbose_name_plural = "Tableros de trazado"

    def __str__(self):
        return f"{self.titulo} ({self.get_estado_display()})"

    def estado_disponibilidad(self):
        from django.utils import timezone
        if self.estado != self.Estado.PUBLICADO:
            return ('cerrado', 'No disponible')
        ahora = timezone.now()
        if self.fecha_inicio and ahora < self.fecha_inicio:
            return ('proximo', f"Disponible desde el {timezone.localtime(self.fecha_inicio):%d/%m/%Y %H:%M}")
        if self.fecha_fin and ahora > self.fecha_fin:
            return ('vencido', f"El plazo venció el {timezone.localtime(self.fecha_fin):%d/%m/%Y %H:%M}")
        return ('disponible', 'Disponible')


class PlantillaTrazado(models.Model):
    tablero = models.ForeignKey(
        TableroTrazado, on_delete=models.CASCADE, related_name='plantillas',
    )
    orden = models.PositiveIntegerField(default=0)
    texto = models.CharField(max_length=20, verbose_name="Letra o palabra a trazar")
    audio = models.FileField(upload_to='trazado/audios/', null=True, blank=True)

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = "Plantilla de trazado"
        verbose_name_plural = "Plantillas de trazado"

    def __str__(self):
        return f"{self.texto} (tablero {self.tablero_id})"


class IntentoTrazado(models.Model):
    tablero = models.ForeignKey(
        TableroTrazado, on_delete=models.CASCADE, related_name='intentos',
    )
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)
    estudiante = models.ForeignKey(
        'gestion_academica.Estudiante', on_delete=models.CASCADE,
        related_name='intentos_trazado',
    )
    completado = models.BooleanField(default=False)
    total = models.PositiveIntegerField(default=0)
    hechas = models.PositiveIntegerField(default=0)
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    puntaje = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    inicio = models.DateTimeField(auto_now_add=True)
    fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('tablero', 'estudiante')
        ordering = ['-inicio']
        verbose_name = "Intento de trazado"
        verbose_name_plural = "Intentos de trazado"

    def __str__(self):
        return f"Intento {self.estudiante_id} — tablero {self.tablero_id}"


class TrazoEstudiante(models.Model):
    """El dibujo que hizo el estudiante sobre una plantilla."""
    intento = models.ForeignKey(IntentoTrazado, on_delete=models.CASCADE, related_name='trazos')
    plantilla = models.ForeignKey(PlantillaTrazado, on_delete=models.CASCADE)
    imagen = models.ImageField(upload_to='trazado/trazos/')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('intento', 'plantilla')
        verbose_name = "Trazo del estudiante"
        verbose_name_plural = "Trazos del estudiante"

    def __str__(self):
        return f"Trazo {self.plantilla_id} (intento {self.intento_id})"
