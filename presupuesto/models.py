"""
presupuesto/models.py
======================
Fase 1 (Núcleo Presupuestal) del módulo de Presupuesto FSE — pensado para
Fondos de Servicios Educativos de instituciones oficiales (Decreto 1075 de
2015 / Ley 715), no para el módulo de cobros a familias (`finanzas`), que
sigue existiendo tal cual para los colegios privados.

Cadena obligatoria del ciclo de gasto público, cada eslabón sin poder
superar el saldo disponible del anterior:

    Apropiación → CDP → RP → Obligación → Orden de Pago

Las validaciones de saldo "duras" (las que de verdad impiden comprometer
más de lo disponible) viven en `presupuesto/services.py`, protegidas con
`transaction.atomic()` + `select_for_update()` — el mismo patrón que ya usa
`finanzas.ConsecutivoDocumento.obtener_siguiente()` para evitar condiciones
de carrera cuando dos personas cargan documentos al mismo tiempo. Las
`clean()` de aquí son una validación "blanda" adicional (para que el admin
y los formularios avisen rápido), no la única barrera.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _


# ─────────────────────────────────────────────────────────────────────────
# Vigencia fiscal
# ─────────────────────────────────────────────────────────────────────────

class VigenciaFiscal(models.Model):
    class Estado(models.TextChoices):
        ABIERTA = 'ABIERTA', _('Abierta')
        CERRADA = 'CERRADA', _('Cerrada')

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='vigencias_fiscales', verbose_name=_('Institución'),
    )
    anio = models.PositiveIntegerField(_('Año'))
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ABIERTA)
    fecha_apertura = models.DateTimeField(_('Fecha de apertura'), auto_now_add=True)
    fecha_cierre = models.DateTimeField(_('Fecha de cierre'), null=True, blank=True)
    cerrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name=_('Cerrada por'),
    )

    class Meta:
        unique_together = ('institucion', 'anio')
        ordering = ['-anio']
        verbose_name = _('Vigencia Fiscal')
        verbose_name_plural = _('Vigencias Fiscales')

    def __str__(self):
        return f"{self.institucion} — {self.anio} ({self.get_estado_display()})"

    @property
    def esta_abierta(self):
        return self.estado == self.Estado.ABIERTA


# ─────────────────────────────────────────────────────────────────────────
# Rubros presupuestales (catálogo por institución — cada FSE define los
# suyos según su propio acuerdo de presupuesto anual)
# ─────────────────────────────────────────────────────────────────────────

class RubroPresupuestalIngreso(models.Model):
    class TipoRecurso(models.TextChoices):
        SGP = 'SGP', _('Sistema General de Participaciones')
        RECURSOS_PROPIOS = 'RECURSOS_PROPIOS', _('Recursos propios')
        TRANSFERENCIAS = 'TRANSFERENCIAS', _('Transferencias territoriales')
        RECURSOS_CAPITAL = 'RECURSOS_CAPITAL', _('Recursos de capital')
        DONACIONES = 'DONACIONES', _('Donaciones')

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='rubros_ingreso', verbose_name=_('Institución'),
    )
    codigo = models.CharField(_('Código'), max_length=20)
    nombre = models.CharField(_('Nombre'), max_length=200)
    tipo_recurso = models.CharField(_('Fuente de financiación'), max_length=20, choices=TipoRecurso.choices)
    rubro_padre = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='hijos', verbose_name=_('Rubro padre'),
    )
    activo = models.BooleanField(_('Activo'), default=True)

    class Meta:
        unique_together = ('institucion', 'codigo')
        ordering = ['codigo']
        verbose_name = _('Rubro Presupuestal de Ingreso')
        verbose_name_plural = _('Rubros Presupuestales de Ingreso')

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"


class RubroPresupuestalGasto(models.Model):
    class Tipo(models.TextChoices):
        FUNCIONAMIENTO = 'FUNCIONAMIENTO', _('Funcionamiento')
        INVERSION = 'INVERSION', _('Inversión')

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='rubros_gasto', verbose_name=_('Institución'),
    )
    codigo = models.CharField(_('Código'), max_length=20)
    nombre = models.CharField(_('Nombre'), max_length=200)
    tipo = models.CharField(_('Tipo de gasto'), max_length=20, choices=Tipo.choices)
    rubro_padre = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='hijos', verbose_name=_('Rubro padre'),
    )
    activo = models.BooleanField(_('Activo'), default=True)

    class Meta:
        unique_together = ('institucion', 'codigo')
        ordering = ['codigo']
        verbose_name = _('Rubro Presupuestal de Gasto')
        verbose_name_plural = _('Rubros Presupuestales de Gasto')

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"


# ─────────────────────────────────────────────────────────────────────────
# Presupuesto de ingresos (informativo — no bloquea nada, solo compara
# recaudado vs. presupuestado)
# ─────────────────────────────────────────────────────────────────────────

class PresupuestoIngreso(models.Model):
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='presupuestos_ingreso', verbose_name=_('Institución'),
    )
    vigencia = models.ForeignKey(
        VigenciaFiscal, on_delete=models.CASCADE,
        related_name='presupuestos_ingreso', verbose_name=_('Vigencia fiscal'),
    )
    rubro = models.ForeignKey(
        RubroPresupuestalIngreso, on_delete=models.PROTECT,
        related_name='presupuestos', verbose_name=_('Rubro de ingreso'),
    )
    valor_inicial = models.DecimalField(_('Valor presupuestado'), max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_recaudado = models.DecimalField(_('Valor recaudado'), max_digits=14, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        unique_together = ('vigencia', 'rubro')
        verbose_name = _('Presupuesto de Ingreso')
        verbose_name_plural = _('Presupuestos de Ingreso')

    def __str__(self):
        return f"{self.rubro} — {self.vigencia.anio}: ${self.valor_inicial:,.2f}"

    def clean(self):
        if self.rubro_id and self.vigencia_id and self.rubro.institucion_id != self.vigencia.institucion_id:
            raise ValidationError(_('El rubro y la vigencia deben pertenecer a la misma institución.'))


# ─────────────────────────────────────────────────────────────────────────
# Apropiación (el "presupuesto de gasto" definitivo, con sus modificaciones)
# ─────────────────────────────────────────────────────────────────────────

class Apropiacion(models.Model):
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='apropiaciones', verbose_name=_('Institución'),
    )
    vigencia = models.ForeignKey(
        VigenciaFiscal, on_delete=models.CASCADE,
        related_name='apropiaciones', verbose_name=_('Vigencia fiscal'),
    )
    rubro = models.ForeignKey(
        RubroPresupuestalGasto, on_delete=models.PROTECT,
        related_name='apropiaciones', verbose_name=_('Rubro de gasto'),
    )
    valor_inicial = models.DecimalField(_('Apropiación inicial'), max_digits=14, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        unique_together = ('vigencia', 'rubro')
        verbose_name = _('Apropiación Presupuestal')
        verbose_name_plural = _('Apropiaciones Presupuestales')

    def __str__(self):
        return f"{self.rubro} — {self.vigencia.anio}"

    def clean(self):
        if self.rubro_id and self.vigencia_id and self.rubro.institucion_id != self.vigencia.institucion_id:
            raise ValidationError(_('El rubro y la vigencia deben pertenecer a la misma institución.'))

    # --- Saldos calculados (siempre en vivo, nunca desnormalizados) ---

    @property
    def total_adiciones(self):
        return self.modificaciones.filter(tipo=ModificacionPresupuestal.Tipo.ADICION).aggregate(
            t=Sum('valor'))['t'] or Decimal('0.00')

    @property
    def total_reducciones(self):
        return self.modificaciones.filter(tipo=ModificacionPresupuestal.Tipo.REDUCCION).aggregate(
            t=Sum('valor'))['t'] or Decimal('0.00')

    @property
    def total_traslados_entrada(self):
        return self.traslados_recibidos.aggregate(t=Sum('valor'))['t'] or Decimal('0.00')

    @property
    def total_traslados_salida(self):
        return self.modificaciones.filter(tipo=ModificacionPresupuestal.Tipo.TRASLADO).aggregate(
            t=Sum('valor'))['t'] or Decimal('0.00')

    @property
    def valor_definitivo(self):
        return (
            self.valor_inicial
            + self.total_adiciones
            - self.total_reducciones
            - self.total_traslados_salida
            + self.total_traslados_entrada
        )

    @property
    def total_comprometido(self):
        """Suma de los CDP vigentes (no anulados) expedidos contra esta apropiación."""
        return self.cdps.exclude(estado=CDP.Estado.ANULADO).aggregate(t=Sum('valor'))['t'] or Decimal('0.00')

    @property
    def saldo_disponible(self):
        return self.valor_definitivo - self.total_comprometido


class ModificacionPresupuestal(models.Model):
    class Tipo(models.TextChoices):
        ADICION = 'ADICION', _('Adición')
        REDUCCION = 'REDUCCION', _('Reducción')
        TRASLADO = 'TRASLADO', _('Traslado')

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='modificaciones_presupuestales', verbose_name=_('Institución'),
    )
    apropiacion = models.ForeignKey(
        Apropiacion, on_delete=models.CASCADE,
        related_name='modificaciones', verbose_name=_('Apropiación (origen)'),
    )
    apropiacion_destino = models.ForeignKey(
        Apropiacion, on_delete=models.CASCADE, null=True, blank=True,
        related_name='traslados_recibidos', verbose_name=_('Apropiación destino (solo traslados)'),
        help_text=_('Obligatorio solo para movimientos de tipo Traslado: el rubro que RECIBE el valor.'),
    )
    tipo = models.CharField(_('Tipo de movimiento'), max_length=12, choices=Tipo.choices)
    valor = models.DecimalField(_('Valor'), max_digits=14, decimal_places=2)
    acto_administrativo = models.CharField(
        _('Acto administrativo'), max_length=255, blank=True,
        help_text=_('Ej: Resolución 014 del 12/03/2026 del Consejo Directivo.'),
    )
    soporte = models.FileField(_('Soporte (PDF)'), upload_to='presupuesto/modificaciones/', blank=True, null=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    fecha = models.DateTimeField(_('Fecha de registro'), auto_now_add=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = _('Modificación Presupuestal')
        verbose_name_plural = _('Modificaciones Presupuestales')

    def __str__(self):
        return f"{self.get_tipo_display()} ${self.valor:,.2f} — {self.apropiacion.rubro}"

    def clean(self):
        if self.tipo == self.Tipo.TRASLADO and not self.apropiacion_destino_id:
            raise ValidationError({'apropiacion_destino': _('Un traslado necesita el rubro que recibe el valor.')})
        if self.tipo != self.Tipo.TRASLADO and self.apropiacion_destino_id:
            raise ValidationError({'apropiacion_destino': _('Solo los traslados usan un rubro destino.')})
        if self.apropiacion_destino_id and self.apropiacion_destino_id == self.apropiacion_id:
            raise ValidationError({'apropiacion_destino': _('El rubro destino no puede ser el mismo que el de origen.')})
        if self.valor is not None and self.valor <= 0:
            raise ValidationError({'valor': _('El valor debe ser mayor a cero.')})


# ─────────────────────────────────────────────────────────────────────────
# CDP → RP → Obligación → Orden de Pago
# ─────────────────────────────────────────────────────────────────────────

class CDP(models.Model):
    """Certificado de Disponibilidad Presupuestal."""

    class Estado(models.TextChoices):
        VIGENTE = 'VIGENTE', _('Vigente')
        ANULADO = 'ANULADO', _('Anulado')
        AGOTADO = 'AGOTADO', _('Agotado')

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='cdps', verbose_name=_('Institución'),
    )
    vigencia = models.ForeignKey(
        VigenciaFiscal, on_delete=models.PROTECT, related_name='cdps', verbose_name=_('Vigencia fiscal'),
    )
    apropiacion = models.ForeignKey(
        Apropiacion, on_delete=models.PROTECT, related_name='cdps', verbose_name=_('Apropiación'),
    )
    numero = models.PositiveIntegerField(_('Número'), editable=False)
    valor = models.DecimalField(_('Valor'), max_digits=14, decimal_places=2)
    objeto = models.CharField(_('Objeto'), max_length=255, help_text=_('Para qué se aparta este dinero.'))
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.VIGENTE)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    fecha_expedicion = models.DateTimeField(_('Fecha de expedición'), auto_now_add=True)
    anulado_motivo = models.CharField(_('Motivo de anulación'), max_length=255, blank=True)

    class Meta:
        unique_together = ('institucion', 'vigencia', 'numero')
        ordering = ['-numero']
        verbose_name = _('Certificado de Disponibilidad Presupuestal (CDP)')
        verbose_name_plural = _('Certificados de Disponibilidad Presupuestal (CDP)')

    def __str__(self):
        return f"CDP #{self.numero}/{self.vigencia.anio} — ${self.valor:,.2f}"

    @property
    def total_comprometido_rp(self):
        return self.registros_presupuestales.exclude(estado=RP.Estado.ANULADO).aggregate(
            t=Sum('valor'))['t'] or Decimal('0.00')

    @property
    def saldo_disponible(self):
        if self.estado == self.Estado.ANULADO:
            return Decimal('0.00')
        return self.valor - self.total_comprometido_rp


class RP(models.Model):
    """Registro Presupuestal (compromiso con un tercero)."""

    class Estado(models.TextChoices):
        VIGENTE = 'VIGENTE', _('Vigente')
        ANULADO = 'ANULADO', _('Anulado')
        LIQUIDADO = 'LIQUIDADO', _('Liquidado')

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='registros_presupuestales', verbose_name=_('Institución'),
    )
    cdp = models.ForeignKey(
        CDP, on_delete=models.PROTECT, related_name='registros_presupuestales', verbose_name=_('CDP'),
    )
    numero = models.PositiveIntegerField(_('Número'), editable=False)
    tercero = models.ForeignKey(
        'finanzas.Proveedor', on_delete=models.PROTECT, related_name='registros_presupuestales',
        verbose_name=_('Tercero / contratista'),
    )
    objeto_contrato = models.CharField(_('Objeto del contrato'), max_length=255)
    valor = models.DecimalField(_('Valor'), max_digits=14, decimal_places=2)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.VIGENTE)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    fecha = models.DateTimeField(_('Fecha de registro'), auto_now_add=True)
    anulado_motivo = models.CharField(_('Motivo de anulación'), max_length=255, blank=True)

    class Meta:
        unique_together = ('institucion', 'numero')
        ordering = ['-numero']
        verbose_name = _('Registro Presupuestal (RP)')
        verbose_name_plural = _('Registros Presupuestales (RP)')

    def __str__(self):
        return f"RP #{self.numero} — ${self.valor:,.2f} ({self.tercero})"

    @property
    def total_obligado(self):
        return self.obligaciones.exclude(estado=Obligacion.Estado.ANULADA).aggregate(
            t=Sum('valor'))['t'] or Decimal('0.00')

    @property
    def saldo_disponible(self):
        if self.estado == self.Estado.ANULADO:
            return Decimal('0.00')
        return self.valor - self.total_obligado


class Obligacion(models.Model):
    """Causación del gasto: el bien/servicio ya se recibió a satisfacción."""

    class Estado(models.TextChoices):
        VIGENTE = 'VIGENTE', _('Vigente')
        ANULADA = 'ANULADA', _('Anulada')
        PAGADA = 'PAGADA', _('Pagada')

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='obligaciones', verbose_name=_('Institución'),
    )
    rp = models.ForeignKey(
        RP, on_delete=models.PROTECT, related_name='obligaciones', verbose_name=_('Registro Presupuestal (RP)'),
    )
    numero = models.PositiveIntegerField(_('Número'), editable=False)
    valor = models.DecimalField(_('Valor'), max_digits=14, decimal_places=2)
    soporte_recibido_satisfaccion = models.FileField(
        _('Soporte (acta / factura)'), upload_to='presupuesto/obligaciones/', blank=True, null=True,
    )
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.VIGENTE)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    fecha = models.DateTimeField(_('Fecha de registro'), auto_now_add=True)
    anulado_motivo = models.CharField(_('Motivo de anulación'), max_length=255, blank=True)

    class Meta:
        unique_together = ('institucion', 'numero')
        ordering = ['-numero']
        verbose_name = _('Obligación')
        verbose_name_plural = _('Obligaciones')

    def __str__(self):
        return f"Obligación #{self.numero} — ${self.valor:,.2f}"

    @property
    def total_pagado(self):
        return self.ordenes_de_pago.exclude(estado=OrdenDePago.Estado.ANULADA).aggregate(
            t=Sum('valor_bruto'))['t'] or Decimal('0.00')

    @property
    def saldo_disponible(self):
        if self.estado == self.Estado.ANULADA:
            return Decimal('0.00')
        return self.valor - self.total_pagado


class OrdenDePago(models.Model):
    class Estado(models.TextChoices):
        GENERADA = 'GENERADA', _('Generada')
        PAGADA = 'PAGADA', _('Pagada')
        ANULADA = 'ANULADA', _('Anulada')

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='ordenes_de_pago', verbose_name=_('Institución'),
    )
    obligacion = models.ForeignKey(
        Obligacion, on_delete=models.PROTECT, related_name='ordenes_de_pago', verbose_name=_('Obligación'),
    )
    numero = models.PositiveIntegerField(_('Número'), editable=False)
    valor_bruto = models.DecimalField(_('Valor bruto'), max_digits=14, decimal_places=2)
    total_retenciones = models.DecimalField(_('Total retenciones'), max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_neto = models.DecimalField(_('Valor neto a pagar'), max_digits=14, decimal_places=2)
    beneficiario = models.ForeignKey(
        'finanzas.Proveedor', on_delete=models.PROTECT, related_name='ordenes_de_pago', verbose_name=_('Beneficiario'),
    )
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.GENERADA)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    fecha = models.DateTimeField(_('Fecha de registro'), auto_now_add=True)
    anulado_motivo = models.CharField(_('Motivo de anulación'), max_length=255, blank=True)

    class Meta:
        unique_together = ('institucion', 'numero')
        ordering = ['-numero']
        verbose_name = _('Orden de Pago')
        verbose_name_plural = _('Órdenes de Pago')

    def __str__(self):
        return f"Orden de Pago #{self.numero} — ${self.valor_neto:,.2f}"
