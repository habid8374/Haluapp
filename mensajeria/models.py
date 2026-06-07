"""
mensajeria/models.py
====================
Módulo de mensajería directa bidireccional docente ↔ familiar.

Diseño multi-tenant: toda conversación está ligada a InstitucionEducativa.
Regla de privacidad: un familiar solo puede escribir a docentes que enseñan
a alguno de sus estudiantes asociados (validado en las vistas).
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class Conversacion(models.Model):
    """
    Hilo de conversación entre exactamente dos usuarios:
    - participante_a: docente o coordinador
    - participante_b: familiar

    unique_together garantiza que no existan dos hilos sobre el mismo alumno
    entre las mismas personas.
    """
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa',
        on_delete=models.CASCADE,
        related_name='conversaciones',
        verbose_name='Institución',
    )
    participante_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversaciones_como_a',
        verbose_name='Docente / Coordinador',
    )
    participante_b = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversaciones_como_b',
        verbose_name='Familiar',
    )
    # Contexto opcional: el estudiante que origina la conversación
    estudiante_contexto = models.ForeignKey(
        'gestion_academica.Estudiante',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversaciones',
        verbose_name='Estudiante (contexto)',
    )

    creada_en = models.DateTimeField(auto_now_add=True)
    # Se actualiza cada vez que llega un mensaje — sirve para ordenar el inbox
    ultimo_mensaje_en = models.DateTimeField(default=timezone.now, db_index=True)

    # Archivado independiente por participante
    archivada_por_a = models.BooleanField(default=False)
    archivada_por_b = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Conversación'
        verbose_name_plural = 'Conversaciones'
        ordering = ['-ultimo_mensaje_en']
        unique_together = [('participante_a', 'participante_b', 'estudiante_contexto')]
        permissions = [
            ('puede_supervisar_mensajes', 'Puede ver todos los mensajes de la institución (coordinador/admin)'),
        ]

    def __str__(self):
        return (
            f"{self.participante_a.get_full_name()} ↔ "
            f"{self.participante_b.get_full_name()}"
        )

    def get_otro_participante(self, usuario):
        """Devuelve el participante que NO es el usuario dado."""
        if usuario.pk == self.participante_a_id:
            return self.participante_b
        return self.participante_a

    def no_leidos_para(self, usuario):
        """Cuenta de mensajes no leídos para el usuario dado."""
        return self.mensajes.filter(leido=False).exclude(remitente=usuario).count()

    def esta_archivada_para(self, usuario):
        if usuario.pk == self.participante_a_id:
            return self.archivada_por_a
        return self.archivada_por_b


class Mensaje(models.Model):
    """
    Mensaje individual dentro de una Conversacion.
    Con solo 2 participantes un booleano `leido` es suficiente.
    """
    conversacion = models.ForeignKey(
        Conversacion,
        on_delete=models.CASCADE,
        related_name='mensajes',
        verbose_name='Conversación',
    )
    remitente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='mensajes_enviados',
        verbose_name='Remitente',
    )
    texto = models.TextField(
        max_length=2000,
        verbose_name='Texto del mensaje',
    )
    adjunto = models.FileField(
        upload_to='mensajeria/adjuntos/%Y/%m/',
        null=True,
        blank=True,
        verbose_name='Archivo adjunto',
    )
    enviado_en = models.DateTimeField(auto_now_add=True, db_index=True)
    leido = models.BooleanField(default=False, verbose_name='Leído')
    leido_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Mensaje'
        verbose_name_plural = 'Mensajes'
        ordering = ['enviado_en']

    def __str__(self):
        return f"[{self.conversacion}] {self.remitente.get_full_name()}: {self.texto[:40]}"

    def marcar_leido(self):
        if not self.leido:
            self.leido = True
            self.leido_en = timezone.now()
            self.save(update_fields=['leido', 'leido_en'])
