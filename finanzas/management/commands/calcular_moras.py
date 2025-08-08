# finanzas/management/commands/calcular_moras.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from finanzas.models import CuentaPorCobrarEstudiante, ConceptoPago
from decimal import Decimal

class Command(BaseCommand):
    help = 'Calcula y genera cargos por mora para cuentas vencidas que lo permitan.'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("--- Iniciando cálculo de moras ---"))
        
        today = timezone.now().date()
        
        # 1. Buscamos todas las cuentas vencidas que permiten mora
        cuentas_vencidas = CuentaPorCobrarEstudiante.objects.filter(
            estado='VENCIDO',
            concepto_pago__permite_mora=True,
            concepto_pago__porcentaje_mora_mensual__isnull=False,
            estudiante__activo=True  # <-- FILTRO AÑADIDO
        ).select_related('institucion', 'concepto_pago')

        for cuenta_original in cuentas_vencidas:
            institucion = cuenta_original.institucion
            
            # 2. Buscamos el concepto 'Intereses por Mora' para esta institución
            concepto_mora = ConceptoPago.objects.filter(
                institucion=institucion, 
                nombre_concepto__iexact="Intereses por Mora" # Nombre estandarizado
            ).first()

            if not concepto_mora:
                self.stdout.write(self.style.WARNING(f"  - Omitiendo institución '{institucion.nombre}': No tiene un 'Concepto de Pago' llamado 'Intereses por Mora'."))
                continue

            # 3. Calculamos la mora (Interés simple diario)
            saldo_pendiente = cuenta_original.saldo_pendiente
            if saldo_pendiente <= 0:
                continue

            tasa_mensual = cuenta_original.concepto_pago.porcentaje_mora_mensual
            tasa_diaria = tasa_mensual / Decimal('30.0')
            dias_vencido = (today - cuenta_original.fecha_vencimiento_especifica).days
            
            # Solo calculamos mora para días positivos
            if dias_vencido <= 0:
                continue

            monto_mora = (saldo_pendiente * (tasa_diaria / Decimal('100.0')) * Decimal(dias_vencido)).quantize(Decimal('0.01'))

            # 4. Creamos o actualizamos la cuenta por mora para el mes actual
            # Esto evita que se genere un cargo por mora todos los días
            cuenta_de_mora, created = CuentaPorCobrarEstudiante.objects.get_or_create(
                estudiante=cuenta_original.estudiante,
                concepto_pago=concepto_mora,
                año=today.year,
                mes=today.month,
                defaults={
                    'monto_asignado': monto_mora,
                    'fecha_vencimiento_especifica': today,
                    'institucion': institucion,
                    'observaciones_internas': f"Mora generada sobre saldo de la cuenta #{cuenta_original.pk}"
                }
            )

            if created:
                self.stdout.write(self.style.SUCCESS(f"  - CREADA cuenta de mora de ${monto_mora} para estudiante {cuenta_original.estudiante}"))
            else:
                # Si ya existía, actualizamos el monto
                cuenta_de_mora.monto_asignado = monto_mora
                cuenta_de_mora.save()
                self.stdout.write(f"  - ACTUALIZADA cuenta de mora a ${monto_mora} para estudiante {cuenta_original.estudiante}")

        self.stdout.write(self.style.SUCCESS("--- Cálculo de moras finalizado ---"))