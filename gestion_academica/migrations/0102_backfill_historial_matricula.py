"""Backfill de HistorialMatriculaAnual para años anteriores a la creación de
esta tabla. Infiere el grado que cada estudiante tuvo en cada año escolar a
partir de sus calificaciones (Calificacion -> ActividadCalificable -> Curso
-> grado + periodo_academico.año_escolar) — la única fuente histórica ya
guardada en la base de datos que permite reconstruir ese dato.

Reglas:
- Un solo grado distinto entre las calificaciones de ese año -> confianza ALTA.
- Varios grados distintos (caso inconsistente/raro) -> se usa el más
  frecuente, marcado como DUDOSA para que quede visible y revisable en el
  admin (HistorialMatriculaAnualAdmin filtra por 'confianza_backfill').
- Sin ninguna calificación ese año: si es el año escolar ACTUALMENTE activo
  de la institución, se usa el grado_actual del estudiante (dato vivo, no
  hay que inferir nada) con confianza ALTA. Si es un año distinto sin
  ninguna calificación, no se crea nada — no hay ninguna señal de la que
  partir, y es preferible dejarlo sin backfillear a inventar un dato.
"""
from collections import Counter

from django.db import migrations


def backfill_historial_matricula(apps, schema_editor):
    Estudiante = apps.get_model('gestion_academica', 'Estudiante')
    Calificacion = apps.get_model('gestion_academica', 'Calificacion')
    PeriodoAcademico = apps.get_model('gestion_academica', 'PeriodoAcademico')
    HistorialMatriculaAnual = apps.get_model('gestion_academica', 'HistorialMatriculaAnual')

    for estudiante in Estudiante.objects.filter(institucion__isnull=False).iterator():
        años_institucion = list(
            PeriodoAcademico.objects.filter(institucion_id=estudiante.institucion_id)
            .values_list('año_escolar', flat=True).distinct()
        )
        if not años_institucion:
            continue
        año_activo = (
            PeriodoAcademico.objects.filter(
                institucion_id=estudiante.institucion_id, activo=True,
            ).values_list('año_escolar', flat=True).first()
        )

        for año in años_institucion:
            if HistorialMatriculaAnual.objects.filter(
                estudiante_id=estudiante.pk, año_escolar=año,
            ).exists():
                continue

            grados_del_año = list(
                Calificacion.objects.filter(
                    estudiante_id=estudiante.pk,
                    actividad_calificable__curso__institucion_id=estudiante.institucion_id,
                    actividad_calificable__curso__periodo_academico__año_escolar=año,
                ).values_list('actividad_calificable__curso__grado_id', flat=True)
            )

            if grados_del_año:
                conteo = Counter(grados_del_año)
                grado_id, _n = conteo.most_common(1)[0]
                confianza = 'ALTA' if len(conteo) == 1 else 'DUDOSA'
            elif año == año_activo and estudiante.grado_actual_id:
                grado_id = estudiante.grado_actual_id
                confianza = 'ALTA'
            else:
                continue

            HistorialMatriculaAnual.objects.get_or_create(
                estudiante_id=estudiante.pk, año_escolar=año,
                defaults={
                    'institucion_id': estudiante.institucion_id,
                    'grado_id': grado_id,
                    'grupo_id': estudiante.grupo_id if año == año_activo else None,
                    'origen': 'INFERIDO',
                    'confianza_backfill': confianza,
                },
            )


def eliminar_backfill(apps, schema_editor):
    HistorialMatriculaAnual = apps.get_model('gestion_academica', 'HistorialMatriculaAnual')
    HistorialMatriculaAnual.objects.filter(origen='INFERIDO').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0101_historialmatriculaanual'),
    ]

    operations = [
        migrations.RunPython(backfill_historial_matricula, eliminar_backfill),
    ]
