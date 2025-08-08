# finanzas/managers.py

from django.db import models
from django.utils import timezone
from decimal import Decimal
import calendar
from datetime import datetime, date

# NO importamos los modelos aquí para evitar el error de importación circular.

class CuentaPorCobrarEstudianteManager(models.Manager):
    """Manager para centralizar la lógica de negocio de las Cuentas por Cobrar."""

    def sincronizar_cuentas_automaticas(self, estudiante):
        """
        VERSIÓN DEFINITIVA Y ROBUSTA:
        1. VERIFICA y CORRIGE los precios en el perfil del estudiante usando el Nivel de Escolaridad.
        2. CREA las pensiones faltantes con los valores correctos y aplica descuentos.
        """
        if not estudiante.activo:
            return 0 

        # Importamos los modelos aquí dentro para evitar importaciones circulares
        from .models import ConceptoPago, CuentaPorCobrarEstudiante, NOMBRES_MESES_ESPANOL
        
        if not (estudiante.institucion and estudiante.grado_actual and estudiante.grado_actual.nivel_escolaridad):
            # Si no podemos encontrar el nivel, no podemos obtener el precio.
            return 0

        # PASO 1: Asegurarnos de que el estudiante tenga los precios correctos en su perfil.
        nivel_escolar = estudiante.grado_actual.nivel_escolaridad
        
        if not estudiante.valor_mensualidad or estudiante.valor_mensualidad <= 0:
            estudiante.valor_mensualidad = nivel_escolar.valor_pension_estandar
            if not estudiante.valor_matricula or estudiante.valor_matricula <= 0:
                estudiante.valor_matricula = nivel_escolar.valor_matricula_estandar
            
            estudiante.save(update_fields=['valor_mensualidad', 'valor_matricula'])
            print(f"INFO: Se corrigieron los precios en el perfil del estudiante {estudiante}.")

        # PASO 2: Ahora procedemos a crear las pensiones.
        institucion = estudiante.institucion
        año_actual = timezone.now().year

        concepto_pension_base = ConceptoPago.objects.filter(
            institucion=institucion,
            automatico=True,
            tipo_concepto__nombre__icontains='pensión'
        ).first()

        if not concepto_pension_base:
            return 0

        cuentas_creadas = 0
        for mes_num in range(2, 12): # De Febrero a Noviembre
            nombre_mes = NOMBRES_MESES_ESPANOL.get(mes_num, '')

            concepto_mes_actual, _ = ConceptoPago.objects.get_or_create(
                nombre_concepto=f"Pensión {nombre_mes} {año_actual}",
                tipo_concepto=concepto_pension_base.tipo_concepto,
                institucion=institucion,
                defaults={'valor': estudiante.valor_mensualidad}
            )

            _, ultimo_dia = calendar.monthrange(año_actual, mes_num)
            fecha_vencimiento = date(año_actual, mes_num, ultimo_dia)
            
            # --- INICIO DE LA LÓGICA DE DESCUENTOS (COMPLETA) ---
            monto_original = estudiante.valor_mensualidad
            monto_final = monto_original
            descuentos_aplicados_a_esta_cuenta = []

            # Asumiendo que tienes una relación ManyToMany 'descuentos' en tu modelo Estudiante
            for descuento in estudiante.descuentos.filter(activo=True):
                aplica_a_este_concepto = not descuento.conceptos_aplicables.exists() or \
                                         descuento.conceptos_aplicables.filter(pk=concepto_mes_actual.pk).exists()

                if aplica_a_este_concepto:
                    monto_descuento = Decimal('0.00')
                    if descuento.tipo == 'PORCENTAJE':
                        monto_descuento = monto_original * (descuento.valor / Decimal('100.0'))
                    else: # Asume que es un valor FIJO
                        monto_descuento = descuento.valor
                    
                    monto_final -= monto_descuento
                    descuentos_aplicados_a_esta_cuenta.append(f"{descuento.nombre}: -${monto_descuento:,.2f}")

            if monto_final < 0:
                monto_final = 0

            observaciones = f"Monto original: ${monto_original:,.2f}. "
            if descuentos_aplicados_a_esta_cuenta:
                observaciones += "Descuentos aplicados: " + ", ".join(descuentos_aplicados_a_esta_cuenta)
            # --- FIN DE LA LÓGICA DE DESCUENTOS ---

            # Crear la Cuenta por Cobrar si no existe
            _, created = self.get_queryset().get_or_create(
                estudiante=estudiante,
                concepto_pago=concepto_mes_actual,
                año=año_actual,
                mes=mes_num,
                defaults={
                    'monto_asignado': monto_final,
                    'fecha_vencimiento_especifica': fecha_vencimiento,
                    'institucion': institucion,
                    'observaciones_internas': observaciones
                }
            )

            if created:
                cuentas_creadas += 1

        return cuentas_creadas