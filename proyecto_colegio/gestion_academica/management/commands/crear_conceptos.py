from django.core.management.base import BaseCommand
from gestion_academica.models import ConceptoPago, TipoConceptoPago, PeriodoAcademico

class Command(BaseCommand):
    help = 'Crea los conceptos de matrícula y mensualidades si no existen'

    def handle(self, *args, **kwargs):
        tipo, _ = TipoConceptoPago.objects.get_or_create(nombre="Mensualidad")
        periodo = PeriodoAcademico.objects.filter(activo=True).first()

        nombres_meses = ["Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre"]
        for i, mes in enumerate(nombres_meses, start=2):
            nombre = f"Mensualidad {mes}"
            ConceptoPago.objects.get_or_create(
                nombre_concepto=nombre,
                tipo_concepto=tipo,
                monto_estandar=0.0,
                periodo_academico_aplicable=periodo,
                automatico=True
            )

        ConceptoPago.objects.get_or_create(
            nombre_concepto="Matrícula",
            tipo_concepto=tipo,
            monto_estandar=0.0,
            periodo_academico_aplicable=periodo,
            automatico=True
        )

        self.stdout.write(self.style.SUCCESS('✅ Conceptos creados o ya existentes.'))
