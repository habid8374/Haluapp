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
from django.utils.translation import gettext as _

from finanzas.models import ConsecutivoDocumento

from .models import CDP, RP, Obligacion, OrdenDePago, Apropiacion


def _siguiente_numero(institucion_id, tipo_documento):
    return ConsecutivoDocumento.obtener_siguiente(institucion_id, tipo_documento)


@transaction.atomic
def expedir_cdp(*, apropiacion: Apropiacion, valor: Decimal, objeto: str, usuario) -> CDP:
    apropiacion = Apropiacion.objects.select_for_update().get(pk=apropiacion.pk)
    vigencia = apropiacion.vigencia
    if not vigencia.esta_abierta:
        raise ValidationError(_('La vigencia %(anio)s está cerrada: no se pueden expedir nuevos CDP.') % {'anio': vigencia.anio})
    if valor <= 0:
        raise ValidationError(_('El valor del CDP debe ser mayor a cero.'))
    saldo = apropiacion.saldo_disponible
    if valor > saldo:
        raise ValidationError(
            _('El CDP ($%(valor)s) supera el saldo disponible de la apropiación ($%(saldo)s).')
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
def crear_rp(*, cdp: CDP, tercero, objeto_contrato: str, valor: Decimal, usuario) -> RP:
    cdp = CDP.objects.select_for_update().get(pk=cdp.pk)
    if cdp.estado != CDP.Estado.VIGENTE:
        raise ValidationError(_('El CDP #%(num)s no está vigente.') % {'num': cdp.numero})
    if not cdp.vigencia.esta_abierta:
        raise ValidationError(_('La vigencia %(anio)s está cerrada.') % {'anio': cdp.vigencia.anio})
    if valor <= 0:
        raise ValidationError(_('El valor del RP debe ser mayor a cero.'))
    saldo = cdp.saldo_disponible
    if valor > saldo:
        raise ValidationError(
            _('El RP ($%(valor)s) supera el saldo disponible del CDP #%(num)s ($%(saldo)s).')
            % {'valor': f'{valor:,.2f}', 'num': cdp.numero, 'saldo': f'{saldo:,.2f}'}
        )
    rp = RP.objects.create(
        institucion=cdp.institucion,
        cdp=cdp,
        numero=_siguiente_numero(cdp.institucion_id, 'presupuesto_rp'),
        tercero=tercero,
        objeto_contrato=objeto_contrato,
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
        raise ValidationError(_('El RP #%(num)s no está vigente.') % {'num': rp.numero})
    if not rp.cdp.vigencia.esta_abierta:
        raise ValidationError(_('La vigencia %(anio)s está cerrada.') % {'anio': rp.cdp.vigencia.anio})
    if valor <= 0:
        raise ValidationError(_('El valor de la obligación debe ser mayor a cero.'))
    saldo = rp.saldo_disponible
    if valor > saldo:
        raise ValidationError(
            _('La obligación ($%(valor)s) supera el saldo disponible del RP #%(num)s ($%(saldo)s).')
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
def generar_orden_pago(*, obligacion: Obligacion, total_retenciones: Decimal, usuario) -> OrdenDePago:
    obligacion = Obligacion.objects.select_for_update().get(pk=obligacion.pk)
    if obligacion.estado != Obligacion.Estado.VIGENTE:
        raise ValidationError(_('La obligación #%(num)s no está vigente.') % {'num': obligacion.numero})
    if not obligacion.rp.cdp.vigencia.esta_abierta:
        raise ValidationError(_('La vigencia %(anio)s está cerrada.') % {'anio': obligacion.rp.cdp.vigencia.anio})
    valor_bruto = obligacion.saldo_disponible
    if valor_bruto <= 0:
        raise ValidationError(_('La obligación #%(num)s ya está totalmente pagada.') % {'num': obligacion.numero})
    total_retenciones = total_retenciones or Decimal('0.00')
    if total_retenciones < 0 or total_retenciones > valor_bruto:
        raise ValidationError(_('Las retenciones no pueden ser negativas ni superar el valor de la obligación.'))
    orden = OrdenDePago.objects.create(
        institucion=obligacion.institucion,
        obligacion=obligacion,
        numero=_siguiente_numero(obligacion.institucion_id, 'presupuesto_orden_pago'),
        valor_bruto=valor_bruto,
        total_retenciones=total_retenciones,
        valor_neto=valor_bruto - total_retenciones,
        beneficiario=obligacion.rp.tercero,
        creado_por=usuario,
    )
    if obligacion.saldo_disponible <= 0:
        obligacion.estado = Obligacion.Estado.PAGADA
        obligacion.save(update_fields=['estado'])
    return orden


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
