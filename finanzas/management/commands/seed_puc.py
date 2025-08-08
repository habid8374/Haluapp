# finanzas/management/commands/seed_puc.py

from django.core.management.base import BaseCommand
from finanzas.models import CuentaContable

class Command(BaseCommand):
    help = 'Pre-carga la base de datos con un Plan Único de Cuentas (PUC) estándar.'

    def handle(self, *args, **options):
        self.stdout.write("Verificando y creando cuentas contables estándar...")
        
        cuentas_a_crear = [
            # INGRESOS (Clase 4)
            {'codigo': '4145', 'nombre': 'Ingresos Operacionales (Educación)', 'tipo': 'INGRESO'},
            {'codigo': '414505', 'nombre': 'Matrículas y Pensiones', 'tipo': 'INGRESO'},
            {'codigo': '414510', 'nombre': 'Transporte, Alojamiento y Alimentación', 'tipo': 'INGRESO'},
            {'codigo': '4295', 'nombre': 'Ingresos Diversos', 'tipo': 'INGRESO'},
            {'codigo': '429547', 'nombre': 'Intereses por Mora', 'tipo': 'INGRESO'},

            # GASTOS (Clase 5)
            {'codigo': '5105', 'nombre': 'Gastos de Personal', 'tipo': 'GASTO'},
            {'codigo': '510506', 'nombre': 'Sueldos', 'tipo': 'GASTO'},
            {'codigo': '5110', 'nombre': 'Honorarios', 'tipo': 'GASTO'},
            {'codigo': '5120', 'nombre': 'Arrendamientos', 'tipo': 'GASTO'},
            {'codigo': '5135', 'nombre': 'Servicios Públicos', 'tipo': 'GASTO'},
            {'codigo': '5195', 'nombre': 'Gastos Diversos', 'tipo': 'GASTO'},
            {'codigo': '519530', 'nombre': 'Útiles, Papelería y Fotocopias', 'tipo': 'GASTO'},
        ]

        creadas = 0
        for data in cuentas_a_crear:
            _, created = CuentaContable.objects.get_or_create(
                codigo=data['codigo'],
                defaults={'nombre': data['nombre'], 'tipo': data['tipo']}
            )
            if created:
                creadas += 1
        
        self.stdout.write(self.style.SUCCESS(f"Proceso finalizado. Se crearon {creadas} nuevas cuentas contables."))