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


# ─────────────────────────────────────────────────────────────────────────
# Vigencia fiscal
# ─────────────────────────────────────────────────────────────────────────

class VigenciaFiscal(models.Model):
    class Estado(models.TextChoices):
        ABIERTA = 'ABIERTA', 'Abierta'
        CERRADA = 'CERRADA', 'Cerrada'

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='vigencias_fiscales', verbose_name='Institución',
    )
    anio = models.PositiveIntegerField('Año')
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ABIERTA)
    fecha_apertura = models.DateTimeField('Fecha de apertura', auto_now_add=True)
    fecha_cierre = models.DateTimeField('Fecha de cierre', null=True, blank=True)
    cerrada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name='Cerrada por',
    )

    class Meta:
        unique_together = ('institucion', 'anio')
        ordering = ['-anio']
        verbose_name = 'Vigencia Fiscal'
        verbose_name_plural = 'Vigencias Fiscales'

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
        SGP = 'SGP', 'Sistema General de Participaciones'
        RECURSOS_PROPIOS = 'RECURSOS_PROPIOS', 'Recursos propios'
        TRANSFERENCIAS = 'TRANSFERENCIAS', 'Transferencias territoriales'
        RECURSOS_CAPITAL = 'RECURSOS_CAPITAL', 'Recursos de capital'
        DONACIONES = 'DONACIONES', 'Donaciones'

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='rubros_ingreso', verbose_name='Institución',
    )
    codigo = models.CharField('Código', max_length=20)
    nombre = models.CharField('Nombre', max_length=200)
    tipo_recurso = models.CharField('Fuente de financiación', max_length=20, choices=TipoRecurso.choices)
    rubro_padre = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='hijos', verbose_name='Rubro padre',
    )
    activo = models.BooleanField('Activo', default=True)

    class Meta:
        unique_together = ('institucion', 'codigo')
        ordering = ['codigo']
        verbose_name = 'Rubro Presupuestal de Ingreso'
        verbose_name_plural = 'Rubros Presupuestales de Ingreso'

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"


class RubroPresupuestalGasto(models.Model):
    class Tipo(models.TextChoices):
        FUNCIONAMIENTO = 'FUNCIONAMIENTO', 'Funcionamiento'
        INVERSION = 'INVERSION', 'Inversión'

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='rubros_gasto', verbose_name='Institución',
    )
    codigo = models.CharField('Código', max_length=20)
    nombre = models.CharField('Nombre', max_length=200)
    tipo = models.CharField('Tipo de gasto', max_length=20, choices=Tipo.choices)
    rubro_padre = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='hijos', verbose_name='Rubro padre',
    )
    activo = models.BooleanField('Activo', default=True)

    class Meta:
        unique_together = ('institucion', 'codigo')
        ordering = ['codigo']
        verbose_name = 'Rubro Presupuestal de Gasto'
        verbose_name_plural = 'Rubros Presupuestales de Gasto'

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"


# ─────────────────────────────────────────────────────────────────────────
# Presupuesto de ingresos (informativo — no bloquea nada, solo compara
# recaudado vs. presupuestado)
# ─────────────────────────────────────────────────────────────────────────

class PresupuestoIngreso(models.Model):
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='presupuestos_ingreso', verbose_name='Institución',
    )
    vigencia = models.ForeignKey(
        VigenciaFiscal, on_delete=models.CASCADE,
        related_name='presupuestos_ingreso', verbose_name='Vigencia fiscal',
    )
    rubro = models.ForeignKey(
        RubroPresupuestalIngreso, on_delete=models.PROTECT,
        related_name='presupuestos', verbose_name='Rubro de ingreso',
    )
    valor_inicial = models.DecimalField('Valor presupuestado', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_recaudado = models.DecimalField('Valor recaudado', max_digits=14, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        unique_together = ('vigencia', 'rubro')
        verbose_name = 'Presupuesto de Ingreso'
        verbose_name_plural = 'Presupuestos de Ingreso'

    def __str__(self):
        return f"{self.rubro} — {self.vigencia.anio}: ${self.valor_inicial:,.2f}"

    def clean(self):
        if self.rubro_id and self.vigencia_id and self.rubro.institucion_id != self.vigencia.institucion_id:
            raise ValidationError('El rubro y la vigencia deben pertenecer a la misma institución.')


# ─────────────────────────────────────────────────────────────────────────
# Apropiación (el "presupuesto de gasto" definitivo, con sus modificaciones)
# ─────────────────────────────────────────────────────────────────────────

class Apropiacion(models.Model):
    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='apropiaciones', verbose_name='Institución',
    )
    vigencia = models.ForeignKey(
        VigenciaFiscal, on_delete=models.CASCADE,
        related_name='apropiaciones', verbose_name='Vigencia fiscal',
    )
    rubro = models.ForeignKey(
        RubroPresupuestalGasto, on_delete=models.PROTECT,
        related_name='apropiaciones', verbose_name='Rubro de gasto',
    )
    valor_inicial = models.DecimalField('Apropiación inicial', max_digits=14, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        unique_together = ('vigencia', 'rubro')
        verbose_name = 'Apropiación Presupuestal'
        verbose_name_plural = 'Apropiaciones Presupuestales'

    def __str__(self):
        return f"{self.rubro} — {self.vigencia.anio}"

    def clean(self):
        if self.rubro_id and self.vigencia_id and self.rubro.institucion_id != self.vigencia.institucion_id:
            raise ValidationError('El rubro y la vigencia deben pertenecer a la misma institución.')

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
        ADICION = 'ADICION', 'Adición'
        REDUCCION = 'REDUCCION', 'Reducción'
        TRASLADO = 'TRASLADO', 'Traslado'

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='modificaciones_presupuestales', verbose_name='Institución',
    )
    apropiacion = models.ForeignKey(
        Apropiacion, on_delete=models.CASCADE,
        related_name='modificaciones', verbose_name='Apropiación (origen)',
    )
    apropiacion_destino = models.ForeignKey(
        Apropiacion, on_delete=models.CASCADE, null=True, blank=True,
        related_name='traslados_recibidos', verbose_name='Apropiación destino (solo traslados)',
        help_text='Obligatorio solo para movimientos de tipo Traslado: el rubro que RECIBE el valor.',
    )
    tipo = models.CharField('Tipo de movimiento', max_length=12, choices=Tipo.choices)
    valor = models.DecimalField('Valor', max_digits=14, decimal_places=2)
    acto_administrativo = models.CharField(
        'Acto administrativo', max_length=255, blank=True,
        help_text='Ej: Resolución 014 del 12/03/2026 del Consejo Directivo.',
    )
    soporte = models.FileField('Soporte (PDF)', upload_to='presupuesto/modificaciones/', blank=True, null=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    fecha = models.DateTimeField('Fecha de registro', auto_now_add=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Modificación Presupuestal'
        verbose_name_plural = 'Modificaciones Presupuestales'

    def __str__(self):
        return f"{self.get_tipo_display()} ${self.valor:,.2f} — {self.apropiacion.rubro}"

    def clean(self):
        if self.tipo == self.Tipo.TRASLADO and not self.apropiacion_destino_id:
            raise ValidationError({'apropiacion_destino': 'Un traslado necesita el rubro que recibe el valor.'})
        if self.tipo != self.Tipo.TRASLADO and self.apropiacion_destino_id:
            raise ValidationError({'apropiacion_destino': 'Solo los traslados usan un rubro destino.'})
        if self.apropiacion_destino_id and self.apropiacion_destino_id == self.apropiacion_id:
            raise ValidationError({'apropiacion_destino': 'El rubro destino no puede ser el mismo que el de origen.'})
        if self.valor is not None and self.valor <= 0:
            raise ValidationError({'valor': 'El valor debe ser mayor a cero.'})


# ─────────────────────────────────────────────────────────────────────────
# CDP → RP → Obligación → Orden de Pago
# ─────────────────────────────────────────────────────────────────────────

class CDP(models.Model):
    """Certificado de Disponibilidad Presupuestal."""

    class Estado(models.TextChoices):
        VIGENTE = 'VIGENTE', 'Vigente'
        ANULADO = 'ANULADO', 'Anulado'
        AGOTADO = 'AGOTADO', 'Agotado'

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='cdps', verbose_name='Institución',
    )
    vigencia = models.ForeignKey(
        VigenciaFiscal, on_delete=models.PROTECT, related_name='cdps', verbose_name='Vigencia fiscal',
    )
    apropiacion = models.ForeignKey(
        Apropiacion, on_delete=models.PROTECT, related_name='cdps', verbose_name='Apropiación',
    )
    numero = models.PositiveIntegerField('Número', editable=False)
    valor = models.DecimalField('Valor', max_digits=14, decimal_places=2)
    objeto = models.CharField('Objeto', max_length=255, help_text='Para qué se aparta este dinero.')
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.VIGENTE)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    fecha_expedicion = models.DateTimeField('Fecha de expedición', auto_now_add=True)
    anulado_motivo = models.CharField('Motivo de anulación', max_length=255, blank=True)

    class Meta:
        unique_together = ('institucion', 'vigencia', 'numero')
        ordering = ['-numero']
        verbose_name = 'Certificado de Disponibilidad Presupuestal (CDP)'
        verbose_name_plural = 'Certificados de Disponibilidad Presupuestal (CDP)'

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
        VIGENTE = 'VIGENTE', 'Vigente'
        ANULADO = 'ANULADO', 'Anulado'
        LIQUIDADO = 'LIQUIDADO', 'Liquidado'

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='registros_presupuestales', verbose_name='Institución',
    )
    cdp = models.ForeignKey(
        CDP, on_delete=models.PROTECT, related_name='registros_presupuestales', verbose_name='CDP',
    )
    numero = models.PositiveIntegerField('Número', editable=False)
    tercero = models.ForeignKey(
        'finanzas.Proveedor', on_delete=models.PROTECT, related_name='registros_presupuestales',
        verbose_name='Tercero / contratista',
    )
    objeto_contrato = models.CharField('Objeto del contrato', max_length=255)
    valor = models.DecimalField('Valor', max_digits=14, decimal_places=2)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.VIGENTE)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    fecha = models.DateTimeField('Fecha de registro', auto_now_add=True)
    anulado_motivo = models.CharField('Motivo de anulación', max_length=255, blank=True)

    class Meta:
        unique_together = ('institucion', 'numero')
        ordering = ['-numero']
        verbose_name = 'Registro Presupuestal (RP)'
        verbose_name_plural = 'Registros Presupuestales (RP)'

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
        VIGENTE = 'VIGENTE', 'Vigente'
        ANULADA = 'ANULADA', 'Anulada'
        PAGADA = 'PAGADA', 'Pagada'

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='obligaciones', verbose_name='Institución',
    )
    rp = models.ForeignKey(
        RP, on_delete=models.PROTECT, related_name='obligaciones', verbose_name='Registro Presupuestal (RP)',
    )
    numero = models.PositiveIntegerField('Número', editable=False)
    valor = models.DecimalField('Valor', max_digits=14, decimal_places=2)
    soporte_recibido_satisfaccion = models.FileField(
        'Soporte (acta / factura)', upload_to='presupuesto/obligaciones/', blank=True, null=True,
    )
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.VIGENTE)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    fecha = models.DateTimeField('Fecha de registro', auto_now_add=True)
    anulado_motivo = models.CharField('Motivo de anulación', max_length=255, blank=True)

    class Meta:
        unique_together = ('institucion', 'numero')
        ordering = ['-numero']
        verbose_name = 'Obligación'
        verbose_name_plural = 'Obligaciones'

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
        GENERADA = 'GENERADA', 'Generada'
        PAGADA = 'PAGADA', 'Pagada'
        ANULADA = 'ANULADA', 'Anulada'

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='ordenes_de_pago', verbose_name='Institución',
    )
    obligacion = models.ForeignKey(
        Obligacion, on_delete=models.PROTECT, related_name='ordenes_de_pago', verbose_name='Obligación',
    )
    numero = models.PositiveIntegerField('Número', editable=False)
    valor_bruto = models.DecimalField('Valor bruto', max_digits=14, decimal_places=2)
    total_retenciones = models.DecimalField('Total retenciones', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_neto = models.DecimalField('Valor neto a pagar', max_digits=14, decimal_places=2)
    beneficiario = models.ForeignKey(
        'finanzas.Proveedor', on_delete=models.PROTECT, related_name='ordenes_de_pago', verbose_name='Beneficiario',
    )
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.GENERADA)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    fecha = models.DateTimeField('Fecha de registro', auto_now_add=True)
    anulado_motivo = models.CharField('Motivo de anulación', max_length=255, blank=True)

    class Meta:
        unique_together = ('institucion', 'numero')
        ordering = ['-numero']
        verbose_name = 'Orden de Pago'
        verbose_name_plural = 'Órdenes de Pago'

    def __str__(self):
        return f"Orden de Pago #{self.numero} — ${self.valor_neto:,.2f}"
