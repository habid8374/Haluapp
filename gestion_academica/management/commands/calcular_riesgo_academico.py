# gestion_academica/management/commands/calcular_riesgo_academico.py

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from datetime import date, timedelta
from gestion_academica.models import Estudiante, PeriodoAcademico, AnalisisRiesgo, PrediccionRiesgoEstudiante
from django.db import transaction

class Command(BaseCommand):
    help = 'Calcula y guarda el riesgo académico de los estudiantes, incluyendo inasistencias y anotaciones.'

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Iniciando HALU Sentinel: Análisis de Riesgo Académico..."))

        periodos_activos = PeriodoAcademico.objects.filter(activo=True)
        if not periodos_activos.exists():
            self.stdout.write(self.style.WARNING("No hay periodos académicos activos. No se puede ejecutar el análisis."))
            return

        for periodo in periodos_activos:
            self.stdout.write(f"Analizando institución: {periodo.institucion.nombre}...")

            analisis = AnalisisRiesgo.objects.create(
                periodo_academico=periodo,
                institucion=periodo.institucion
            )

            UMBRAL_INASISTENCIAS = 3
            UMBRAL_ANOTACIONES = 2
            SEMANAS_DE_GRACIA = 3
            fecha_limite_asistencia = date.today() - timedelta(days=30)
            fecha_limite_calificaciones = periodo.fecha_inicio + timedelta(weeks=SEMANAS_DE_GRACIA)

            estudiantes_a_evaluar = Estudiante.objects.filter(
                activo=True,
                institucion=periodo.institucion
            ).annotate(
                inasistencias_recientes=Count('asistencias', filter=Q(asistencias__fecha__gte=fecha_limite_asistencia) & Q(asistencias__estado='AUSENTE')),
                anotaciones_negativas=Count('anotaciones_observador', filter=Q(anotaciones_observador__tipo='LLAMADO_ATENCION')),
                total_calificaciones_periodo=Count('calificaciones', filter=Q(calificaciones__actividad_calificable__curso__periodo_academico=periodo))
            )
            
            predicciones_a_crear = []
            
            for estudiante in estudiantes_a_evaluar:
                motivos_riesgo = {} # Usamos un diccionario para el campo JSON
                
                if estudiante.inasistencias_recientes >= UMBRAL_INASISTENCIAS:
                    motivos_riesgo['Inasistencias'] = f"{estudiante.inasistencias_recientes} ausencias en los últimos 30 días."
                
                if estudiante.anotaciones_negativas >= UMBRAL_ANOTACIONES:
                    motivos_riesgo['Observador'] = f"{estudiante.anotaciones_negativas} llamados de atención."

                if date.today() > fecha_limite_calificaciones and estudiante.total_calificaciones_periodo == 0:
                    motivos_riesgo['Calificaciones'] = "Sin notas registradas en el periodo."

                if motivos_riesgo:
                    predicciones_a_crear.append(
                        PrediccionRiesgoEstudiante(
                            analisis=analisis,
                            estudiante=estudiante,
                            nivel_riesgo='MEDIO',
                            # --- ✅ INICIO DE LA CORRECCIÓN ---
                            # Usamos el nombre de campo correcto 'factores_influyentes'
                            # y le pasamos el diccionario con los motivos.
                            factores_influyentes=motivos_riesgo,
                            # --- FIN DE LA CORRECCIÓN ---
                            institucion=periodo.institucion
                        )
                    )

            if predicciones_a_crear:
                PrediccionRiesgoEstudiante.objects.bulk_create(predicciones_a_crear)
            
            analisis.resumen = f"Análisis completado. Se generaron {len(predicciones_a_crear)} predicciones de riesgo."
            analisis.save(update_fields=['resumen'])

            self.stdout.write(self.style.SUCCESS(f"Análisis para {periodo.institucion.nombre} finalizado."))