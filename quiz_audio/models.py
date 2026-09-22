"""
Quiz de Audio ("Escucha y Elige") — actividad calificable por curso.

Pensado para primer grado / comprensión auditiva. Cada pregunta tiene un audio
(grabado en la plataforma o subido) y varias opciones con imagen; el niño
escucha y toca la imagen correcta. Se corrige en el servidor (la opción
correcta nunca viaja al navegador). La nota fluye al libro de notas.

Multi-institución: TODO se filtra por `institucion`.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class QuizAudio(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', _('Borrador')
        PUBLICADO = 'PUBLICADO', _('Publicado')
        CERRADO = 'CERRADO', _('Cerrado')

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='quices_audio', verbose_name=_("Institución"),
    )
    curso = models.ForeignKey(
        'gestion_academica.Curso', on_delete=models.CASCADE,
        related_name='quices_audio', verbose_name=_("Curso"),
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
        on_delete=models.SET_NULL, related_name='quiz_audio',
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
        related_name='quices_audio_creados',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = _("Quiz de audio")
        verbose_name_plural = _("Quices de audio")

    def __str__(self):
        return f"{self.titulo} ({self.get_estado_display()})"

    def estado_disponibilidad(self):
        from django.utils import timezone
        if self.estado != self.Estado.PUBLICADO:
            return ('cerrado', _('No disponible'))
        ahora = timezone.now()
        if self.fecha_inicio and ahora < self.fecha_inicio:
            return ('proximo', _("Disponible desde el %(fecha)s") % {
                'fecha': f"{timezone.localtime(self.fecha_inicio):%d/%m/%Y %H:%M}",
            })
        if self.fecha_fin and ahora > self.fecha_fin:
            return ('vencido', _("El plazo venció el %(fecha)s") % {
                'fecha': f"{timezone.localtime(self.fecha_fin):%d/%m/%Y %H:%M}",
            })
        return ('disponible', _('Disponible'))


class PreguntaAudio(models.Model):
    quiz = models.ForeignKey(QuizAudio, on_delete=models.CASCADE, related_name='preguntas')
    orden = models.PositiveIntegerField(default=0)
    audio = models.FileField(upload_to='quiz_audio/audios/')
    enunciado = models.CharField(max_length=200, blank=True, default='', verbose_name=_("Texto (opcional)"))

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = _("Pregunta de audio")
        verbose_name_plural = _("Preguntas de audio")

    def __str__(self):
        return f"Pregunta {self.orden} — quiz {self.quiz_id}"


class OpcionAudio(models.Model):
    pregunta = models.ForeignKey(PreguntaAudio, on_delete=models.CASCADE, related_name='opciones')
    orden = models.PositiveIntegerField(default=0)
    imagen = models.ImageField(upload_to='quiz_audio/imagenes/', null=True, blank=True)
    texto = models.CharField(max_length=60, blank=True, default='')
    es_correcta = models.BooleanField(default=False)

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = _("Opción de audio")
        verbose_name_plural = _("Opciones de audio")

    def __str__(self):
        return f"Opción {self.orden} (pregunta {self.pregunta_id})"


class IntentoQuizAudio(models.Model):
    quiz = models.ForeignKey(QuizAudio, on_delete=models.CASCADE, related_name='intentos')
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)
    estudiante = models.ForeignKey(
        'gestion_academica.Estudiante', on_delete=models.CASCADE,
        related_name='intentos_quiz_audio',
    )
    completado = models.BooleanField(default=False)
    aciertos = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    puntaje = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    # {pregunta_id: {"op": opcion_id, "ok": bool}}
    respuestas = models.JSONField(default=dict, blank=True)
    inicio = models.DateTimeField(auto_now_add=True)
    fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('quiz', 'estudiante')
        ordering = ['-inicio']
        verbose_name = _("Intento de quiz de audio")
        verbose_name_plural = _("Intentos de quiz de audio")

    def __str__(self):
        return f"Intento {self.estudiante_id} — quiz {self.quiz_id}"
