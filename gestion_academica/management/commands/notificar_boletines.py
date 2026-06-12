"""
Encola la notificación por correo de "boletín disponible" para todos los
estudiantes activos de la institución de un período académico.

Uso:
    python manage.py notificar_boletines <periodo_id>
    python manage.py notificar_boletines <periodo_id> --grado <grado_id>
    python manage.py notificar_boletines <periodo_id> --simular

Requiere el worker de Celery activo: los correos se envían en segundo plano.
"""

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        'Notifica por correo a acudientes y estudiantes que el boletín de un '
        'período está disponible. Los correos se encolan en Celery.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'periodo_id',
            type=int,
            help='ID del PeriodoAcademico cuyo boletín se va a notificar.',
        )
        parser.add_argument(
            '--grado',
            type=int,
            default=None,
            help='Limitar el envío a un grado específico (ID del Grado).',
        )
        parser.add_argument(
            '--simular',
            action='store_true',
            help='Solo muestra cuántos correos se enviarían, sin encolar nada.',
        )

    def handle(self, *args, **options):
        from gestion_academica.models import Estudiante, PeriodoAcademico
        from gestion_academica.tasks_notificaciones import notificar_boletin_disponible

        try:
            periodo = PeriodoAcademico.objects.select_related('institucion').get(
                pk=options['periodo_id']
            )
        except PeriodoAcademico.DoesNotExist:
            raise CommandError(f"No existe un período con ID {options['periodo_id']}.")

        estudiantes = Estudiante.objects.filter(
            institucion=periodo.institucion,
            activo=True,
        ).select_related('usuario')

        if options['grado']:
            estudiantes = estudiantes.filter(grado_actual_id=options['grado'])

        total = estudiantes.count()
        self.stdout.write(
            f"Período: {periodo.nombre} ({periodo.año_escolar}) — "
            f"{periodo.institucion.nombre}"
        )
        self.stdout.write(f"Estudiantes activos a notificar: {total}")

        if options['simular']:
            self.stdout.write(self.style.WARNING(
                'Modo simulación: no se encoló ningún correo.'
            ))
            return

        encolados = 0
        for estudiante in estudiantes.iterator():
            notificar_boletin_disponible.delay(estudiante.pk, periodo.pk)
            encolados += 1

        self.stdout.write(self.style.SUCCESS(
            f'✅ {encolados} notificación(es) encoladas en Celery. '
            f'Los correos saldrán en los próximos minutos.'
        ))
