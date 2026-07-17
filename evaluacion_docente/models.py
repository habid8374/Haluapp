"""
Evaluación de Desempeño Docente por las familias.

Un colegio lanza una CAMPAÑA por periodo; cada acudiente (Familiar) evalúa a los
docentes que le dan clase a su(s) hijo(s), curso por curso, con una rúbrica de
criterios editables (escala 1–5) y un comentario opcional. La respuesta puede
ser anónima (se oculta la identidad en los reportes, pero el sistema sabe
internamente quién respondió para no pedirla dos veces).

Multi-institución: TODO se filtra por `institucion`. Configurable para servir
tanto a colegios privados (100% familias) como oficiales (donde la encuesta a
familias es un instrumento más del Decreto 1278) — por ahora se implementa el
instrumento de familias.
"""
from django.conf import settings
from django.db import models


class CriterioEvaluacion(models.Model):
    """Pregunta/criterio editable por la institución (escala 1–5)."""
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='criterios_eval_docente', verbose_name="Institución",
    )
    texto = models.CharField(max_length=255, verbose_name="Criterio / pregunta")
    descripcion = models.CharField(
        max_length=255, blank=True, default='', verbose_name="Ayuda (opcional)",
    )
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")
    activo = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = "Criterio de evaluación docente"
        verbose_name_plural = "Criterios de evaluación docente"

    def __str__(self):
        return self.texto


class CampanaEvaluacion(models.Model):
    """Un lanzamiento de evaluación para un periodo académico."""
    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', 'Borrador'
        ABIERTA = 'ABIERTA', 'Abierta'
        CERRADA = 'CERRADA', 'Cerrada'

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='campanas_eval_docente', verbose_name="Institución",
    )
    periodo_academico = models.ForeignKey(
        'gestion_academica.PeriodoAcademico', on_delete=models.PROTECT,
        related_name='campanas_eval_docente', verbose_name="Periodo académico",
    )
    titulo = models.CharField(max_length=200, verbose_name="Título")
    estado = models.CharField(
        max_length=10, choices=Estado.choices, default=Estado.BORRADOR,
        verbose_name="Estado",
    )
    fecha_apertura = models.DateField(null=True, blank=True, verbose_name="Apertura")
    fecha_cierre = models.DateField(null=True, blank=True, verbose_name="Cierre")
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='campanas_eval_creadas',
    )
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creada_en']
        verbose_name = "Campaña de evaluación docente"
        verbose_name_plural = "Campañas de evaluación docente"

    def __str__(self):
        return f"{self.titulo} ({self.get_estado_display()})"

    @property
    def esta_abierta(self):
        return self.estado == self.Estado.ABIERTA


class RespuestaEvaluacion(models.Model):
    """Evaluación de UN acudiente a UN docente en UN curso (para un hijo)."""
    campana = models.ForeignKey(
        CampanaEvaluacion, on_delete=models.CASCADE, related_name='respuestas',
    )
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
    )
    docente = models.ForeignKey(
        'gestion_academica.Docente', on_delete=models.CASCADE,
        related_name='evaluaciones_recibidas',
    )
    curso = models.ForeignKey('gestion_academica.Curso', on_delete=models.CASCADE)
    estudiante = models.ForeignKey('gestion_academica.Estudiante', on_delete=models.CASCADE)
    # Quién respondió (uso interno: dedup + control de participación).
    familiar = models.ForeignKey(
        'gestion_academica.Familiar', on_delete=models.CASCADE,
        related_name='evaluaciones_docente_hechas',
    )
    anonimo = models.BooleanField(default=False, verbose_name="Respuesta anónima")
    comentario = models.TextField(blank=True, default='', verbose_name="Comentario")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Un acudiente evalúa una vez a cada (docente, curso) por hijo y campaña.
        unique_together = ('campana', 'docente', 'curso', 'estudiante', 'familiar')
        indexes = [
            models.Index(fields=['campana', 'docente'], name='evaldoc_camp_doc_idx'),
            models.Index(fields=['institucion', 'campana'], name='evaldoc_inst_camp_idx'),
        ]
        verbose_name = "Respuesta de evaluación docente"
        verbose_name_plural = "Respuestas de evaluación docente"

    def __str__(self):
        return f"Eval docente {self.docente_id} — campaña {self.campana_id}"


class ValoracionCriterio(models.Model):
    """Puntaje 1–5 de un criterio dentro de una respuesta."""
    respuesta = models.ForeignKey(
        RespuestaEvaluacion, on_delete=models.CASCADE, related_name='valoraciones',
    )
    criterio = models.ForeignKey(CriterioEvaluacion, on_delete=models.PROTECT)
    valor = models.PositiveSmallIntegerField(verbose_name="Valor (1–5)")

    class Meta:
        unique_together = ('respuesta', 'criterio')
        verbose_name = "Valoración de criterio"
        verbose_name_plural = "Valoraciones de criterio"

    def __str__(self):
        return f"{self.criterio_id}: {self.valor}"
