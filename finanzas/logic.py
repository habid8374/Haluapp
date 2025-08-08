# finanzas/logic.py

from decimal import Decimal

def aplicar_descuentos_a_cuenta(estudiante, concepto_pago):
    """
    Calcula el monto final de una cuenta aplicando los descuentos de un estudiante.
    Retorna una tupla: (monto_final, observaciones_str).
    """
    monto_original = concepto_pago.valor
    monto_final = monto_original
    descuentos_aplicados = []

    # Buscamos los descuentos activos del estudiante
    for descuento in estudiante.descuentos.filter(activo=True):
        # Verificamos si el descuento aplica a este concepto de pago
        # o si es un descuento general (sin conceptos especificados)
        aplica_a_este_concepto = not descuento.conceptos_aplicables.exists() or \
                                 descuento.conceptos_aplicables.filter(pk=concepto_pago.pk).exists()

        if aplica_a_este_concepto:
            monto_descuento = Decimal('0.00')
            if descuento.tipo == 'PORCENTAJE':
                monto_descuento = monto_original * (descuento.valor / Decimal('100.0'))
            else:  # VALOR_FIJO
                monto_descuento = descuento.valor
            
            monto_final -= monto_descuento
            descuentos_aplicados.append(f"{descuento.nombre}: -${monto_descuento:,.2f}")

    # Nos aseguramos que el monto final no sea negativo
    if monto_final < 0:
        monto_final = Decimal('0.00')

    observaciones = f"Monto original: ${monto_original:,.2f}. "
    if descuentos_aplicados:
        observaciones += "Descuentos aplicados: " + ", ".join(descuentos_aplicados)

    return monto_final.quantize(Decimal('0.01')), observaciones