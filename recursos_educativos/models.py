"""
recursos_educativos/models.py
==============================
Modelos para el módulo de Recursos Educativos 3D — Cuerpo Humano.

Multi-institución: TODOS los modelos filtran por `institucion` (FK →
finanzas.InstitucionEducativa) para respetar el aislamiento multi-tenant.

Flujo:
  Docente crea ActividadCalificable (existente) + RecursoEducativo3D (nuevo).
  Estudiante abre el visor → se registra EntregaRecurso3D.
  Al completar el Studio (13/13 piezas) → se escribe Calificacion automáticamente.
"""
import decimal

from django.db import models
from django.utils import timezone


class RecursoEducativo3D(models.Model):
    """
    Extiende una ActividadCalificable existente con el modo del visor 3D.
    El OneToOne garantiza que cada actividad tiene como máximo un recurso 3D.
    """

    MODO_GALERIA = 'galeria'
    MODO_STUDIO  = 'studio'
    MODO_AMBOS   = 'ambos'

    MODO_CHOICES = [
        (MODO_GALERIA, 'Solo Galería'),
        (MODO_STUDIO,  'Solo Studio'),
        (MODO_AMBOS,   'Galería + Studio'),
    ]

    TOTAL_PIEZAS = 13  # Órganos del cuerpo humano incluidos en el Studio

    actividad = models.OneToOneField(
        'gestion_academica.ActividadCalificable',
        on_delete=models.CASCADE,
        related_name='recurso_3d',
        verbose_name='Actividad Calificable',
    )
    modo = models.CharField(
        max_length=10,
        choices=MODO_CHOICES,
        default=MODO_AMBOS,
        verbose_name='Modo del Recurso',
    )
    valor_maximo = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=decimal.Decimal('5.00'),
        verbose_name='Nota Máxima',
        help_text='Nota máxima que puede obtener el estudiante (ej: 5.00)',
    )
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa',
        on_delete=models.CASCADE,
        verbose_name='Institución',
        related_name='recursos_3d',
    )

    class Meta:
        verbose_name = 'Recurso Educativo 3D'
        verbose_name_plural = 'Recursos Educativos 3D'
        ordering = ['-actividad__fecha_publicacion']

    def __str__(self):
        return f"[3D] {self.actividad.titulo} — {self.get_modo_display()}"

    def tiene_galeria(self):
        return self.modo in (self.MODO_GALERIA, self.MODO_AMBOS)

    def tiene_studio(self):
        return self.modo in (self.MODO_STUDIO, self.MODO_AMBOS)

    def calcular_nota(self, piezas_colocadas: int) -> decimal.Decimal:
        """Calcula la nota proporcional según piezas colocadas."""
        if piezas_colocadas <= 0:
            return decimal.Decimal('0.00')
        ratio = decimal.Decimal(min(piezas_colocadas, self.TOTAL_PIEZAS)) / decimal.Decimal(self.TOTAL_PIEZAS)
        return (ratio * self.valor_maximo).quantize(decimal.Decimal('0.01'))


class EntregaRecurso3D(models.Model):
    """
    Registro de la actividad de un estudiante en un RecursoEducativo3D.
    Se crea al primer acceso y se actualiza conforme el estudiante avanza.
    """

    recurso = models.ForeignKey(
        RecursoEducativo3D,
        on_delete=models.CASCADE,
        related_name='entregas',
        verbose_name='Recurso 3D',
    )
    estudiante = models.ForeignKey(
        'gestion_academica.Estudiante',
        on_delete=models.CASCADE,
        related_name='entregas_3d',
        verbose_name='Estudiante',
    )
    piezas_colocadas = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Piezas Colocadas',
        help_text='Número de órganos correctamente colocados en el Studio (0–13)',
    )
    completado = models.BooleanField(
        default=False,
        verbose_name='Studio Completado',
    )
    fecha_inicio = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Primer Acceso',
    )
    fecha_completado = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Fecha de Completado',
    )
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa',
        on_delete=models.CASCADE,
        verbose_name='Institución',
        related_name='entregas_3d',
    )

    class Meta:
        unique_together = ('recurso', 'estudiante', 'institucion')
        verbose_name = 'Entrega de Recurso 3D'
        verbose_name_plural = 'Entregas de Recursos 3D'
        ordering = ['-fecha_inicio']

    def __str__(self):
        estado = 'Completado' if self.completado else f'{self.piezas_colocadas}/13 piezas'
        return f"{self.estudiante} — {self.recurso.actividad.titulo} ({estado})"

    def registrar_progreso(self, piezas: int) -> bool:
        """
        Actualiza piezas_colocadas. Si llega a 13, marca completado,
        escribe la Calificacion automática y retorna True (primera vez).
        """
        from gestion_academica.models import Calificacion

        self.piezas_colocadas = min(piezas, RecursoEducativo3D.TOTAL_PIEZAS)

        primera_completacion = False

        if self.piezas_colocadas >= RecursoEducativo3D.TOTAL_PIEZAS and not self.completado:
            self.completado = True
            self.fecha_completado = timezone.now()
            primera_completacion = True

            nota = self.recurso.calcular_nota(self.piezas_colocadas)
            Calificacion.objects.update_or_create(
                estudiante=self.estudiante,
                actividad_calificable=self.recurso.actividad,
                institucion=self.institucion,
                defaults={
                    'valor_numerico': nota,
                    'registrada_por': None,
                    'observaciones': 'Calificación automática — Studio 3D completado.',
                },
            )

        self.save(update_fields=['piezas_colocadas', 'completado', 'fecha_completado'])
        return primera_completacion
