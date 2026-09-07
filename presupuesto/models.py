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
    cuenta_cgc_gasto = models.ForeignKey(
        'CatalogoGeneralCuentas', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='rubros_gasto', verbose_name='Cuenta contable (CGC) de este gasto',
        help_text='La cuenta que se debita al causar contablemente un pago de este rubro. Sin esto, no se puede generar el comprobante contable.',
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


# ─────────────────────────────────────────────────────────────────────────
# FASE 2 — Causación Contable (partida doble) y Retenciones
# ─────────────────────────────────────────────────────────────────────────

class CatalogoGeneralCuentas(models.Model):
    """Catálogo de cuentas contables — GLOBAL de la plataforma, no por
    institución (igual que el catálogo DBA de `piar`/`simulacros`): el plan
    de cuentas para entidades de gobierno lo fija la Contaduría General de
    la Nación (CGN), no cada colegio.

    IMPORTANTE: la migración que siembra este catálogo trae solo un
    conjunto base de ejemplo (Caja, Bancos, CxP, gastos y patrimonio más
    comunes de un FSE) para que el módulo sea usable desde el día uno —
    NO es una copia certificada del Catálogo General de Cuentas vigente.
    Antes de cerrar una vigencia fiscal real, el contador de la
    institución debe revisar/completar los códigos aquí contra la
    resolución CGN vigente.
    """
    class Naturaleza(models.TextChoices):
        DEBITO = 'DEBITO', 'Débito'
        CREDITO = 'CREDITO', 'Crédito'

    codigo = models.CharField('Código', max_length=20, unique=True)
    nombre = models.CharField('Nombre', max_length=200)
    naturaleza = models.CharField(max_length=10, choices=Naturaleza.choices)
    cuenta_padre = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='hijas', verbose_name='Cuenta padre',
    )
    permite_movimientos = models.BooleanField(
        'Permite movimientos', default=True,
        help_text='Si está desactivado, es una cuenta "de agrupación" (ej. una clase o grupo) que no recibe movimientos directos, solo sus subcuentas.',
    )
    activo = models.BooleanField('Activa', default=True)

    class Meta:
        ordering = ['codigo']
        verbose_name = 'Cuenta del Catálogo General de Cuentas'
        verbose_name_plural = 'Catálogo General de Cuentas (CGC)'

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"


class ComprobanteContable(models.Model):
    """Un comprobante = un hecho económico completo (por ahora, uno por
    Orden de Pago). Se genera en BORRADOR y el contador lo revisa antes de
    "contabilizar" — una vez CONTABILIZADO queda inmutable (igual que
    `PagoRegistrado.anulado`: nunca se edita ni se borra, solo se reversa
    con OTRO comprobante nuevo)."""

    class Tipo(models.TextChoices):
        EGRESO = 'EGRESO', 'Comprobante de Egreso'
        AJUSTE = 'AJUSTE', 'Ajuste / Reversión'

    class Estado(models.TextChoices):
        BORRADOR = 'BORRADOR', 'Borrador'
        CONTABILIZADO = 'CONTABILIZADO', 'Contabilizado'
        ANULADO = 'ANULADO', 'Anulado'

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='comprobantes_contables', verbose_name='Institución',
    )
    vigencia = models.ForeignKey(
        VigenciaFiscal, on_delete=models.PROTECT, related_name='comprobantes_contables', verbose_name='Vigencia fiscal',
    )
    numero = models.PositiveIntegerField('Número', editable=False)
    tipo = models.CharField(max_length=10, choices=Tipo.choices, default=Tipo.EGRESO)
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.BORRADOR)
    orden_pago = models.OneToOneField(
        OrdenDePago, on_delete=models.PROTECT, null=True, blank=True,
        related_name='comprobante_contable', verbose_name='Orden de Pago de origen',
    )
    comprobante_que_reversa = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='reversiones', verbose_name='Comprobante que reversa (solo ajustes)',
    )
    fecha = models.DateTimeField('Fecha de creación', auto_now_add=True)
    contabilizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    fecha_contabilizacion = models.DateTimeField('Fecha de contabilización', null=True, blank=True)
    anulado_motivo = models.CharField('Motivo de anulación', max_length=255, blank=True)

    class Meta:
        unique_together = ('institucion', 'numero')
        ordering = ['-numero']
        verbose_name = 'Comprobante Contable'
        verbose_name_plural = 'Comprobantes Contables'

    def __str__(self):
        return f"Comprobante #{self.numero} ({self.get_estado_display()})"

    @property
    def total_debitos(self):
        return self.movimientos.aggregate(t=Sum('valor_debito'))['t'] or Decimal('0.00')

    @property
    def total_creditos(self):
        return self.movimientos.aggregate(t=Sum('valor_credito'))['t'] or Decimal('0.00')

    @property
    def esta_cuadrado(self):
        return self.total_debitos == self.total_creditos and self.total_debitos > 0


class MovimientoContable(models.Model):
    """Una línea de un comprobante: SIEMPRE tiene valor en débito O en
    crédito (nunca ambos, nunca ninguno) — se valida en `clean()` y, sobre
    todo, en `services.contabilizar_comprobante()` antes de permitir el
    paso a CONTABILIZADO."""

    comprobante = models.ForeignKey(
        ComprobanteContable, on_delete=models.CASCADE, related_name='movimientos', verbose_name='Comprobante',
    )
    cuenta = models.ForeignKey(
        CatalogoGeneralCuentas, on_delete=models.PROTECT, related_name='movimientos', verbose_name='Cuenta (CGC)',
    )
    tercero = models.ForeignKey(
        'finanzas.Proveedor', on_delete=models.PROTECT, null=True, blank=True,
        related_name='movimientos_contables', verbose_name='Tercero',
    )
    descripcion = models.CharField('Descripción', max_length=255, blank=True)
    valor_debito = models.DecimalField('Débito', max_digits=14, decimal_places=2, default=Decimal('0.00'))
    valor_credito = models.DecimalField('Crédito', max_digits=14, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        ordering = ['id']
        verbose_name = 'Movimiento Contable'
        verbose_name_plural = 'Movimientos Contables'

    def __str__(self):
        lado = f"Db ${self.valor_debito:,.2f}" if self.valor_debito else f"Cr ${self.valor_credito:,.2f}"
        return f"{self.cuenta.codigo} — {lado}"

    def clean(self):
        if self.valor_debito and self.valor_credito:
            raise ValidationError('Un movimiento no puede tener valor en débito Y en crédito a la vez.')
        if not self.valor_debito and not self.valor_credito:
            raise ValidationError('Un movimiento debe tener valor en débito o en crédito.')


class ConceptoRetencion(models.Model):
    """Tarifas de retención configurables POR INSTITUCIÓN — varían por
    departamento/municipio (estampillas) y por tipo de tercero (ReteFuente),
    así que no se fijan como constantes globales de la plataforma."""

    class Tipo(models.TextChoices):
        RETEFUENTE = 'RETEFUENTE', 'Retención en la Fuente'
        RETEICA = 'RETEICA', 'ReteICA'
        ESTAMPILLA = 'ESTAMPILLA', 'Estampilla territorial'
        OTRA = 'OTRA', 'Otra retención'

    institucion = models.ForeignKey(
        'finanzas.InstitucionEducativa', on_delete=models.CASCADE,
        related_name='conceptos_retencion', verbose_name='Institución',
    )
    tipo = models.CharField(max_length=15, choices=Tipo.choices)
    nombre = models.CharField('Nombre', max_length=150, help_text='Ej: "Estampilla Pro-Cultura", "ReteFuente servicios".')
    tarifa_porcentaje = models.DecimalField('Tarifa (%)', max_digits=6, decimal_places=3)
    cuenta_puc_pasivo = models.ForeignKey(
        CatalogoGeneralCuentas, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='conceptos_retencion', verbose_name='Cuenta PUC del pasivo (por pagar)',
    )
    activo = models.BooleanField('Activo', default=True)

    class Meta:
        ordering = ['tipo', 'nombre']
        verbose_name = 'Concepto de Retención'
        verbose_name_plural = 'Conceptos de Retención'

    def __str__(self):
        return f"{self.nombre} ({self.tarifa_porcentaje}%)"


class RetencionAplicada(models.Model):
    """Una retención concreta aplicada a una Orden de Pago — itemizada
    (nunca un solo número suelto) para que se pueda auditar y, más
    adelante, reportar por tipo."""

    orden_pago = models.ForeignKey(
        OrdenDePago, on_delete=models.CASCADE, related_name='retenciones', verbose_name='Orden de Pago',
    )
    concepto = models.ForeignKey(
        ConceptoRetencion, on_delete=models.PROTECT, related_name='retenciones_aplicadas', verbose_name='Concepto',
    )
    base_gravable = models.DecimalField('Base gravable', max_digits=14, decimal_places=2)
    tarifa_porcentaje = models.DecimalField('Tarifa aplicada (%)', max_digits=6, decimal_places=3)
    valor = models.DecimalField('Valor retenido', max_digits=14, decimal_places=2)

    class Meta:
        ordering = ['id']
        verbose_name = 'Retención Aplicada'
        verbose_name_plural = 'Retenciones Aplicadas'

    def __str__(self):
        return f"{self.concepto.nombre}: ${self.valor:,.2f}"
