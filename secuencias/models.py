"""
Ordenar Secuencias — actividad calificable por curso (arrastre táctil).

El docente arma una secuencia de tarjetas (imagen/texto) en el orden correcto
(ej. el ciclo de la planta, los números, los momentos del día). El estudiante
las ve desordenadas y las arrastra a las casillas 1..N. Se corrige en el
servidor comparando la posición donde quedó cada tarjeta con su posición
correcta (que nunca viaja al navegador). La nota fluye al libro de notas.

Multi-institución: TODO se filtra por `institucion`.
"""
from django.conf import settings
from django.db import models


class SecuenciaActividad(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', 'Borrador'
        PUBLICADO = 'PUBLICADO', 'Publicado'
        CERRADO = 'CERRADO', 'Cerrado'

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='secuencias', verbose_name="Institución",
    )
    curso = models.ForeignKey(
        'gestion_academica.Curso', on_delete=models.CASCADE,
        related_name='secuencias', verbose_name="Curso",
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
        on_delete=models.SET_NULL, related_name='secuencia',
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
        related_name='secuencias_creadas',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = "Secuencia"
        verbose_name_plural = "Secuencias"

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


class ItemSecuencia(models.Model):
    actividad = models.ForeignKey(
        SecuenciaActividad, on_delete=models.CASCADE, related_name='items',
    )
    posicion_correcta = models.PositiveIntegerField(verbose_name="Posición correcta")
    imagen = models.ImageField(upload_to='secuencias/imagenes/', null=True, blank=True)
    texto = models.CharField(max_length=60, blank=True, default='')

    class Meta:
        ordering = ['posicion_correcta', 'id']
        verbose_name = "Elemento de secuencia"
        verbose_name_plural = "Elementos de secuencia"

    def __str__(self):
        return f"#{self.posicion_correcta} — actividad {self.actividad_id}"


class IntentoSecuencia(models.Model):
    actividad = models.ForeignKey(
        SecuenciaActividad, on_delete=models.CASCADE, related_name='intentos',
    )
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)
    estudiante = models.ForeignKey(
        'gestion_academica.Estudiante', on_delete=models.CASCADE,
        related_name='intentos_secuencia',
    )
    completado = models.BooleanField(default=False)
    aciertos = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    puntaje = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    # {slot: item_id} tal como lo dejó el estudiante
    respuestas = models.JSONField(default=dict, blank=True)
    inicio = models.DateTimeField(auto_now_add=True)
    fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('actividad', 'estudiante')
        ordering = ['-inicio']
        verbose_name = "Intento de secuencia"
        verbose_name_plural = "Intentos de secuencia"

    def __str__(self):
        return f"Intento {self.estudiante_id} — actividad {self.actividad_id}"
