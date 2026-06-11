"""
Carga los DBA oficiales del MEN desde el fixture.
Uso: python manage.py cargar_dba
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Carga el catálogo de DBA oficiales del MEN en la base de datos.'

    def handle(self, *args, **options):
        self.stdout.write('Cargando DBA predefinidos del MEN…')
        call_command('loaddata', 'dba_predefinidos', verbosity=1)
        self.stdout.write(self.style.SUCCESS('DBA cargados correctamente.'))
