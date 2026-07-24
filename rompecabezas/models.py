"""
Rompecabezas — actividad calificable por curso.

El docente sube una imagen y elige la dificultad (filas x columnas); el
recorte de la imagen en piezas se hace 100% en el navegador con CSS
(background-position), sin procesar la imagen en el servidor. El estudiante
arma el rompecabezas tocando dos piezas para intercambiarlas, hasta que
queden en el orden correcto. Como no hay una "respuesta secreta" que
proteger (la imagen se ve completa desde el inicio), la corrección en el
servidor solo confirma que el orden final sea 0..N-1 — nunca se confía en
lo que el navegador diga sobre si "ganó" o no.

Multi-institución: TODO se filtra por `institucion`.
"""
from django.conf import settings
from django.db import models


class Rompecabezas(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', 'Borrador'
        PUBLICADO = 'PUBLICADO', 'Publicado'
        CERRADO = 'CERRADO', 'Cerrado'

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='rompecabezas', verbose_name="Institución",
    )
    curso = models.ForeignKey(
        'gestion_academica.Curso', on_delete=models.CASCADE,
        related_name='rompecabezas', verbose_name="Curso",
    )
    titulo = models.CharField(max_length=200, verbose_name="Título")
    instrucciones = models.TextField(blank=True, default='', verbose_name="Instrucciones")
    imagen = models.ImageField(upload_to='rompecabezas/imagenes/', verbose_name="Imagen")

    filas = models.PositiveIntegerField(default=3, verbose_name="Filas")
    columnas = models.PositiveIntegerField(default=3, verbose_name="Columnas")

    tipo_actividad = models.ForeignKey(
        'gestion_academica.TipoActividad', on_delete=models.PROTECT,
        verbose_name="Categoría (para el libro de notas)",
    )
    nota_maxima = models.DecimalField(
        max_digits=4, decimal_places=2, default=5.0, verbose_name="Nota máxima",
    )
    actividad_calificable = models.OneToOneField(
        'gestion_academica.ActividadCalificable', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='rompecabezas',
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
        related_name='rompecabezas_creados',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = "Rompecabezas"
        verbose_name_plural = "Rompecabezas"

    def __str__(self):
        return f"{self.titulo} ({self.get_estado_display()})"

    @property
    def num_piezas(self):
        return self.filas * self.columnas

    def estado_disponibilidad(self):
        """('disponible'|'proximo'|'vencido'|'cerrado', mensaje) para el estudiante."""
        from django.utils import timezone
        if self.estado != self.Estado.PUBLICADO:
            return ('cerrado', 'No disponible')
        ahora = timezone.now()
        if self.fecha_inicio and ahora < self.fecha_inicio:
            return ('proximo', f"Disponible desde el {timezone.localtime(self.fecha_inicio):%d/%m/%Y %H:%M}")
        if self.fecha_fin and ahora > self.fecha_fin:
            return ('vencido', f"El plazo venció el {timezone.localtime(self.fecha_fin):%d/%m/%Y %H:%M}")
        return ('disponible', 'Disponible')


class IntentoRompecabezas(models.Model):
    rompecabezas = models.ForeignKey(Rompecabezas, on_delete=models.CASCADE, related_name='intentos')
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)
    estudiante = models.ForeignKey(
        'gestion_academica.Estudiante', on_delete=models.CASCADE,
        related_name='intentos_rompecabezas',
    )
    completado = models.BooleanField(default=False)
    movimientos = models.PositiveIntegerField(default=0, verbose_name="Movimientos")
    tiempo_segundos = models.PositiveIntegerField(null=True, blank=True, verbose_name="Tiempo (segundos)")
    puntaje = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    inicio = models.DateTimeField(auto_now_add=True)
    fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('rompecabezas', 'estudiante')
        ordering = ['-inicio']
        verbose_name = "Intento de rompecabezas"
        verbose_name_plural = "Intentos de rompecabezas"

    def __str__(self):
        return f"Intento {self.estudiante_id} — rompecabezas {self.rompecabezas_id}"
