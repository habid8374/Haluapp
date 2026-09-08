"""
presupuesto/reportes.py
=========================
Fase 4 — Reportes de ejecución presupuestal y consolidación contable.

Estas funciones solo LEEN y agregan datos que ya existen (nunca escriben
nada) — son la base tanto de las pantallas HTML de reportes como de la
exportación a Excel. Cada una recibe una `VigenciaFiscal` ya resuelta por
la vista (con su filtro de institución ya aplicado).
"""
from decimal import Decimal

from django.db.models import Sum

from .models import (
    CDP, RP, Apropiacion, ComprobanteContable, MovimientoContable,
    Obligacion, OrdenDePago, PresupuestoIngreso,
)


def ejecucion_ingresos(vigencia):
    """Presupuestado vs. recaudado, por rubro de ingreso."""
    items = PresupuestoIngreso.objects.filter(vigencia=vigencia).select_related(
        'rubro', 'rubro__tipo_recurso'
    ).order_by('rubro__codigo')
    filas = []
    for i in items:
        filas.append({
            'rubro': i.rubro,
            'fuente_financiacion': i.rubro.tipo_recurso,
            'presupuestado': i.valor_inicial,
            'recaudado': i.valor_recaudado,
            'saldo_por_recaudar': i.valor_inicial - i.valor_recaudado,
        })
    return filas


def ejecucion_gastos(vigencia):
    """Apropiación, comprometido (RP), obligado y pagado, por rubro de gasto."""
    apropiaciones = Apropiacion.objects.filter(vigencia=vigencia).select_related('rubro').order_by('rubro__codigo')
    filas = []
    for a in apropiaciones:
        rps_vigentes = RP.objects.filter(
            cdp__apropiacion=a
        ).exclude(estado=RP.Estado.ANULADO)
        comprometido = rps_vigentes.aggregate(t=Sum('valor'))['t'] or Decimal('0.00')

        obligaciones_vigentes = Obligacion.objects.filter(
            rp__cdp__apropiacion=a
        ).exclude(estado=Obligacion.Estado.ANULADA)
        obligado = obligaciones_vigentes.aggregate(t=Sum('valor'))['t'] or Decimal('0.00')

        pagado = OrdenDePago.objects.filter(
            obligacion__rp__cdp__apropiacion=a, estado=OrdenDePago.Estado.PAGADA
        ).aggregate(t=Sum('valor_neto'))['t'] or Decimal('0.00')

        filas.append({
            'rubro': a.rubro,
            'apropiacion_inicial': a.valor_inicial,
            'apropiacion_definitiva': a.valor_definitivo,
            'comprometido': comprometido,
            'obligado': obligado,
            'pagado': pagado,
            'saldo_por_comprometer': a.valor_definitivo - comprometido,
        })
    return filas


def balance_comprobacion(vigencia):
    """Saldo por cuenta CGC — suma de débitos y créditos de todos los
    comprobantes CONTABILIZADOS de la vigencia (el "libro mayor" básico
    que pide un contador para reportar)."""
    filas = list(
        MovimientoContable.objects.filter(
            comprobante__vigencia=vigencia,
            comprobante__estado=ComprobanteContable.Estado.CONTABILIZADO,
        )
        .values('cuenta__codigo', 'cuenta__nombre')
        .annotate(total_debitos=Sum('valor_debito'), total_creditos=Sum('valor_credito'))
        .order_by('cuenta__codigo')
    )
    for f in filas:
        f['saldo'] = f['total_debitos'] - f['total_creditos']
    return filas
