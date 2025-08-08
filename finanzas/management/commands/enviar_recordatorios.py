# finanzas/management/commands/enviar_recordatorios.py

import logging
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from django.contrib.sites.models import Site
from django.template.loader import render_to_string
from django.urls import reverse
from django.core.mail import get_connection

# Importamos los modelos y funciones de utilidad necesarios
from finanzas.models import CuentaPorCobrarEstudiante
from admisiones.utils import enviar_correo_dinamico

# Configuración del logger para este archivo
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Envía correos de recordatorio para cuentas por cobrar próximas a vencer o ya vencidas.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("--- Iniciando tarea de envío de recordatorios de pago ---"))
        
        today = timezone.now().date()
        
        # 1. Obtenemos todas las cuentas que podrían necesitar una notificación
        cuentas_a_revisar = CuentaPorCobrarEstudiante.objects.filter(
            estado__in=['PENDIENTE', 'VENCIDO'],
            estudiante__activo=True  # <-- FILTRO AÑADIDO
        ).select_related('institucion', 'estudiante__usuario').order_by('institucion')

        if not cuentas_a_revisar.exists():
            self.stdout.write("No hay cuentas pendientes o vencidas para notificar.")
            self.stdout.write(self.style.SUCCESS("--- Tarea finalizada ---"))
            return

        institucion_actual = None
        connection = None

        for cuenta in cuentas_a_revisar:
            try:
                # Si la institución de esta cuenta es diferente a la anterior, gestionamos la conexión
                if cuenta.institucion != institucion_actual:
                    if connection:
                        connection.close() # Cerramos la conexión anterior
                    
                    institucion_actual = cuenta.institucion
                    
                    # Intentamos abrir una nueva conexión para la institución actual
                    if institucion_actual.email_host_user and institucion_actual.email_host_password:
                        self.stdout.write(f"Abriendo conexión para: {institucion_actual.nombre}")
                        connection = get_connection(
                            host=institucion_actual.email_host,
                            port=institucion_actual.email_port,
                            username=institucion_actual.email_host_user,
                            password=institucion_actual.email_host_password,
                            use_tls=institucion_actual.email_use_tls
                        )
                        connection.open()
                    else:
                        self.stdout.write(self.style.WARNING(f"  - Institución '{institucion_actual.nombre}' no tiene credenciales SMTP. Omitiendo sus correos."))
                        connection = None

                # Si no tenemos una conexión activa para esta institución, pasamos a la siguiente cuenta
                if not connection:
                    continue

                # 2. Decidimos si esta cuenta específica necesita un recordatorio hoy
                tipo_notificacion = None
                if cuenta.estado == 'PENDIENTE' and cuenta.fecha_vencimiento_especifica == (today + timedelta(days=3)):
                    tipo_notificacion = 'proximo_vencimiento'
                elif cuenta.estado == 'VENCIDO':
                    # Podrías añadir lógica más compleja aquí (ej: enviar solo los lunes)
                    tipo_notificacion = 'vencido'

                # 3. Si necesita notificación, la enviamos usando la conexión abierta
                if tipo_notificacion:
                    self.enviar_un_recordatorio(cuenta, tipo_notificacion, connection)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  - Error inesperado procesando cuenta #{cuenta.pk}. Error: {e}"))
                if connection:
                    connection.close() # Cerramos la conexión si falla
                connection = None # Forzamos a reabrir la conexión para la siguiente institución

        # Cerramos la última conexión al finalizar todo el proceso
        if connection:
            connection.close()

        self.stdout.write(self.style.SUCCESS("--- Tarea de envío de recordatorios finalizada ---"))

    def enviar_un_recordatorio(self, cuenta, tipo, connection):
        """Prepara y envía un correo de recordatorio usando una conexión existente."""
        
        institucion = cuenta.institucion
        estudiante = cuenta.estudiante
        email_destinatario = getattr(estudiante, 'email_acudiente', None) or estudiante.usuario.email

        if not email_destinatario:
            self.stdout.write(self.style.WARNING(f"  - Omitido: Cuenta #{cuenta.pk} no tiene email de destinatario."))
            return

        if tipo == 'proximo_vencimiento':
            asunto = f"Recordatorio de Pago Próximo - {institucion.nombre}"
        else: # tipo == 'vencido'
            asunto = f"Aviso de Saldo Vencido - {institucion.nombre}"
        
        domain = Site.objects.get_current().domain
        protocol = 'https' if not settings.DEBUG else 'http'
        portal_url = f"{protocol}://{domain}{reverse('finanzas:mi_estado_de_cuenta')}"
        
        context = {
            'cuenta': cuenta,
            'institucion': institucion,
            'tipo_recordatorio': tipo,
            'portal_url': portal_url
        }
        
        html_content = render_to_string('finanzas/emails/recordatorio_pago.html', context)
        
        # Llamamos a la función de utilidad, pasándole la conexión activa
        exito = enviar_correo_dinamico(
            institucion=institucion,
            asunto=asunto,
            destinatarios=[email_destinatario],
            html_content=html_content,
            connection=connection # <-- ¡Paso clave para reutilizar la conexión!
        )

        if exito:
            self.stdout.write(self.style.SUCCESS(f"  - Recordatorio para cuenta #{cuenta.pk} enviado a {email_destinatario}."))
        else:
            self.stdout.write(self.style.ERROR(f"  - FALLO al enviar recordatorio para cuenta #{cuenta.pk}."))