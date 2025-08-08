# gestion_academica/management/commands/limpiar_duplicados.py

from django.core.management.base import BaseCommand
from django.db.models import F
from gestion_academica.models import Usuario, Estudiante

class Command(BaseCommand):
    help = 'Busca y elimina usuarios duplicados que fueron creados por un error en la matriculación.'

    def add_arguments(self, parser):
        # Añadimos un argumento --commit para hacer el borrado real.
        # Sin este argumento, solo simulará la operación.
        parser.add_argument(
            '--commit',
            action='store_true',
            help='Realiza el borrado de los usuarios duplicados. Sin esto, solo los mostrará.',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("--- Iniciando búsqueda de usuarios duplicados ---"))
        
        # Un usuario duplicado es aquel cuyo username es similar a otro,
        # pero NO está asociado a un perfil de Estudiante.
        
        usuarios_duplicados_encontrados = 0
        
        # 1. Obtenemos todos los usuarios que SÍ son estudiantes.
        usuarios_correctos = Usuario.objects.filter(estudiante__isnull=False)
        
        for usuario_correcto in usuarios_correctos:
            username_base = usuario_correcto.username
            
            # 2. Buscamos otros usuarios cuyo nombre de usuario comience igual
            #    pero que no sean el usuario correcto y que NO tengan un perfil de estudiante.
            posibles_duplicados = Usuario.objects.filter(
                username__startswith=username_base
            ).exclude(
                pk=usuario_correcto.pk # Excluimos al usuario correcto
            ).filter(
                estudiante__isnull=True # ¡Clave! Solo nos interesan los usuarios "vacíos"
            )

            if not posibles_duplicados.exists():
                continue

            self.stdout.write(self.style.WARNING(f"\nSe encontraron duplicados para el usuario correcto: '{username_base}'"))
            
            for duplicado in posibles_duplicados:
                self.stdout.write(f" - [DUPLICADO ENCONTRADO]: '{duplicado.username}' (ID: {duplicado.id})")
                usuarios_duplicados_encontrados += 1

                # 3. Si se pasó el argumento --commit, procedemos a borrar.
                if options['commit']:
                    try:
                        duplicado.delete()
                        self.stdout.write(self.style.SUCCESS(f"   -> '{duplicado.username}' ha sido ELIMINADO."))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"   -> ERROR al eliminar a '{duplicado.username}': {e}"))
        
        if usuarios_duplicados_encontrados == 0:
            self.stdout.write(self.style.SUCCESS("\n¡Excelente! No se encontraron usuarios duplicados."))
        else:
            if options['commit']:
                self.stdout.write(self.style.SUCCESS(f"\n--- Proceso completado. Se eliminaron {usuarios_duplicados_encontrados} usuarios duplicados. ---"))
            else:
                self.stdout.write(self.style.NOTICE(f"\n--- Simulación terminada. Se encontraron {usuarios_duplicados_encontrados} usuarios para eliminar. ---"))
                self.stdout.write(self.style.NOTICE("-> Para borrarlos de verdad, ejecuta el comando con la opción --commit"))