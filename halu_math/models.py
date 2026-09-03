"""Halu Math — práctica adaptativa de matemáticas por DBA (inspirado en el
modelo de DreamBox Learning: dificultad ajustada en tiempo real según el
desempeño del estudiante).

Arquitectura multi-institución (mismo patrón que BancoPregunta en
Simulacros):
  * EjercicioMath con institucion=NULL + es_publica=True → ejercicio de la
    plataforma, visible para todas las instituciones.
  * EjercicioMath con institucion=X → ejercicio privado de esa institución
    (generado/curado por sus propios docentes).
  * DominioDBA / IntentoEjercicioMath siempre tienen institucion (progreso
    real de un estudiante concreto, nunca público).

El eje de contenido es el DBA oficial del MEN (gestion_academica.DBAPredefinido)
— no se inventa una taxonomía propia de temas.
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Dificultad(models.TextChoices):
    BASICO = 'BASICO', _('Básico')
    MEDIO = 'MEDIO', _('Medio')
    ALTO = 'ALTO', _('Alto')


class EjercicioMath(models.Model):
    """Banco de ejercicios de opción múltiple, organizados por DBA. Mismo
    patrón multi-tenant que BancoPregunta (simulacros)."""

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE, null=True, blank=True,
        related_name='ejercicios_math', verbose_name=_("Institución"),
        help_text=_("Vacío = ejercicio público del catálogo de la plataforma."),
    )
    es_publica = models.BooleanField(default=False, verbose_name=_("Público (catálogo de la plataforma)"))
    dba = models.ForeignKey(
        'gestion_academica.DBAPredefinido', on_delete=models.CASCADE,
        related_name='ejercicios_math', verbose_name=_("DBA"),
    )
    nivel_dificultad = models.CharField(
        max_length=10, choices=Dificultad.choices, default=Dificultad.BASICO,
        verbose_name=_("Nivel de dificultad"),
    )
    enunciado = models.TextField(verbose_name=_("Enunciado"))
    explicacion = models.TextField(blank=True, verbose_name=_("Explicación de la respuesta"))
    fuente = models.CharField(max_length=200, blank=True, verbose_name=_("Fuente"))
    activo = models.BooleanField(default=True, verbose_name=_("Activo"))
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ejercicios_math_creados', verbose_name=_("Creado por"),
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Ejercicio de Matemáticas")
        verbose_name_plural = _("Ejercicios de Matemáticas")
        ordering = ['dba', 'nivel_dificultad', 'pk']

    def __str__(self):
        return f"{self.dba} — {self.enunciado[:60]}"

    @property
    def opcion_correcta(self):
        return self.opciones.filter(es_correcta=True).first()


class OpcionEjercicioMath(models.Model):
    class Letra(models.TextChoices):
        A = 'A', 'A'
        B = 'B', 'B'
        C = 'C', 'C'
        D = 'D', 'D'

    ejercicio = models.ForeignKey(EjercicioMath, on_delete=models.CASCADE, related_name='opciones')
    letra = models.CharField(max_length=1, choices=Letra.choices, verbose_name=_("Letra"))
    texto = models.CharField(max_length=300, verbose_name=_("Texto"))
    es_correcta = models.BooleanField(default=False, verbose_name=_("Es correcta"))

    class Meta:
        verbose_name = _("Opción de ejercicio")
        verbose_name_plural = _("Opciones de ejercicio")
        ordering = ['letra']
        unique_together = [['ejercicio', 'letra']]

    def __str__(self):
        return f"{self.letra}) {self.texto}"


class DominioDBA(models.Model):
    """Estado de dominio de un estudiante sobre un DBA — el corazón del
    motor adaptativo. Se actualiza en cada IntentoEjercicioMath vía
    halu_math.motor.procesar_respuesta()."""

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='dominios_math', verbose_name=_("Institución"),
    )
    estudiante = models.ForeignKey(
        'gestion_academica.Estudiante', on_delete=models.CASCADE,
        related_name='dominios_math', verbose_name=_("Estudiante"),
    )
    dba = models.ForeignKey('gestion_academica.DBAPredefinido', on_delete=models.CASCADE, verbose_name=_("DBA"))
    nivel_actual = models.CharField(
        max_length=10, choices=Dificultad.choices, default=Dificultad.BASICO,
        verbose_name=_("Nivel actual"),
    )
    racha_actual = models.PositiveSmallIntegerField(default=0, verbose_name=_("Racha actual"))
    racha_maxima = models.PositiveSmallIntegerField(default=0, verbose_name=_("Racha máxima"))
    intentos_totales = models.PositiveIntegerField(default=0, verbose_name=_("Intentos totales"))
    aciertos_totales = models.PositiveIntegerField(default=0, verbose_name=_("Aciertos totales"))
    dominado = models.BooleanField(default=False, verbose_name=_("Dominado"))
    fecha_dominado = models.DateTimeField(null=True, blank=True, verbose_name=_("Fecha de dominio"))
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Dominio de DBA")
        verbose_name_plural = _("Dominios de DBA")
        unique_together = [['estudiante', 'dba']]
        ordering = ['dba', 'estudiante']

    def __str__(self):
        return f"{self.estudiante} — {self.dba} ({self.get_nivel_actual_display()})"

    @property
    def porcentaje_acierto(self):
        if not self.intentos_totales:
            return 0
        return round(self.aciertos_totales / self.intentos_totales * 100, 1)


class IntentoEjercicioMath(models.Model):
    """Registro granular de cada intento — histórico, nunca se borra,
    permite auditar el algoritmo adaptativo."""

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='intentos_math', verbose_name=_("Institución"),
    )
    estudiante = models.ForeignKey(
        'gestion_academica.Estudiante', on_delete=models.CASCADE,
        related_name='intentos_math', verbose_name=_("Estudiante"),
    )
    ejercicio = models.ForeignKey(EjercicioMath, on_delete=models.CASCADE, verbose_name=_("Ejercicio"))
    opcion_elegida = models.ForeignKey(
        OpcionEjercicioMath, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name=_("Opción elegida"),
    )
    es_correcta = models.BooleanField(default=False, verbose_name=_("Es correcta"))
    nivel_en_el_momento = models.CharField(
        max_length=10, choices=Dificultad.choices, verbose_name=_("Nivel en el momento del intento"),
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Intento de ejercicio")
        verbose_name_plural = _("Intentos de ejercicio")
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.estudiante} — {self.ejercicio_id} ({'✓' if self.es_correcta else '✗'})"
