"""
Modelos SIMAT / SIMPADE.

Fase 0 (cimientos): catálogos oficiales del MEN (DANE, etnias, resguardos,
EPS, cajas de compensación) y el modelo `Sede` por institución. Todo es
ADITIVO — no altera modelos existentes.

Los catálogos son tablas de referencia GLOBALES de plataforma (sin FK a
institución), igual que `DBAPredefinido`. Se siembran desde los archivos
oficiales del SIMAT (Anexo 6A). El campo `codigo` es el código oficial que
exige el cargue masivo Anexo 6A.
"""
from django.db import models
from django.utils.translation import gettext_lazy as _


class _CatalogoBase(models.Model):
    """Base para catálogos código→nombre del MEN."""
    codigo = models.CharField(_("Código oficial"), max_length=20, unique=True)
    nombre = models.CharField(_("Nombre"), max_length=255)
    habilitado = models.BooleanField(_("Habilitado"), default=True)

    class Meta:
        abstract = True
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"


class Departamento(models.Model):
    """Departamentos DANE (DIVIPOLA). `codigo` = código DANE de 2 posiciones."""
    codigo = models.CharField(_("Código DANE"), max_length=2, unique=True)
    nombre = models.CharField(_("Nombre"), max_length=120)

    class Meta:
        verbose_name = _("Departamento (DANE)")
        verbose_name_plural = _("Departamentos (DANE)")
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"


class Municipio(models.Model):
    """Municipios DANE (DIVIPOLA). `codigo` = código DANE completo (5 posiciones).

    Se siembra vacío en la Fase 0: el listado oficial DIVIPOLA de municipios se
    carga posteriormente (decisión pendiente con el cliente). Las FK a municipio
    quedan opcionales hasta entonces.
    """
    codigo = models.CharField(_("Código DANE"), max_length=5, unique=True)
    nombre = models.CharField(_("Nombre"), max_length=150)
    departamento = models.ForeignKey(
        Departamento, on_delete=models.CASCADE, related_name='municipios',
        verbose_name=_("Departamento"),
    )

    class Meta:
        verbose_name = _("Municipio (DANE)")
        verbose_name_plural = _("Municipios (DANE)")
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"


class Etnia(_CatalogoBase):
    class Meta(_CatalogoBase.Meta):
        verbose_name = _("Etnia (SIMAT)")
        verbose_name_plural = _("Etnias (SIMAT)")


class Resguardo(_CatalogoBase):
    class Meta(_CatalogoBase.Meta):
        verbose_name = _("Resguardo (SIMAT)")
        verbose_name_plural = _("Resguardos (SIMAT)")


class EPS(_CatalogoBase):
    class Meta(_CatalogoBase.Meta):
        verbose_name = _("EPS (SIMAT)")
        verbose_name_plural = _("EPS (SIMAT)")


class CajaCompensacion(_CatalogoBase):
    class Meta(_CatalogoBase.Meta):
        verbose_name = _("Caja de Compensación (SIMAT)")
        verbose_name_plural = _("Cajas de Compensación (SIMAT)")


class Sede(models.Model):
    """Sede de una institución educativa (obligatorio para el reporte SIMAT).

    Institución-scoped: cada sede pertenece a un colegio. Un colegio oficial
    suele tener varias sedes y jornadas.
    """
    JORNADA_CHOICES = [
        ('MANANA', _("Mañana")),
        ('TARDE', _("Tarde")),
        ('NOCHE', _("Noche")),
        ('UNICA', _("Única")),
        ('COMPLETA', _("Completa")),
        ('FIN_DE_SEMANA', _("Fin de semana")),
    ]
    ZONA_CHOICES = [
        ('URBANA', _("Urbana")),
        ('RURAL', _("Rural")),
    ]

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='sedes', verbose_name=_("Institución"),
    )
    nombre = models.CharField(_("Nombre de la sede"), max_length=200)
    codigo_dane_sede = models.CharField(
        _("Código DANE de la sede"), max_length=20, blank=True,
        help_text=_("Código DANE de 12 dígitos asignado por el MEN a la sede."),
    )
    consecutivo = models.CharField(
        _("Consecutivo de la sede"), max_length=20, blank=True,
        help_text=_("Consecutivo de sede que exige el SIMAT."),
    )
    zona = models.CharField(_("Zona"), max_length=10, choices=ZONA_CHOICES, blank=True)
    jornada_principal = models.CharField(
        _("Jornada principal"), max_length=15, choices=JORNADA_CHOICES, blank=True,
    )
    es_principal = models.BooleanField(_("¿Sede principal?"), default=False)
    activa = models.BooleanField(_("Activa"), default=True)

    class Meta:
        verbose_name = _("Sede")
        verbose_name_plural = _("Sedes")
        ordering = ['institucion', '-es_principal', 'nombre']
        constraints = [
            models.UniqueConstraint(
                fields=['institucion', 'nombre'], name='uniq_sede_institucion_nombre'
            ),
        ]

    def __str__(self):
        return self.nombre

    @classmethod
    def principal_de(cls, institucion):
        """Devuelve la sede principal (o la primera activa) de la institución."""
        if institucion is None:
            return None
        qs = cls.objects.filter(institucion=institucion, activa=True)
        return qs.filter(es_principal=True).first() or qs.first()

    @classmethod
    def asegurar_principal(cls, institucion):
        """Garantiza que la institución tenga una Sede Principal (la crea si no).
        Idempotente: si ya hay sedes, no crea otra."""
        if institucion is None:
            return None
        existente = cls.objects.filter(institucion=institucion).order_by('-es_principal').first()
        if existente:
            return existente
        return cls.objects.create(
            institucion=institucion,
            nombre='Sede Principal',
            codigo_dane_sede=(getattr(institucion, 'codigo_dane', '') or '')[:20],
            consecutivo='01',
            zona='URBANA',
            es_principal=True,
            activa=True,
        )

    @classmethod
    def siguiente_consecutivo(cls, institucion):
        """Calcula el próximo consecutivo numérico de sede para la institución.
        La sede principal es 01; las anexas siguen 02, 03… Devuelve un str de 2
        dígitos."""
        if institucion is None:
            return '01'
        maximo = 0
        for c in cls.objects.filter(institucion=institucion).values_list('consecutivo', flat=True):
            try:
                n = int(str(c).strip())
            except (TypeError, ValueError):
                continue
            maximo = max(maximo, n)
        return f"{maximo + 1:02d}"
