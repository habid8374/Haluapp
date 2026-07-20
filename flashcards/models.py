"""
Flash Cards — actividad calificable por curso (respuesta escrita).

Cada tarjeta tiene: una imagen (opcional), una descripción/pista que guía al
estudiante, un audio de guía opcional (grabado en la plataforma) y la
RESPUESTA correcta. El estudiante ve la imagen y la pista, escucha el audio si
lo hay, y ESCRIBE la respuesta en una caja de texto. El servidor la corrige al
instante (ignorando mayúsculas y tildes) — la respuesta correcta nunca viaja
al navegador antes de responder, así que no se puede hacer trampa.

La nota (% de aciertos sobre la nota máxima) fluye al libro de notas.

Multi-institución: TODO se filtra por `institucion`.
"""
from django.conf import settings
from django.db import models


class MazoFlashcard(models.Model):
    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', 'Borrador'
        PUBLICADO = 'PUBLICADO', 'Publicado'
        CERRADO = 'CERRADO', 'Cerrado'

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='mazos_flashcards', verbose_name="Institución",
    )
    curso = models.ForeignKey(
        'gestion_academica.Curso', on_delete=models.CASCADE,
        related_name='mazos_flashcards', verbose_name="Curso",
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
        on_delete=models.SET_NULL, related_name='mazo_flashcard',
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
        related_name='mazos_flashcards_creados',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = "Mazo de flash cards"
        verbose_name_plural = "Mazos de flash cards"

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


class TarjetaFlashcard(models.Model):
    mazo = models.ForeignKey(
        MazoFlashcard, on_delete=models.CASCADE, related_name='tarjetas',
    )
    orden = models.PositiveIntegerField(default=0)
    imagen = models.ImageField(upload_to='flashcards/imagenes/', null=True, blank=True)
    pista = models.CharField(max_length=300, verbose_name="Descripción / pista")
    audio = models.FileField(upload_to='flashcards/audios/', null=True, blank=True)
    respuesta = models.CharField(max_length=80, verbose_name="Respuesta correcta")

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = "Flash card"
        verbose_name_plural = "Flash cards"

    def __str__(self):
        return f"{self.pista[:40]} → {self.respuesta}"


class IntentoFlashcard(models.Model):
    mazo = models.ForeignKey(
        MazoFlashcard, on_delete=models.CASCADE, related_name='intentos',
    )
    institucion = models.ForeignKey('finanzas.InstitucionEducativa', on_delete=models.CASCADE)
    estudiante = models.ForeignKey(
        'gestion_academica.Estudiante', on_delete=models.CASCADE,
        related_name='intentos_flashcards',
    )
    completado = models.BooleanField(default=False)
    aciertos = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    porcentaje = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    puntaje = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    # {tarjeta_id: {"r": "lo que escribió", "ok": true/false}}
    respuestas = models.JSONField(default=dict, blank=True)
    inicio = models.DateTimeField(auto_now_add=True)
    fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('mazo', 'estudiante')
        ordering = ['-inicio']
        verbose_name = "Intento de flash cards"
        verbose_name_plural = "Intentos de flash cards"

    def __str__(self):
        return f"Intento {self.estudiante_id} — mazo {self.mazo_id}"
