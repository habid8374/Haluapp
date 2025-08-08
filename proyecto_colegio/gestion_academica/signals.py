from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Estudiante, ConceptoPago, CuentaPorCobrarEstudiante, TipoConceptoPago, PeriodoAcademico
from datetime import date, timedelta
import calendar

@receiver(post_save, sender=Estudiante)
def crear_cuentas_y_conceptos_automaticamente(sender, instance, created, **kwargs):
    if not created:
        return

    año_actual = date.today().year

    # Obtener el periodo académico actual
    periodo = PeriodoAcademico.objects.filter(activo=True).first()

    # Crear o recuperar tipos de concepto
    tipo_matricula, _ = TipoConceptoPago.objects.get_or_create(nombre="Matrícula")
    tipo_mensualidad, _ = TipoConceptoPago.objects.get_or_create(nombre="Mensualidad")

    # Crear conceptos de matrícula y mensualidades si no existen
    conceptos_creados = []

    # Matrícula (Febrero)
    concepto_matricula, created = ConceptoPago.objects.get_or_create(
        nombre_concepto=f"Matrícula {año_actual}",
        defaults={
            'tipo_concepto': tipo_matricula,
            'monto_estandar': instance.valor_matricula,
            'periodo_academico_aplicable': periodo,
            'fecha_vencimiento_general': date(año_actual, 3, 31),
            'automatico': True,
        }
    )
    conceptos_creados.append((concepto_matricula, date(año_actual, 3, 31)))

    # Mensualidades Feb - Nov
    for mes in range(2, 12):
        nombre_mes = calendar.month_name[mes]
        fecha_venc = date(año_actual, mes, calendar.monthrange(año_actual, mes)[1]) + timedelta(days=30)
        concepto_mensualidad, _ = ConceptoPago.objects.get_or_create(
            nombre_concepto=f"Mensualidad {nombre_mes} {año_actual}",
            defaults={
                'tipo_concepto': tipo_mensualidad,
                'monto_estandar': instance.valor_mensualidad,
                'periodo_academico_aplicable': periodo,
                'fecha_vencimiento_general': fecha_venc,
                'automatico': True,
            }
        )
        conceptos_creados.append((concepto_mensualidad, fecha_venc))

    # Crear cuentas por cobrar por cada concepto
    for concepto, vencimiento in conceptos_creados:
        CuentaPorCobrarEstudiante.objects.create(
            estudiante=instance,
            concepto_pago=concepto,
            monto_asignado=concepto.monto_estandar,
            fecha_vencimiento_especifica=vencimiento
        )
