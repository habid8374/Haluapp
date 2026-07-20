"""
Sopa de letras — actividad calificable por curso.

El docente escribe una lista de palabras; el sistema arma la sopa automáticamente
(coloca las palabras en varias direcciones y rellena con letras al azar). El
estudiante encuentra cada palabra marcando su primera y última letra; el sistema
autocorrige y la nota fluye al libro de notas.

Multi-institución: TODO se filtra por `institucion`.
"""
from django.conf import settings
from django.db import models


class Sopa(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', 'Borrador'
        PUBLICADO = 'PUBLICADO', 'Publicado'
        CERRADO = 'CERRADO', 'Cerrado'

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='sopas_letras', verbose_name="Institución",
    )
    curso = models.ForeignKey(
        'gestion_academica.Curso', on_delete=models.CASCADE,
        related_name='sopas_letras', verbose_name="Curso",
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
        on_delete=models.SET_NULL, related_name='sopa_letras',
    )

    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.BORRADOR,
        verbose_name="Estado",
    )
    # Ventana de disponibilidad para los estudiantes (opcional).
    fecha_inicio = models.DateTimeField(null=True, blank=True, verbose_name="Disponible desde")
    fecha_fin = models.DateTimeField(null=True, blank=True, verbose_name="Plazo final")
    fecha_cierre = models.DateTimeField(null=True, blank=True, verbose_name="Cierre")

    # Cuadrícula generada (se calcula al publicar). grid = lista de filas (strings).
    tamano = models.PositiveIntegerField(default=0)
    grid = models.JSONField(default=list, blank=True)

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='sopas_creadas',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = "Sopa de letras"
        verbose_name_plural = "Sopas de letras"

    def __str__(self):
        return f"{self.titulo} ({self.get_estado_display()})"

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


class PalabraSopa(models.Model):
    sopa = models.ForeignKey(Sopa, on_delete=models.CASCADE, related_name='palabras')
    texto = models.CharField(max_length=40, verbose_name="Palabra")
    orden = models.PositiveIntegerField(default=0)

    # Ubicación en la cuadrícula (tras generar). df/dc = dirección (delta fila/col).
    fila = models.IntegerField(null=True, blank=True)
    columna = models.IntegerField(null=True, blank=True)
    df = models.IntegerField(null=True, blank=True)
    dc = models.IntegerField(null=True, blank=True)

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = "Palabra de sopa"
        verbose_name_plural = "Palabras de sopa"

    def __str__(self):
        return self.texto


class IntentoSopa(models.Model):
    sopa = models.ForeignKey(Sopa, on_delete=models.CASCADE, related_name='intentos')
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)
    estudiante = models.ForeignKey(
        'gestion_academica.Estudiante', on_delete=models.CASCADE,
        related_name='intentos_sopa',
    )
    completado = models.BooleanField(default=False)
    encontradas = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    puntaje = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    # Selecciones enviadas: [{"r1","c1","r2","c2"}, ...]
    selecciones = models.JSONField(default=list, blank=True)
    inicio = models.DateTimeField(auto_now_add=True)
    fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('sopa', 'estudiante')
        ordering = ['-inicio']
        verbose_name = "Intento de sopa"
        verbose_name_plural = "Intentos de sopa"

    def __str__(self):
        return f"Intento {self.estudiante_id} — sopa {self.sopa_id}"
