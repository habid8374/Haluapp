# finanzas/management/commands/sincronizar_pagos_matricula.py

from django.core.management.base import BaseCommand
from django.db import transaction
from finanzas.models import PagoRegistrado
from admisiones.models import Aspirante
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Sincroniza los pagos de MATRÍCULA ya registrados para actualizar el estado de los aspirantes a "Matriculado".'

    def add_arguments(self, parser):
        # Medida de seguridad para evitar ejecuciones accidentales
        parser.add_argument(
            '--ejecutar',
            action='store_true',
            help='Confirma que realmente deseas ejecutar la sincronización de matrículas.',
        )

    @transaction.atomic
    def handle(self, *args, **kwargs):
        if not kwargs['ejecutar']:
            self.stdout.write(self.style.ERROR(
                '>>> ADVERTENCIA: Esta acción modificará el estado de los aspirantes a "Matriculado".'
            ))
            self.stdout.write(self.style.WARNING(
                '>>> Para ejecutar el script, debes añadir la bandera: --ejecutar'
            ))
            return

        self.stdout.write(self.style.SUCCESS("Iniciando sincronización de pagos de matrícula..."))

        # 1. Buscamos todos los pagos que corresponden a un concepto de matrícula.
        pagos_de_matricula = PagoRegistrado.objects.filter(
            cuenta__concepto_pago__es_pago_matricula=True
        ).select_related('cuenta__aspirante')

        actualizados = 0
        ya_estaban_ok = 0
        errores = 0

        for pago in pagos_de_matricula:
            try:
                # 2. Buscamos al aspirante a través de la cuenta por cobrar asociada al pago.
                aspirante = pago.cuenta.aspirante
                if not aspirante:
                    self.stdout.write(self.style.WARNING(f"  ! Omitido: El pago #{pago.pk} no está asociado a un perfil de aspirante."))
                    errores += 1
                    continue

                # 3. Si el aspirante todavía está como 'APROBADO_MATRICULA', lo matriculamos.
                if aspirante.estado == 'APROBADO_MATRICULA':
                    self.stdout.write(self.style.NOTICE(f"  > Procesando matrícula para '{aspirante}'..."))
                    _, resultado = aspirante.matricular()
                    self.stdout.write(self.style.SUCCESS(
                        f"  > Sincronizado: '{aspirante}' -> Matriculado. {resultado.resumen()}"
                    ))
                    if resultado.es_warning:
                        self.stdout.write(self.style.WARNING(
                            f"  !! Advertencia de cuentas: {resultado.mensaje}"
                        ))
                    actualizados += 1
                else:
                    ya_estaban_ok += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  X Error procesando el pago #{pago.pk} para el aspirante '{aspirante}': {e}"))
                errores += 1
        
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS("Proceso de sincronización de matrículas finalizado."))
        self.stdout.write(f"  Aspirantes matriculados exitosamente: {actualizados}")
        self.stdout.write(f"  Aspirantes que ya estaban matriculados: {ya_estaban_ok}")
        self.stdout.write(f"  Pagos con errores o inconsistencias: {errores}")