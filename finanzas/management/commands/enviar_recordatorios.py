# finanzas/management/commands/enviar_recordatorios.py

from django.core.management.base import BaseCommand

from finanzas.models import CuentaPorCobrarEstudiante
from finanzas.recordatorios import enviar_recordatorios_pago


class Command(BaseCommand):
    help = 'Envía correos de recordatorio para cuentas por cobrar próximas a vencer o ya vencidas.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("--- Iniciando tarea de envío de recordatorios de pago ---"))

        cuentas_a_revisar = CuentaPorCobrarEstudiante.objects.filter(
            estado__in=['PENDIENTE', 'VENCIDO'],
            estudiante__activo=True,
        ).order_by('institucion')

        if not cuentas_a_revisar.exists():
            self.stdout.write("No hay cuentas pendientes o vencidas para revisar.")
            self.stdout.write(self.style.SUCCESS("--- Tarea finalizada ---"))
            return

        resultado = enviar_recordatorios_pago(cuentas_a_revisar)

        self.stdout.write(self.style.SUCCESS(f"Recordatorios enviados: {resultado['enviados']}"))
        if resultado['sin_email']:
            self.stdout.write(self.style.WARNING(f"Cuentas omitidas por falta de email: {resultado['sin_email']}"))
        if resultado['sin_canal']:
            self.stdout.write(self.style.WARNING(
                "Instituciones sin Brevo ni SMTP configurado (se omitieron): "
                + ", ".join(sorted(resultado['sin_canal']))
            ))

        self.stdout.write(self.style.SUCCESS("--- Tarea de envío de recordatorios finalizada ---"))
