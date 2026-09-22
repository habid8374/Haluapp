"""
Juego de Memoria (parejas / match) — actividad calificable por curso.

El docente crea parejas de tarjetas; cada tarjeta puede ser una imagen o un
texto, y opcionalmente lleva un audio de guía (grabado en la plataforma) que
suena al voltearla — pensado para niños pequeños que aún no leen.

El estudiante voltea tarjetas de a dos hasta encontrar todas las parejas.
La nota se calcula según el modo elegido por el docente:
- COMPLETAR: terminar el juego = nota máxima (ideal preescolar).
- EFICIENCIA: terminar garantiza el 60%; el 40% restante depende de cuántos
  intentos usó (menos volteos = mejor nota).

Multi-institución: TODO se filtra por `institucion`.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class JuegoMemoria(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', _('Borrador')
        PUBLICADO = 'PUBLICADO', _('Publicado')
        CERRADO = 'CERRADO', _('Cerrado')

    class ModoNota(models.TextChoices):
        COMPLETAR = 'COMPLETAR', _('Completar el juego = nota máxima')
        EFICIENCIA = 'EFICIENCIA', _('Por eficiencia (menos intentos, mejor nota)')

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='juegos_memoria', verbose_name=_("Institución"),
    )
    curso = models.ForeignKey(
        'gestion_academica.Curso', on_delete=models.CASCADE,
        related_name='juegos_memoria', verbose_name=_("Curso"),
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
    modo_nota = models.CharField(
        max_length=12, choices=ModoNota.choices, default=ModoNota.COMPLETAR,
        verbose_name=_("Cómo se califica"),
    )
    actividad_calificable = models.OneToOneField(
        'gestion_academica.ActividadCalificable', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='juego_memoria',
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
        related_name='juegos_memoria_creados',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = _("Juego de memoria")
        verbose_name_plural = _("Juegos de memoria")

    def __str__(self):
        return f"{self.titulo} ({self.get_estado_display()})"

    def estado_disponibilidad(self):
        """('disponible'|'proximo'|'vencido'|'cerrado', mensaje) para el estudiante."""
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


class ParejaMemoria(models.Model):
    """Una pareja: dos tarjetas (A y B). Cada tarjeta es imagen o texto,
    con audio de guía opcional."""
    juego = models.ForeignKey(
        JuegoMemoria, on_delete=models.CASCADE, related_name='parejas',
    )
    orden = models.PositiveIntegerField(default=0)

    imagen_a = models.ImageField(upload_to='memoria/imagenes/', null=True, blank=True)
    texto_a = models.CharField(max_length=60, blank=True, default='')
    audio_a = models.FileField(upload_to='memoria/audios/', null=True, blank=True)

    imagen_b = models.ImageField(upload_to='memoria/imagenes/', null=True, blank=True)
    texto_b = models.CharField(max_length=60, blank=True, default='')
    audio_b = models.FileField(upload_to='memoria/audios/', null=True, blank=True)

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = _("Pareja de memoria")
        verbose_name_plural = _("Parejas de memoria")

    def __str__(self):
        return f"Pareja {self.orden} — juego {self.juego_id}"


class IntentoMemoria(models.Model):
    juego = models.ForeignKey(
        JuegoMemoria, on_delete=models.CASCADE, related_name='intentos',
    )
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)
    estudiante = models.ForeignKey(
        'gestion_academica.Estudiante', on_delete=models.CASCADE,
        related_name='intentos_memoria',
    )
    completado = models.BooleanField(default=False)
    movimientos = models.PositiveIntegerField(default=0, verbose_name=_("Volteos de 2 tarjetas"))
    parejas_total = models.PositiveIntegerField(default=0)
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    puntaje = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    inicio = models.DateTimeField(auto_now_add=True)
    fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('juego', 'estudiante')
        ordering = ['-inicio']
        verbose_name = _("Intento de memoria")
        verbose_name_plural = _("Intentos de memoria")

    def __str__(self):
        return f"Intento {self.estudiante_id} — juego {self.juego_id}"
