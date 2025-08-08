# gestion_academica/management/commands/crear_conceptos_iniciales.py
# (Asegúrate de que este archivo esté en la ruta correcta:
#  tu_proyecto/gestion_academica/management/commands/crear_conceptos_iniciales.py)

from django.core.management.base import BaseCommand
from django.utils import timezone # Para usar timezone.localdate()
from datetime import date
import calendar
from decimal import Decimal

# ¡CORRECCIÓN CLAVE: Importar desde finanzas.models!
from finanzas.models import InstitucionEducativa, ConceptoPago, TipoConceptoPago 

# También necesitas PeriodoAcademico si lo usas, pero lo importamos de gestion_academica
from gestion_academica.models import PeriodoAcademico

# Lista de nombres de meses en español (asegúrate de que esta misma lista esté en finanzas/models.py si la usas allí)
NOMBRES_MESES_ESPANOL = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
    7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
}

class Command(BaseCommand):
    help = 'Crea los conceptos de matrícula y mensualidades si no existen para cada institución.'

    def handle(self, *args, **kwargs):
        instituciones = InstitucionEducativa.objects.all()

        if not instituciones.exists():
            self.stdout.write(self.style.WARNING('⚠️ No hay instituciones educativas registradas. No se pueden crear conceptos de pago.'))
            self.stdout.write(self.style.WARNING('Crea al menos una InstitucionEducativa primero.'))
            return

        for institucion in instituciones:
            self.stdout.write(self.style.HTTP_INFO(f'✨ Procesando conceptos para la institución: {institucion.nombre}'))
            
            # Obtener el AÑO ACTUAL (se recomienda usar timezone.localdate())
            año_actual_cmd = timezone.localdate().year

            # Obtener el Periodo Académico activo para esta institución
            # Esto asume que tienes un campo 'institucion' en PeriodoAcademico
            periodo_activo = PeriodoAcademico.objects.filter(activo=True, institucion=institucion).first()
            if not periodo_activo:
                self.stdout.write(self.style.WARNING(f'   ⚠️ No hay un Periodo Académico activo para {institucion.nombre}. Los conceptos se crearán sin periodo asociado.'))

            # --- Lógica para Matrícula ---
            tipo_matricula, created_tipo_matricula = TipoConceptoPago.objects.get_or_create(
                nombre="Matrícula",
                institucion=institucion, # Asigna la institución
                defaults={'descripcion': 'Pago de matrícula inicial de un periodo académico'}
            )
            if created_tipo_matricula:
                self.stdout.write(self.style.SUCCESS(f'   Tipo de Concepto "Matrícula" creado para {institucion.nombre}.'))

            concepto_matricula, created_concepto_matricula = ConceptoPago.objects.get_or_create(
                nombre_concepto=f"Matrícula {año_actual_cmd}",
                institucion=institucion, # Asigna la institución
                tipo_concepto=tipo_matricula,
                defaults={
                    'valor': Decimal('0.00'), # Valor inicial en 0.00, se debe editar manualmente después
                    'fecha_vencimiento_general': date(año_actual_cmd, 3, 31), # Ejemplo: 31 de marzo del año actual
                    'periodo_academico_aplicable': periodo_activo,
                    'automatico': True,
                }
            )
            if created_concepto_matricula:
                self.stdout.write(self.style.SUCCESS(f'   Concepto "Matrícula {año_actual_cmd}" creado para {institucion.nombre}.'))
            else:
                self.stdout.write(self.style.HTTP_NOT_MODIFIED(f'   Concepto "Matrícula {año_actual_cmd}" ya existe para {institucion.nombre}.'))

            # --- Lógica para Mensualidades (Febrero a Noviembre) ---
            tipo_mensualidad, created_tipo_mensualidad = TipoConceptoPago.objects.get_or_create(
                nombre="Mensualidad",
                institucion=institucion, # Asigna la institución
                defaults={'descripcion': 'Pago de mensualidad académica recurrente'}
            )
            if created_tipo_mensualidad:
                self.stdout.write(self.style.SUCCESS(f'   Tipo de Concepto "Mensualidad" creado para {institucion.nombre}.'))

            for mes_num in range(2, 12): # Febrero (2) a Noviembre (11)
                nombre_mes_espanol = NOMBRES_MESES_ESPANOL.get(mes_num, str(mes_num))
                
                # Calcular la fecha de vencimiento: último día del mes en curso
                ultimo_dia_mes_actual = calendar.monthrange(año_actual_cmd, mes_num)[1]
                fecha_vencimiento_concepto = date(año_actual_cmd, mes_num, ultimo_dia_mes_actual)

                nombre_concepto_mensualidad = f"Mensualidad {nombre_mes_espanol} {año_actual_cmd}"
                
                concepto_mensualidad, created_concepto_mensualidad = ConceptoPago.objects.get_or_create(
                    nombre_concepto=nombre_concepto_mensualidad,
                    institucion=institucion, # Asigna la institución
                    tipo_concepto=tipo_mensualidad,
                    defaults={
                        'valor': Decimal('0.00'), # Valor inicial en 0.00, se debe editar manualmente después
                        'fecha_vencimiento_general': fecha_vencimiento_concepto,
                        'periodo_academico_aplicable': periodo_activo,
                        'automatico': True,
                    }
                )
                if created_concepto_mensualidad:
                    self.stdout.write(self.style.SUCCESS(f'   Concepto "{nombre_concepto_mensualidad}" creado para {institucion.nombre}.'))
                else:
                    self.stdout.write(self.style.HTTP_NOT_MODIFIED(f'   Concepto "{nombre_concepto_mensualidad}" ya existe para {institucion.nombre}.'))

        self.stdout.write(self.style.SUCCESS('\n✅ Proceso de creación/verificación de conceptos finalizado para todas las instituciones.'))