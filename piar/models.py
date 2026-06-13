from django.db import models
from django.conf import settings


class PIAR(models.Model):
    """Plan Individual de Ajustes Razonables (Decreto 1421 de 2017)."""

    class Condicion(models.TextChoices):
        COG = 'COG', 'Cognitiva'
        MOT = 'MOT', 'Motriz'
        VIS = 'VIS', 'Visual'
        AUD = 'AUD', 'Auditiva'
        MUL = 'MUL', 'Múltiple'
        APR = 'APR', 'Trastorno de Aprendizaje'
        CON = 'CON', 'Conductual-TDAH'
        TAL = 'TAL', 'Talentos Excepcionales'
        OTR = 'OTR', 'Otra'

    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', 'Borrador'
        ACTIVO = 'ACTIVO', 'Vigente'
        CERRADO = 'CERRADO', 'Cerrado'

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa',
        on_delete=models.CASCADE,
        related_name='piars',
        verbose_name='Institución',
    )
    estudiante = models.ForeignKey(
        'gestion_academica.Estudiante',
        on_delete=models.CASCADE,
        related_name='piars',
        verbose_name='Estudiante',
    )
    año_lectivo = models.PositiveIntegerField(verbose_name='Año Lectivo')
    grado = models.ForeignKey(
        'gestion_academica.Grado',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Grado',
    )
    condicion = models.CharField(
        max_length=3,
        choices=Condicion.choices,
        verbose_name='Condición',
    )
    condicion_descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción de la condición',
    )
    fortalezas = models.TextField(verbose_name='Fortalezas del estudiante')
    barreras = models.TextField(verbose_name='Barreras para el aprendizaje')
    apoyos = models.TextField(verbose_name='Apoyos requeridos')
    compromisos_familia = models.TextField(blank=True, verbose_name='Compromisos de la familia')
    compromisos_docentes = models.TextField(blank=True, verbose_name='Compromisos de los docentes')
    compromisos_institucion = models.TextField(blank=True, verbose_name='Compromisos de la institución')
    docente_lider = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='piars_liderados',
        verbose_name='Docente Líder',
    )
    fecha_elaboracion = models.DateField(verbose_name='Fecha de Elaboración')
    fecha_revision = models.DateField(null=True, blank=True, verbose_name='Fecha de Revisión')
    estado = models.CharField(
        max_length=10,
        choices=Estado.choices,
        default=Estado.BORRADOR,
        verbose_name='Estado',
    )
    observaciones_generales = models.TextField(blank=True, verbose_name='Observaciones Generales')
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creación')

    class Meta:
        unique_together = [['estudiante', 'año_lectivo']]
        ordering = ['-año_lectivo']
        verbose_name = 'PIAR'
        verbose_name_plural = 'PIARs'

    def __str__(self):
        return f"PIAR {self.año_lectivo} — {self.estudiante}"


class AjustePIAR(models.Model):
    """Ajuste razonable por materia y período académico."""

    PERIODO_CHOICES = [
        (1, 'Período 1'),
        (2, 'Período 2'),
        (3, 'Período 3'),
        (4, 'Período 4'),
    ]

    piar = models.ForeignKey(
        PIAR,
        on_delete=models.CASCADE,
        related_name='ajustes',
        verbose_name='PIAR',
    )
    materia = models.ForeignKey(
        'gestion_academica.Materia',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Materia',
    )
    periodo = models.PositiveSmallIntegerField(
        choices=PERIODO_CHOICES,
        verbose_name='Período Académico',
    )
    logro_ajustado = models.TextField(verbose_name='Logro Ajustado')
    estrategias_flexibles = models.TextField(verbose_name='Estrategias Flexibles')
    ajuste_evaluativo = models.TextField(verbose_name='Ajuste Evaluativo')
    recursos_apoyo = models.TextField(blank=True, verbose_name='Recursos de Apoyo')
    seguimiento = models.TextField(blank=True, verbose_name='Seguimiento')
    alcanzado = models.BooleanField(default=False, verbose_name='¿Logro alcanzado?')

    class Meta:
        ordering = ['periodo', 'materia__nombre_materia']
        verbose_name = 'Ajuste PIAR'
        verbose_name_plural = 'Ajustes PIAR'

    def __str__(self):
        materia_nombre = self.materia.nombre_materia if self.materia else 'Sin materia'
        return f"Ajuste P{self.periodo} — {materia_nombre} ({self.piar})"
