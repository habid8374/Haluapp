"""
Crucigramas — actividad calificable por curso.

El docente escribe una lista de palabras con su pista; el sistema arma la
cuadrícula automáticamente (cruzando las palabras donde comparten letras). El
estudiante lo resuelve en pantalla y el sistema lo autocorrige, generando una
nota que fluye al libro de notas (vía ActividadCalificable / Calificacion).

Multi-institución: TODO se filtra por `institucion`.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Crucigrama(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', _('Borrador')
        PUBLICADO = 'PUBLICADO', _('Publicado')
        CERRADO = 'CERRADO', _('Cerrado')

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='crucigramas', verbose_name=_("Institución"),
    )
    curso = models.ForeignKey(
        'gestion_academica.Curso', on_delete=models.CASCADE,
        related_name='crucigramas', verbose_name=_("Curso"),
    )
    titulo = models.CharField(max_length=200, verbose_name=_("Título"))
    instrucciones = models.TextField(blank=True, default='', verbose_name=_("Instrucciones"))

    # Calificación (siempre calificable).
    tipo_actividad = models.ForeignKey(
        'gestion_academica.TipoActividad', on_delete=models.PROTECT,
        verbose_name=_("Categoría (para el libro de notas)"),
    )
    nota_maxima = models.DecimalField(
        max_digits=4, decimal_places=2, default=5.0, verbose_name=_("Nota máxima"),
    )
    # Enlace a la columna del libro de notas (se crea al publicar).
    actividad_calificable = models.OneToOneField(
        'gestion_academica.ActividadCalificable', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='crucigrama',
    )

    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.BORRADOR,
        verbose_name=_("Estado"),
    )
    # Ventana de disponibilidad para los estudiantes (opcional).
    fecha_inicio = models.DateTimeField(null=True, blank=True, verbose_name=_("Disponible desde"))
    fecha_fin = models.DateTimeField(null=True, blank=True, verbose_name=_("Plazo final"))
    fecha_cierre = models.DateTimeField(null=True, blank=True, verbose_name=_("Cierre"))

    # Dimensiones de la cuadrícula (se calculan al generar el layout).
    filas = models.PositiveIntegerField(default=0)
    columnas = models.PositiveIntegerField(default=0)

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='crucigramas_creados',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = _("Crucigrama")
        verbose_name_plural = _("Crucigramas")

    def __str__(self):
        return f"{self.titulo} ({self.get_estado_display()})"

    def estado_disponibilidad(self):
        """('disponible'|'proximo'|'vencido'|'cerrado', mensaje) para el estudiante."""
        from django.utils import timezone
        if self.estado != self.Estado.PUBLICADO:
            return ('cerrado', _('No disponible'))
        ahora = timezone.now()
        if self.fecha_inicio and ahora < self.fecha_inicio:
            return ('proximo', _("Disponible desde el %(fecha)s") % {
                'fecha': timezone.localtime(self.fecha_inicio).strftime('%d/%m/%Y %H:%M'),
            })
        if self.fecha_fin and ahora > self.fecha_fin:
            return ('vencido', _("El plazo venció el %(fecha)s") % {
                'fecha': timezone.localtime(self.fecha_fin).strftime('%d/%m/%Y %H:%M'),
            })
        return ('disponible', _('Disponible'))


class PalabraCrucigrama(models.Model):
    class Direccion(models.TextChoices):
        HORIZONTAL = 'H', _('Horizontal')
        VERTICAL = 'V', _('Vertical')

    crucigrama = models.ForeignKey(
        Crucigrama, on_delete=models.CASCADE, related_name='palabras',
    )
    respuesta = models.CharField(max_length=40, verbose_name=_("Respuesta"))
    pista = models.CharField(max_length=300, verbose_name=_("Pista"))
    imagen = models.ImageField(upload_to='crucigramas/pistas/', null=True, blank=True, verbose_name=_("Imagen de pista (opcional)"))
    orden = models.PositiveIntegerField(default=0)

    # Posición en la cuadrícula (tras generar el layout).
    fila = models.IntegerField(null=True, blank=True)
    columna = models.IntegerField(null=True, blank=True)
    direccion = models.CharField(
        max_length=1, choices=Direccion.choices, null=True, blank=True,
    )
    numero = models.PositiveIntegerField(null=True, blank=True, verbose_name=_("N.º de pista"))

    class Meta:
        ordering = ['numero', 'orden', 'id']
        verbose_name = _("Palabra de crucigrama")
        verbose_name_plural = _("Palabras de crucigrama")

    def __str__(self):
        return f"{self.respuesta} ({self.pista[:30]})"


class IntentoCrucigrama(models.Model):
    crucigrama = models.ForeignKey(
        Crucigrama, on_delete=models.CASCADE, related_name='intentos',
    )
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
    )
    estudiante = models.ForeignKey(
        'gestion_academica.Estudiante', on_delete=models.CASCADE,
        related_name='intentos_crucigrama',
    )
    completado = models.BooleanField(default=False)
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    puntaje = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    aciertos = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    # Respuestas del estudiante: {palabra_id: "TEXTO"}.
    respuestas = models.JSONField(default=dict, blank=True)
    inicio = models.DateTimeField(auto_now_add=True)
    fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('crucigrama', 'estudiante')
        ordering = ['-inicio']
        verbose_name = _("Intento de crucigrama")
        verbose_name_plural = _("Intentos de crucigrama")

    def __str__(self):
        return f"Intento {self.estudiante_id} — crucigrama {self.crucigrama_id}"
