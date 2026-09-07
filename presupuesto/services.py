"""
presupuesto/services.py
=========================
Aquí viven las validaciones "duras" del ciclo presupuestal — las que de
verdad impiden comprometer más plata de la disponible. Cada función:

  1. Bloquea la fila padre con `select_for_update()` dentro de
     `transaction.atomic()` (mismo patrón que
     `finanzas.ConsecutivoDocumento.obtener_siguiente()`), para que dos
     personas cargando documentos al mismo tiempo no puedan comprometer el
     mismo saldo dos veces.
  2. Verifica que la vigencia fiscal esté ABIERTA.
  3. Verifica que el valor no supere el saldo disponible del eslabón
     anterior de la cadena (Apropiación → CDP → RP → Obligación).

Las vistas y el admin SIEMPRE deben crear estos objetos a través de estas
funciones — nunca con `Modelo.objects.create(...)` directo — porque ahí es
donde vive la regla de negocio real, no en el modelo ni en el formulario.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from finanzas.models import ConsecutivoDocumento

from .models import (
    CDP, RP, Obligacion, OrdenDePago, Apropiacion,
    ComprobanteContable, ConceptoRetencion, MovimientoContable, RetencionAplicada,
)


def _siguiente_numero(institucion_id, tipo_documento):
    return ConsecutivoDocumento.obtener_siguiente(institucion_id, tipo_documento)


@transaction.atomic
def expedir_cdp(*, apropiacion: Apropiacion, valor: Decimal, objeto: str, usuario) -> CDP:
    apropiacion = Apropiacion.objects.select_for_update().get(pk=apropiacion.pk)
    vigencia = apropiacion.vigencia
    if not vigencia.esta_abierta:
        raise ValidationError('La vigencia %(anio)s está cerrada: no se pueden expedir nuevos CDP.' % {'anio': vigencia.anio})
    if valor <= 0:
        raise ValidationError('El valor del CDP debe ser mayor a cero.')
    saldo = apropiacion.saldo_disponible
    if valor > saldo:
        raise ValidationError(
            'El CDP ($%(valor)s) supera el saldo disponible de la apropiación ($%(saldo)s).'
            % {'valor': f'{valor:,.2f}', 'saldo': f'{saldo:,.2f}'}
        )
    return CDP.objects.create(
        institucion=apropiacion.institucion,
        vigencia=vigencia,
        apropiacion=apropiacion,
        numero=_siguiente_numero(apropiacion.institucion_id, 'presupuesto_cdp'),
        valor=valor,
        objeto=objeto,
        creado_por=usuario,
    )


@transaction.atomic
def crear_rp(*, cdp: CDP, tercero, objeto_contrato: str, valor: Decimal, usuario, categoria_cpc=None) -> RP:
    cdp = CDP.objects.select_for_update().get(pk=cdp.pk)
    if cdp.estado != CDP.Estado.VIGENTE:
        raise ValidationError('El CDP #%(num)s no está vigente.' % {'num': cdp.numero})
    if not cdp.vigencia.esta_abierta:
        raise ValidationError('La vigencia %(anio)s está cerrada.' % {'anio': cdp.vigencia.anio})
    if valor <= 0:
        raise ValidationError('El valor del RP debe ser mayor a cero.')
    saldo = cdp.saldo_disponible
    if valor > saldo:
        raise ValidationError(
            'El RP ($%(valor)s) supera el saldo disponible del CDP #%(num)s ($%(saldo)s).'
            % {'valor': f'{valor:,.2f}', 'num': cdp.numero, 'saldo': f'{saldo:,.2f}'}
        )
    rp = RP.objects.create(
        institucion=cdp.institucion,
        cdp=cdp,
        numero=_siguiente_numero(cdp.institucion_id, 'presupuesto_rp'),
        tercero=tercero,
        objeto_contrato=objeto_contrato,
        categoria_cpc=categoria_cpc,
        valor=valor,
        creado_por=usuario,
    )
    if cdp.saldo_disponible <= 0:
        cdp.estado = CDP.Estado.AGOTADO
        cdp.save(update_fields=['estado'])
    return rp


@transaction.atomic
def causar_obligacion(*, rp: RP, valor: Decimal, soporte, usuario) -> Obligacion:
    rp = RP.objects.select_for_update().get(pk=rp.pk)
    if rp.estado != RP.Estado.VIGENTE:
        raise ValidationError('El RP #%(num)s no está vigente.' % {'num': rp.numero})
    if not rp.cdp.vigencia.esta_abierta:
        raise ValidationError('La vigencia %(anio)s está cerrada.' % {'anio': rp.cdp.vigencia.anio})
    if valor <= 0:
        raise ValidationError('El valor de la obligación debe ser mayor a cero.')
    saldo = rp.saldo_disponible
    if valor > saldo:
        raise ValidationError(
            'La obligación ($%(valor)s) supera el saldo disponible del RP #%(num)s ($%(saldo)s).'
            % {'valor': f'{valor:,.2f}', 'num': rp.numero, 'saldo': f'{saldo:,.2f}'}
        )
    obligacion = Obligacion.objects.create(
        institucion=rp.institucion,
        rp=rp,
        numero=_siguiente_numero(rp.institucion_id, 'presupuesto_obligacion'),
        valor=valor,
        soporte_recibido_satisfaccion=soporte,
        creado_por=usuario,
    )
    if rp.saldo_disponible <= 0:
        rp.estado = RP.Estado.LIQUIDADO
        rp.save(update_fields=['estado'])
    return obligacion


@transaction.atomic
def generar_orden_pago(*, obligacion: Obligacion, usuario) -> OrdenDePago:
    """Crea la Orden de Pago SIN retenciones (total_retenciones=0). Las
    retenciones se agregan itemizadas después con `agregar_retencion()` —
    nunca como un número suelto, para que queden auditables por tipo."""
    obligacion = Obligacion.objects.select_for_update().get(pk=obligacion.pk)
    if obligacion.estado != Obligacion.Estado.VIGENTE:
        raise ValidationError('La obligación #%(num)s no está vigente.' % {'num': obligacion.numero})
    if not obligacion.rp.cdp.vigencia.esta_abierta:
        raise ValidationError('La vigencia %(anio)s está cerrada.' % {'anio': obligacion.rp.cdp.vigencia.anio})
    valor_bruto = obligacion.saldo_disponible
    if valor_bruto <= 0:
        raise ValidationError('La obligación #%(num)s ya está totalmente pagada.' % {'num': obligacion.numero})
    orden = OrdenDePago.objects.create(
        institucion=obligacion.institucion,
        obligacion=obligacion,
        numero=_siguiente_numero(obligacion.institucion_id, 'presupuesto_orden_pago'),
        valor_bruto=valor_bruto,
        total_retenciones=Decimal('0.00'),
        valor_neto=valor_bruto,
        beneficiario=obligacion.rp.tercero,
        creado_por=usuario,
    )
    if obligacion.saldo_disponible <= 0:
        obligacion.estado = Obligacion.Estado.PAGADA
        obligacion.save(update_fields=['estado'])
    return orden


def _recalcular_totales_orden(orden: OrdenDePago):
    total = orden.retenciones.aggregate(t=Sum('valor'))['t'] or Decimal('0.00')
    orden.total_retenciones = total
    orden.valor_neto = orden.valor_bruto - total
    orden.save(update_fields=['total_retenciones', 'valor_neto'])


@transaction.atomic
def agregar_retencion(*, orden_pago: OrdenDePago, concepto: ConceptoRetencion, base_gravable: Decimal, usuario) -> RetencionAplicada:
    orden_pago = OrdenDePago.objects.select_for_update().get(pk=orden_pago.pk)
    if orden_pago.estado != OrdenDePago.Estado.GENERADA:
        raise ValidationError('Solo se pueden agregar retenciones a una Orden de Pago en estado Generada.')
    if hasattr(orden_pago, 'comprobante_contable'):
        raise ValidationError('Esta Orden de Pago ya tiene un comprobante contable generado: no se pueden agregar más retenciones.')
    if base_gravable <= 0:
        raise ValidationError('La base gravable debe ser mayor a cero.')
    valor = (base_gravable * concepto.tarifa_porcentaje / Decimal('100')).quantize(Decimal('0.01'))
    nuevo_total = orden_pago.total_retenciones + valor
    if nuevo_total > orden_pago.valor_bruto:
        raise ValidationError(
            'Esta retención ($%(valor)s) haría que el total de retenciones ($%(total)s) supere el valor bruto de la orden ($%(bruto)s).'
            % {'valor': f'{valor:,.2f}', 'total': f'{nuevo_total:,.2f}', 'bruto': f'{orden_pago.valor_bruto:,.2f}'}
        )
    retencion = RetencionAplicada.objects.create(
        orden_pago=orden_pago, concepto=concepto,
        base_gravable=base_gravable, tarifa_porcentaje=concepto.tarifa_porcentaje, valor=valor,
    )
    _recalcular_totales_orden(orden_pago)
    return retencion


@transaction.atomic
def quitar_retencion(*, retencion: RetencionAplicada, usuario):
    orden_pago = OrdenDePago.objects.select_for_update().get(pk=retencion.orden_pago_id)
    if orden_pago.estado != OrdenDePago.Estado.GENERADA:
        raise ValidationError('Solo se pueden quitar retenciones de una Orden de Pago en estado Generada.')
    if hasattr(orden_pago, 'comprobante_contable'):
        raise ValidationError('Esta Orden de Pago ya tiene un comprobante contable generado.')
    retencion.delete()
    _recalcular_totales_orden(orden_pago)


@transaction.atomic
def generar_comprobante_contable(*, orden_pago: OrdenDePago, cuenta_bancos, usuario) -> ComprobanteContable:
    """Crea el comprobante en BORRADOR con sus movimientos ya balanceados
    por construcción (débito al gasto = crédito a retenciones + crédito a
    bancos), listo para que el contador lo revise y lo contabilice."""
    orden_pago = OrdenDePago.objects.select_for_update().get(pk=orden_pago.pk)
    if hasattr(orden_pago, 'comprobante_contable'):
        raise ValidationError('Esta Orden de Pago ya tiene un comprobante contable.')
    if orden_pago.estado == OrdenDePago.Estado.ANULADA:
        raise ValidationError('No se puede generar comprobante de una Orden de Pago anulada.')
    vigencia = orden_pago.obligacion.rp.cdp.vigencia
    if not vigencia.esta_abierta:
        raise ValidationError('La vigencia %(anio)s está cerrada.' % {'anio': vigencia.anio})

    rubro = orden_pago.obligacion.rp.cdp.apropiacion.rubro
    cuenta_gasto = rubro.cuenta_cgc_gasto
    if cuenta_gasto is None:
        raise ValidationError(
            'El rubro "%(rubro)s" no tiene configurada su cuenta contable (CGC) de gasto. '
            'Configúrala en Rubros de Gasto antes de generar el comprobante.' % {'rubro': rubro}
        )

    comprobante = ComprobanteContable.objects.create(
        institucion=orden_pago.institucion,
        vigencia=vigencia,
        numero=_siguiente_numero(orden_pago.institucion_id, 'presupuesto_comprobante'),
        tipo=ComprobanteContable.Tipo.EGRESO,
        orden_pago=orden_pago,
    )
    MovimientoContable.objects.create(
        comprobante=comprobante, cuenta=cuenta_gasto, tercero=orden_pago.beneficiario,
        descripcion=f'Causación Orden de Pago #{orden_pago.numero}',
        valor_debito=orden_pago.valor_bruto, valor_credito=Decimal('0.00'),
    )
    for retencion in orden_pago.retenciones.select_related('concepto', 'concepto__cuenta_puc_pasivo'):
        cuenta_pasivo = retencion.concepto.cuenta_puc_pasivo
        if cuenta_pasivo is None:
            raise ValidationError(
                'El concepto de retención "%(concepto)s" no tiene configurada su cuenta contable (CGC) de pasivo.'
                % {'concepto': retencion.concepto.nombre}
            )
        MovimientoContable.objects.create(
            comprobante=comprobante, cuenta=cuenta_pasivo, tercero=orden_pago.beneficiario,
            descripcion=f'{retencion.concepto.nombre} — OP #{orden_pago.numero}',
            valor_debito=Decimal('0.00'), valor_credito=retencion.valor,
        )
    MovimientoContable.objects.create(
        comprobante=comprobante, cuenta=cuenta_bancos, tercero=orden_pago.beneficiario,
        descripcion=f'Pago neto Orden de Pago #{orden_pago.numero}',
        valor_debito=Decimal('0.00'), valor_credito=orden_pago.valor_neto,
    )
    return comprobante


@transaction.atomic
def contabilizar_comprobante(*, comprobante: ComprobanteContable, usuario) -> ComprobanteContable:
    from django.utils import timezone
    comprobante = ComprobanteContable.objects.select_for_update().get(pk=comprobante.pk)
    if comprobante.estado != ComprobanteContable.Estado.BORRADOR:
        raise ValidationError('Solo un comprobante en Borrador se puede contabilizar.')
    if not comprobante.vigencia.esta_abierta:
        raise ValidationError('La vigencia %(anio)s está cerrada.' % {'anio': comprobante.vigencia.anio})
    if not comprobante.esta_cuadrado:
        raise ValidationError(
            'El comprobante no cuadra: débitos ($%(d)s) ≠ créditos ($%(c)s). No se puede contabilizar así.'
            % {'d': f'{comprobante.total_debitos:,.2f}', 'c': f'{comprobante.total_creditos:,.2f}'}
        )
    comprobante.estado = ComprobanteContable.Estado.CONTABILIZADO
    comprobante.contabilizado_por = usuario
    comprobante.fecha_contabilizacion = timezone.now()
    comprobante.save(update_fields=['estado', 'contabilizado_por', 'fecha_contabilizacion'])
    if comprobante.orden_pago_id:
        orden = comprobante.orden_pago
        orden.estado = OrdenDePago.Estado.PAGADA
        orden.save(update_fields=['estado'])
    return comprobante


@transaction.atomic
def reversar_comprobante(*, comprobante: ComprobanteContable, usuario, motivo: str) -> ComprobanteContable:
    """Nunca se edita ni se borra un comprobante contabilizado: se crea uno
    nuevo de tipo AJUSTE con los movimientos exactamente invertidos
    (débito↔crédito), y ese nuevo queda contabilizado de una vez."""
    comprobante = ComprobanteContable.objects.select_for_update().get(pk=comprobante.pk)
    if comprobante.estado != ComprobanteContable.Estado.CONTABILIZADO:
        raise ValidationError('Solo se puede reversar un comprobante que ya esté Contabilizado.')
    if not comprobante.vigencia.esta_abierta:
        raise ValidationError('La vigencia %(anio)s está cerrada.' % {'anio': comprobante.vigencia.anio})

    from django.utils import timezone
    reverso = ComprobanteContable.objects.create(
        institucion=comprobante.institucion,
        vigencia=comprobante.vigencia,
        numero=_siguiente_numero(comprobante.institucion_id, 'presupuesto_comprobante'),
        tipo=ComprobanteContable.Tipo.AJUSTE,
        comprobante_que_reversa=comprobante,
        estado=ComprobanteContable.Estado.CONTABILIZADO,
        contabilizado_por=usuario,
        fecha_contabilizacion=timezone.now(),
    )
    for mov in comprobante.movimientos.all():
        MovimientoContable.objects.create(
            comprobante=reverso, cuenta=mov.cuenta, tercero=mov.tercero,
            descripcion=f'Reversión de comprobante #{comprobante.numero}: {mov.descripcion}',
            valor_debito=mov.valor_credito, valor_credito=mov.valor_debito,
        )
    comprobante.anulado_motivo = motivo
    comprobante.save(update_fields=['anulado_motivo'])
    return reverso


@transaction.atomic
def cerrar_vigencia(*, vigencia, usuario):
    from .models import VigenciaFiscal
    vigencia = VigenciaFiscal.objects.select_for_update().get(pk=vigencia.pk)
    if vigencia.estado == VigenciaFiscal.Estado.CERRADA:
        return vigencia
    vigencia.estado = VigenciaFiscal.Estado.CERRADA
    from django.utils import timezone
    vigencia.fecha_cierre = timezone.now()
    vigencia.cerrada_por = usuario
    vigencia.save(update_fields=['estado', 'fecha_cierre', 'cerrada_por'])
    return vigencia
