# gestion_academica/management/commands/cancelar_planeaciones_colgadas.py

from django.core.management.base import BaseCommand
from django.db import transaction
from gestion_academica.models import PlaneacionClase
from datetime import timedelta
from django.utils import timezone

class Command(BaseCommand):
    help = 'Busca planeaciones que lleven mucho tiempo en estado "Generando" y las marca como "Fallido".'

    def add_arguments(self, parser):
        # Medida de seguridad para evitar ejecuciones accidentales
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Confirma que realmente deseas cancelar las planeaciones colgadas.',
        )
        # Argumento opcional para definir el tiempo de espera
        parser.add_argument(
            '--minutos',
            type=int,
            default=10, # Por defecto, cancela las que lleven más de 10 minutos
            help='Número de minutos que una tarea debe llevar en estado "Generando" para ser considerada colgada.',
        )

    @transaction.atomic
    def handle(self, *args, **kwargs):
        if not kwargs['confirmar']:
            self.stdout.write(self.style.ERROR(
                '>>> ADVERTENCIA: Esta acción cambiará el estado de las planeaciones que parezcan estar colgadas.'
            ))
            self.stdout.write(self.style.WARNING(
                '>>> Para ejecutar el comando, debes añadir la bandera: --confirmar'
            ))
            return

        minutos_limite = kwargs['minutos']
        tiempo_limite = timezone.now() - timedelta(minutes=minutos_limite)

        self.stdout.write(self.style.NOTICE(
            f"Buscando planeaciones en estado 'Generando' que no se han actualizado en los últimos {minutos_limite} minutos..."
        ))

        # Buscamos las planeaciones que están "Generando" y cuya última actualización fue hace más de X minutos.
        planeaciones_colgadas = PlaneacionClase.objects.filter(
            estado_generacion=PlaneacionClase.EstadoGeneracion.GENERANDO,
            ultima_actualizacion__lt=tiempo_limite
        )

        if not planeaciones_colgadas.exists():
            self.stdout.write(self.style.SUCCESS("¡Buenas noticias! No se encontraron planeaciones colgadas."))
            return

        self.stdout.write(self.style.WARNING(f"Se encontraron {planeaciones_colgadas.count()} planeaciones para cancelar."))

        for planeacion in planeaciones_colgadas:
            planeacion.estado_generacion = PlaneacionClase.EstadoGeneracion.FALLIDO
            planeacion.error_generacion = f"Proceso cancelado manualmente por el administrador por exceder el tiempo límite de {minutos_limite} minutos."
            planeacion.save()
            self.stdout.write(self.style.SUCCESS(
                f"  > Cancelada: Planeación #{planeacion.pk} ('{planeacion.titulo}')"
            ))
        
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS("Proceso de limpieza finalizado."))