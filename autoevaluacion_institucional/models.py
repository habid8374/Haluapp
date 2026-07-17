"""
Autoevaluación Institucional — Guía 34 (Ministerio de Educación Nacional).

El equipo directivo (rector / coordinador) valora la gestión del colegio en las
cuatro áreas de la Guía 34, componente por componente, en la escala oficial 1–4:

    1 · Existencia            2 · Pertinencia
    3 · Apropiación           4 · Mejoramiento continuo

Los componentes se siembran automáticamente con la estructura oficial de la
Guía 34 la primera vez que la institución entra al módulo, y quedan editables
(se pueden agregar, renombrar o desactivar). Sirve tanto para colegios privados
como oficiales.

Multi-institución: TODO se filtra por `institucion`.
"""
from django.conf import settings
from django.db import models


class AreaGestion(models.TextChoices):
    """Las 4 áreas de gestión de la Guía 34."""
    DIRECTIVA = 'DIRECTIVA', 'Gestión Directiva'
    ACADEMICA = 'ACADEMICA', 'Gestión Académica'
    ADMINISTRATIVA = 'ADMINISTRATIVA', 'Gestión Administrativa y Financiera'
    COMUNIDAD = 'COMUNIDAD', 'Gestión de la Comunidad'


# Escala oficial Guía 34 (1–4).
ESCALA_VALORACION = {
    1: 'Existencia',
    2: 'Pertinencia',
    3: 'Apropiación',
    4: 'Mejoramiento continuo',
}


class ComponenteGestion(models.Model):
    """Componente evaluable dentro de un área (editable por la institución)."""
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='componentes_autoeval', verbose_name="Institución",
    )
    area = models.CharField(
        max_length=20, choices=AreaGestion.choices, verbose_name="Área de gestión",
    )
    nombre = models.CharField(max_length=255, verbose_name="Componente")
    descripcion = models.CharField(
        max_length=500, blank=True, default='', verbose_name="Descripción (opcional)",
    )
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")
    activo = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        ordering = ['area', 'orden', 'id']
        verbose_name = "Componente de gestión"
        verbose_name_plural = "Componentes de gestión"

    def __str__(self):
        return f"{self.get_area_display()} — {self.nombre}"


class AutoevaluacionInstitucional(models.Model):
    """Un ejercicio anual de autoevaluación institucional."""
    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', 'Borrador'
        EN_PROCESO = 'EN_PROCESO', 'En proceso'
        CERRADA = 'CERRADA', 'Cerrada'

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='autoevaluaciones', verbose_name="Institución",
    )
    anio = models.PositiveIntegerField(verbose_name="Año")
    titulo = models.CharField(max_length=200, verbose_name="Título")
    estado = models.CharField(
        max_length=12, choices=Estado.choices, default=Estado.BORRADOR,
        verbose_name="Estado",
    )
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='autoevaluaciones_creadas',
    )
    creada_en = models.DateTimeField(auto_now_add=True)
    cerrada_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-anio', '-creada_en']
        verbose_name = "Autoevaluación institucional"
        verbose_name_plural = "Autoevaluaciones institucionales"

    def __str__(self):
        return f"{self.titulo} ({self.anio})"


class ValoracionGestion(models.Model):
    """Valoración 1–4 de un componente dentro de una autoevaluación."""
    autoevaluacion = models.ForeignKey(
        AutoevaluacionInstitucional, on_delete=models.CASCADE,
        related_name='valoraciones',
    )
    componente = models.ForeignKey(ComponenteGestion, on_delete=models.PROTECT)
    # Nula hasta que el equipo directivo la diligencie.
    valor = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Valoración (1–4)")
    observaciones = models.TextField(blank=True, default='', verbose_name="Observaciones / evidencias")
    accion_mejora = models.TextField(blank=True, default='', verbose_name="Acción de mejora")

    class Meta:
        ordering = ['componente__area', 'componente__orden', 'componente__id']
        unique_together = ('autoevaluacion', 'componente')
        verbose_name = "Valoración de gestión"
        verbose_name_plural = "Valoraciones de gestión"

    def __str__(self):
        return f"{self.componente_id}: {self.valor or '—'}"
