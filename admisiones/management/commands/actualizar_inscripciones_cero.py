# finanzas/management/commands/actualizar_inscripciones_cero.py

from django.core.management.base import BaseCommand
from django.db import transaction
from finanzas.models import CuentaPorCobrarEstudiante, ConceptoPago
from gestion_academica.models import NivelEscolaridad

class Command(BaseCommand):
    help = 'Actualiza el monto de las cuentas por cobrar de inscripción que están en cero, usando el valor del Nivel de Escolaridad.'

    def add_arguments(self, parser):
        # --- MEDIDA DE SEGURIDAD ---
        # El comando no hará nada a menos que se use esta bandera para evitar ejecuciones accidentales.
        parser.add_argument(
            '--ejecutar',
            action='store_true',
            help='Confirma que realmente deseas ejecutar la actualización de los montos.',
        )

    @transaction.atomic
    def handle(self, *args, **kwargs):
        if not kwargs['ejecutar']:
            self.stdout.write(self.style.ERROR(
                '>>> ADVERTENCIA: Esta acción modificará datos en tu base de datos.'
            ))
            self.stdout.write(self.style.WARNING(
                '>>> Para ejecutar el script, debes añadir la bandera: --ejecutar'
            ))
            return

        self.stdout.write(self.style.SUCCESS("Iniciando script para corregir montos de inscripción en cero..."))

        # 1. Buscamos todas las cuentas por cobrar que cumplen tres condiciones:
        #    - Su monto es cero.
        #    - Su concepto de pago está marcado como "pago de inscripción".
        #    - El nivel de escolaridad del estudiante NO es 'Preescolar'.
        cuentas_a_corregir = CuentaPorCobrarEstudiante.objects.filter(
            monto_asignado=0,
            concepto_pago__es_pago_inscripcion=True
        ).exclude(
            estudiante__grado_actual__nivel_escolaridad__nombre__iexact='Preescolar'
        ).select_related(
            'estudiante__grado_actual__nivel_escolaridad' # Optimizamos la consulta
        )

        if not cuentas_a_corregir.exists():
            self.stdout.write(self.style.SUCCESS("No se encontraron cuentas de inscripción en cero para corregir. ¡Todo está en orden!"))
            return

        self.stdout.write(self.style.WARNING(f"Se encontraron {cuentas_a_corregir.count()} cuentas por cobrar para actualizar."))
        
        cuentas_actualizadas = 0
        for cuenta in cuentas_a_corregir:
            try:
                estudiante = cuenta.estudiante
                nivel_escolar = estudiante.grado_actual.nivel_escolaridad
                
                # 2. Obtenemos el precio correcto desde el Nivel de Escolaridad.
                precio_correcto = nivel_escolar.valor_inscripcion_estandar

                if precio_correcto and precio_correcto > 0:
                    valor_anterior = cuenta.monto_asignado
                    
                    # 3. Actualizamos el monto en la cuenta por cobrar.
                    cuenta.monto_asignado = precio_correcto
                    cuenta.save(update_fields=['monto_asignado'])
                    
                    self.stdout.write(self.style.SUCCESS(
                        f"  > Actualizado: Cuenta #{cuenta.pk} para '{estudiante}'. "
                        f"Valor anterior: ${valor_anterior}, Nuevo valor: ${precio_correcto}"
                    ))
                    cuentas_actualizadas += 1
                else:
                    self.stdout.write(self.style.WARNING(
                        f"  ! Omitido: El precio para el nivel '{nivel_escolar.nombre}' también es cero. "
                        f"No se actualizó la cuenta #{cuenta.pk}."
                    ))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  X Error procesando la cuenta #{cuenta.pk} para '{cuenta.estudiante}': {e}"))

        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS("Proceso de actualización finalizado."))
        self.stdout.write(f"Total de cuentas por cobrar actualizadas: {cuentas_actualizadas}")