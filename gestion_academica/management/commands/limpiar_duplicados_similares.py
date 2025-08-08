from django.core.management.base import BaseCommand
from django.db.models import Q
from gestion_academica.models import Usuario

class Command(BaseCommand):
    help = 'Busca y elimina usuarios con username similar a otro, pero sin estudiante asociado.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--commit',
            action='store_true',
            help='Elimina realmente los duplicados. Sin esto, solo los muestra.',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("--- Buscando usuarios con username similares ---"))
        usuarios_con_estudiante = Usuario.objects.filter(estudiante__isnull=False)

        total_encontrados = 0

        for u in usuarios_con_estudiante:
            base = u.username.split('.')[0]  # Tomamos "estudiante1" de "estudiante1.prueba1"
            similares = Usuario.objects.filter(
                Q(username__icontains=base),
                estudiante__isnull=True  # Solo los que no están asociados
            ).exclude(pk=u.pk)

            if similares.exists():
                self.stdout.write(self.style.WARNING(f"\nUsuario base: {u.username} (ID {u.id})"))
                for dup in similares:
                    self.stdout.write(f" - POSIBLE DUPLICADO: {dup.username} (ID {dup.id})")
                    total_encontrados += 1
                    if options['commit']:
                        try:
                            dup.delete()
                            self.stdout.write(self.style.SUCCESS("   -> Eliminado."))
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"   -> ERROR al eliminar: {e}"))

        if total_encontrados == 0:
            self.stdout.write(self.style.SUCCESS("No se encontraron usuarios similares duplicados."))
        elif not options['commit']:
            self.stdout.write(self.style.NOTICE(f"\nSe encontraron {total_encontrados} duplicados potenciales (no eliminados). Usa --commit para borrarlos."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\n{total_encontrados} usuarios duplicados similares fueron eliminados."))
