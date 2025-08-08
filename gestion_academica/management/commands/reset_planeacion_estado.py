# gestion_academica/management/commands/reset_planeacion_estado.py

from django.core.management.base import BaseCommand
from gestion_academica.models import PlaneacionClase

class Command(BaseCommand):
    help = 'Fuerza el reseteo del estado de una planeación que se ha quedado atascada en "Generando".'

    def add_arguments(self, parser):
        # Argumento obligatorio: el ID de la planeación a resetear.
        parser.add_argument('planeacion_id', type=int, help='El ID de la PlaneacionClase que se va a resetear.')
        # Medida de seguridad
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Confirma la ejecución del reseteo.',
        )

    def handle(self, *args, **kwargs):
        planeacion_id = kwargs['planeacion_id']
        
        if not kwargs['confirmar']:
            self.stdout.write(self.style.ERROR('>>> ADVERTENCIA: Esta acción modificará datos en la base de datos.'))
            self.stdout.write(self.style.WARNING('>>> Para ejecutar, añade la bandera: --confirmar'))
            return

        try:
            planeacion = PlaneacionClase.objects.get(pk=planeacion_id)
            self.stdout.write(f"Encontrada planeación: '{planeacion.titulo}' (ID: {planeacion.pk})")

            if planeacion.estado_generacion == 'GENERANDO':
                planeacion.estado_generacion = PlaneacionClase.EstadoGeneracion.FALLIDO
                planeacion.error_generacion = "Proceso reseteado manualmente por el administrador."
                planeacion.save()
                self.stdout.write(self.style.SUCCESS(
                    f"¡Éxito! La planeación ha sido reseteada al estado 'Fallido'."
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f"La planeación no está en estado 'Generando'. Su estado actual es '{planeacion.get_estado_generacion_display()}'. No se realizó ninguna acción."
                ))

        except PlaneacionClase.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Error: No se encontró ninguna planeación con el ID {planeacion_id}."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ocurrió un error inesperado: {e}"))