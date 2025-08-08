from django.core.management.base import BaseCommand
from django.db import transaction
from finanzas.models import PagoRegistrado
from admisiones.models import Aspirante

class Command(BaseCommand):
    help = 'Sincroniza los pagos de inscripción ya registrados para actualizar el estado de los aspirantes a "Admitido".'

    def add_arguments(self, parser):
        # Medida de seguridad para evitar ejecuciones accidentales
        parser.add_argument(
            '--ejecutar',
            action='store_true',
            help='Confirma que realmente deseas ejecutar la sincronización.',
        )

    @transaction.atomic
    def handle(self, *args, **kwargs):
        if not kwargs['ejecutar']:
            self.stdout.write(self.style.ERROR(
                '>>> ADVERTENCIA: Esta acción modificará el estado de los aspirantes.'
            ))
            self.stdout.write(self.style.WARNING(
                '>>> Para ejecutar el script, debes añadir la bandera: --ejecutar'
            ))
            return

        self.stdout.write(self.style.SUCCESS("Iniciando sincronización de pagos de inscripción..."))

        # 1. Buscamos todos los pagos que corresponden a un concepto de inscripción.
        pagos_de_inscripcion = PagoRegistrado.objects.filter(
            cuenta__concepto_pago__es_pago_inscripcion=True
        ).select_related('estudiante__aspirante_origen')

        actualizados = 0
        ya_estaban_ok = 0
        errores = 0

        for pago in pagos_de_inscripcion:
            try:
                # 2. Buscamos al aspirante a través del perfil de estudiante asociado al pago.
                aspirante = pago.estudiante.aspirante_origen
                if not aspirante:
                    self.stdout.write(self.style.WARNING(f"  ! Omitido: El pago #{pago.pk} está asociado a un estudiante sin perfil de aspirante."))
                    errores += 1
                    continue

                # 3. Si el aspirante todavía está como 'INSCRITO', lo actualizamos.
                if aspirante.estado == 'INSCRITO':
                    aspirante.estado = 'ADMITIDO'
                    aspirante.save(update_fields=['estado'])
                    self.stdout.write(self.style.SUCCESS(f"  > Sincronizado: El aspirante '{aspirante}' ha sido actualizado a 'Admitido'."))
                    actualizados += 1
                else:
                    ya_estaban_ok += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  X Error procesando el pago #{pago.pk}: {e}"))
                errores += 1
        
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS("Proceso de sincronización finalizado."))
        self.stdout.write(f"  Aspirantes actualizados a 'Admitido': {actualizados}")
        self.stdout.write(f"  Aspirantes que ya tenían un estado correcto: {ya_estaban_ok}")
        self.stdout.write(f"  Pagos con errores o inconsistencias: {errores}")