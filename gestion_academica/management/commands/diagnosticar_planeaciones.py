# gestion_academica/management/commands/diagnosticar_planeaciones.py

from django.core.management.base import BaseCommand
from gestion_academica.models import PlaneacionClase, Docente

class Command(BaseCommand):
    help = 'Diagnostica y/o elimina forzosamente planeaciones de un docente.'

    def add_arguments(self, parser):
        # Argumento obligatorio: el ID del DOCENTE
        parser.add_argument('docente_id', type=int, help='El ID del Docente cuyo perfil se va a diagnosticar.')
        
        # Argumento opcional para eliminar una planeación específica
        parser.add_argument(
            '--eliminar',
            type=int,
            metavar='PLANEACION_ID',
            help='El ID de la PlaneacionClase que se va a eliminar forzosamente.',
        )

    def handle(self, *args, **kwargs):
        docente_id = kwargs['docente_id']
        planeacion_a_eliminar_id = kwargs['eliminar']

        try:
            docente = Docente.objects.get(pk=docente_id)
            self.stdout.write(self.style.SUCCESS(f"Diagnóstico para el docente: {docente.usuario.get_full_name()} (ID: {docente_id})"))
        except Docente.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Error: No se encontró ningún docente con el ID {docente_id}."))
            return

        # Obtenemos la lista de planeaciones directamente de la base de datos
        planeaciones_en_db = PlaneacionClase.objects.filter(docente=docente)

        if not planeaciones_en_db.exists():
            self.stdout.write(self.style.SUCCESS("VEREDICTO: La base de datos confirma que este docente NO tiene ninguna planeación guardada."))
            return

        self.stdout.write(self.style.WARNING("--- Planeaciones encontradas en la Base de Datos ---"))
        for p in planeaciones_en_db:
            self.stdout.write(f"  - ID: {p.pk}, Título: '{p.titulo}', Estado: {p.estado_generacion}")
        self.stdout.write("----------------------------------------------------")

        if planeacion_a_eliminar_id:
            self.stdout.write(self.style.NOTICE(f"Intentando eliminar forzosamente la planeación con ID: {planeacion_a_eliminar_id}"))
            try:
                planeacion_a_eliminar = planeaciones_en_db.get(pk=planeacion_a_eliminar_id)
                titulo_eliminado = planeacion_a_eliminar.titulo
                planeacion_a_eliminar.delete()
                self.stdout.write(self.style.SUCCESS(f"¡ÉXITO! La planeación '{titulo_eliminado}' ha sido eliminada forzosamente de la base de datos."))
            except PlaneacionClase.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"Error: La planeación con ID {planeacion_a_eliminar_id} no pertenece a este docente o no existe."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Ocurrió un error inesperado durante la eliminación: {e}"))