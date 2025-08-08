# admisiones/management/commands/eliminar_todos_los_estudiantes.py

from django.core.management.base import BaseCommand
from django.db import transaction
from django.apps import apps

# Importamos los modelos de forma segura para evitar errores si una app no existe
Estudiante = apps.get_model('gestion_academica', 'Estudiante')
Usuario = apps.get_model('gestion_academica', 'Usuario')
AnotacionObservador = apps.get_model('gestion_academica', 'AnotacionObservador')
Calificacion = apps.get_model('gestion_academica', 'Calificacion')
EntregaDeber = apps.get_model('gestion_academica', 'EntregaDeber')
Aspirante = apps.get_model('admisiones', 'Aspirante')
PagoRegistrado = apps.get_model('finanzas', 'PagoRegistrado')
CuentaPorCobrarEstudiante = apps.get_model('finanzas', 'CuentaPorCobrarEstudiante')

class Command(BaseCommand):
    help = 'Elimina TODOS los estudiantes, sus usuarios y todos los datos asociados (financieros, académicos, etc.).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar-eliminacion',
            action='store_true',
            help='Confirma que realmente deseas eliminar todos los datos de los estudiantes.',
        )

    @transaction.atomic
    def handle(self, *args, **kwargs):
        if not kwargs['confirmar_eliminacion']:
            self.stdout.write(self.style.ERROR(
                '>>> ADVERTENCIA: Esta acción es destructiva y eliminará permanentemente los datos.'
            ))
            self.stdout.write(self.style.WARNING(
                '>>> Para ejecutar el comando, debes añadir la bandera: --confirmar-eliminacion'
            ))
            return

        self.stdout.write(self.style.WARNING('Iniciando eliminación masiva...'))

        estudiantes_a_eliminar = Estudiante.objects.filter(usuario__is_superuser=False)
        total_estudiantes = estudiantes_a_eliminar.count()

        if total_estudiantes == 0:
            self.stdout.write(self.style.SUCCESS('No se encontraron estudiantes para eliminar.'))
            return

        # --- INICIO DE LA LÓGICA DE ELIMINACIÓN EN ORDEN CORRECTO ---
        
        self.stdout.write(f'Eliminando {PagoRegistrado.objects.filter(estudiante__in=estudiantes_a_eliminar).count()} registros de pagos...')
        PagoRegistrado.objects.filter(estudiante__in=estudiantes_a_eliminar).delete()

        self.stdout.write(f'Eliminando {CuentaPorCobrarEstudiante.objects.filter(estudiante__in=estudiantes_a_eliminar).count()} cuentas por cobrar...')
        CuentaPorCobrarEstudiante.objects.filter(estudiante__in=estudiantes_a_eliminar).delete()
        
        self.stdout.write(f'Eliminando {Calificacion.objects.filter(estudiante__in=estudiantes_a_eliminar).count()} calificaciones...')
        Calificacion.objects.filter(estudiante__in=estudiantes_a_eliminar).delete()
        
        self.stdout.write(f'Eliminando {EntregaDeber.objects.filter(estudiante__in=estudiantes_a_eliminar).count()} entregas de deberes...')
        EntregaDeber.objects.filter(estudiante__in=estudiantes_a_eliminar).delete()

        self.stdout.write(f'Eliminando {AnotacionObservador.objects.filter(estudiante__in=estudiantes_a_eliminar).count()} anotaciones del observador...')
        AnotacionObservador.objects.filter(estudiante__in=estudiantes_a_eliminar).delete()

        self.stdout.write('Eliminando perfiles de aspirante asociados...')
        Aspirante.objects.filter(estudiante_creado__in=estudiantes_a_eliminar).delete()
        
        # --- FIN DE LA LÓGICA DE ELIMINACIÓN DE DEPENDENCIAS ---

        usuarios_ids_a_eliminar = list(estudiantes_a_eliminar.values_list('usuario_id', flat=True))

        self.stdout.write(f'Eliminando {total_estudiantes} perfiles de estudiante...')
        estudiantes_a_eliminar.delete()

        self.stdout.write(f'Eliminando {len(usuarios_ids_a_eliminar)} cuentas de usuario asociadas...')
        Usuario.objects.filter(pk__in=usuarios_ids_a_eliminar).delete()

        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS(
            f'¡Limpieza completada! Se eliminaron {total_estudiantes} estudiantes y todos sus datos asociados.'
        ))