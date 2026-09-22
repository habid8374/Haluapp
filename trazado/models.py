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
from django.utils.translation import gettext_lazy as _


class TableroTrazado(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', _('Borrador')
        PUBLICADO = 'PUBLICADO', _('Publicado')
        CERRADO = 'CERRADO', _('Cerrado')

    class EstiloLetra(models.TextChoices):
        CURSIVA = 'CURSIVA', _('Cursiva (ligada)')
        IMPRENTA = 'IMPRENTA', _('Imprenta (palo)')

    estilo_letra = models.CharField(
        max_length=10, choices=EstiloLetra.choices, default=EstiloLetra.CURSIVA,
        verbose_name=_("Tipo de letra de la guía"),
    )

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='tableros_trazado', verbose_name=_("Institución"),
    )
    curso = models.ForeignKey(
        'gestion_academica.Curso', on_delete=models.CASCADE,
        related_name='tableros_trazado', verbose_name=_("Curso"),
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
        on_delete=models.SET_NULL, related_name='tablero_trazado',
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
        related_name='tableros_trazado_creados',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = _("Tablero de trazado")
        verbose_name_plural = _("Tableros de trazado")

    def __str__(self):
        return f"{self.titulo} ({self.get_estado_display()})"

    def estado_disponibilidad(self):
        from django.utils import timezone
        if self.estado != self.Estado.PUBLICADO:
            return ('cerrado', _('No disponible'))
        ahora = timezone.now()
        if self.fecha_inicio and ahora < self.fecha_inicio:
            fecha = timezone.localtime(self.fecha_inicio).strftime('%d/%m/%Y %H:%M')
            return ('proximo', _("Disponible desde el %(fecha)s") % {'fecha': fecha})
        if self.fecha_fin and ahora > self.fecha_fin:
            fecha = timezone.localtime(self.fecha_fin).strftime('%d/%m/%Y %H:%M')
            return ('vencido', _("El plazo venció el %(fecha)s") % {'fecha': fecha})
        return ('disponible', _('Disponible'))


class PlantillaTrazado(models.Model):
    tablero = models.ForeignKey(
        TableroTrazado, on_delete=models.CASCADE, related_name='plantillas',
    )
    orden = models.PositiveIntegerField(default=0)
    texto = models.CharField(max_length=20, verbose_name=_("Letra o palabra a trazar"))
    audio = models.FileField(upload_to='trazado/audios/', null=True, blank=True)

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = _("Plantilla de trazado")
        verbose_name_plural = _("Plantillas de trazado")

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
        verbose_name = _("Intento de trazado")
        verbose_name_plural = _("Intentos de trazado")

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
        verbose_name = _("Trazo del estudiante")
        verbose_name_plural = _("Trazos del estudiante")

    def __str__(self):
        return f"Trazo {self.plantilla_id} (intento {self.intento_id})"
