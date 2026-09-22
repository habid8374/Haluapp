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
from django.utils.translation import gettext_lazy as _


class SecuenciaActividad(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', _('Borrador')
        PUBLICADO = 'PUBLICADO', _('Publicado')
        CERRADO = 'CERRADO', _('Cerrado')

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='secuencias', verbose_name=_("Institución"),
    )
    curso = models.ForeignKey(
        'gestion_academica.Curso', on_delete=models.CASCADE,
        related_name='secuencias', verbose_name=_("Curso"),
    )
    titulo = models.CharField(max_length=200, verbose_name=_("Título"))
    instrucciones = models.TextField(blank=True, default='', verbose_name=_("Instrucciones"))

    tipo_actividad = models.ForeignKey(
        'gestion_academica.TipoActividad', on_delete=models.PROTECT,
        verbose_name=_("Categoría (para el libro de notas)"),
    )
    nota_maxima = models.DecimalField(
        max_digits=4, decimal_places=2, default=5.0, verbose_name=_("Nota máxima"),
    )
    actividad_calificable = models.OneToOneField(
        'gestion_academica.ActividadCalificable', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='secuencia',
    )

    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.BORRADOR,
        verbose_name=_("Estado"),
    )
    fecha_inicio = models.DateTimeField(null=True, blank=True, verbose_name=_("Disponible desde"))
    fecha_fin = models.DateTimeField(null=True, blank=True, verbose_name=_("Plazo final"))
    fecha_cierre = models.DateTimeField(null=True, blank=True, verbose_name=_("Cierre"))

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='secuencias_creadas',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = _("Secuencia")
        verbose_name_plural = _("Secuencias")

    def __str__(self):
        return f"{self.titulo} ({self.get_estado_display()})"

    def estado_disponibilidad(self):
        from django.utils import timezone
        if self.estado != self.Estado.PUBLICADO:
            return ('cerrado', _('No disponible'))
        ahora = timezone.now()
        if self.fecha_inicio and ahora < self.fecha_inicio:
            fecha_str = timezone.localtime(self.fecha_inicio).strftime('%d/%m/%Y %H:%M')
            return ('proximo', _("Disponible desde el %(fecha)s") % {'fecha': fecha_str})
        if self.fecha_fin and ahora > self.fecha_fin:
            fecha_str = timezone.localtime(self.fecha_fin).strftime('%d/%m/%Y %H:%M')
            return ('vencido', _("El plazo venció el %(fecha)s") % {'fecha': fecha_str})
        return ('disponible', _('Disponible'))


class ItemSecuencia(models.Model):
    actividad = models.ForeignKey(
        SecuenciaActividad, on_delete=models.CASCADE, related_name='items',
    )
    posicion_correcta = models.PositiveIntegerField(verbose_name=_("Posición correcta"))
    imagen = models.ImageField(upload_to='secuencias/imagenes/', null=True, blank=True)
    texto = models.CharField(max_length=60, blank=True, default='')

    class Meta:
        ordering = ['posicion_correcta', 'id']
        verbose_name = _("Elemento de secuencia")
        verbose_name_plural = _("Elementos de secuencia")

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
        verbose_name = _("Intento de secuencia")
        verbose_name_plural = _("Intentos de secuencia")

    def __str__(self):
        return f"Intento {self.estudiante_id} — actividad {self.actividad_id}"
