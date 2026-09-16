"""Traduce el progreso de Halu Math (DominioDBA) en una nota del libro de
calificaciones (gestion_academica.Calificacion), a través del modelo
puente ActividadHaluMath.

Fórmula (acordada con el usuario): por cada DBA asignado a la actividad se
da crédito parcial según el nivel alcanzado, y la nota final es el
promedio simple entre todos los DBA asignados. Cualquier práctica cuenta
— banco de ejercicios de opción múltiple y retos del Laboratorio de
manipulativos comparten el mismo DominioDBA, así que no hay que
distinguir el origen.
"""
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _

from gestion_academica.models import Calificacion, Estudiante

from .models import ActividadHaluMath, Dificultad, DominioDBA

NOTA_POR_NIVEL = {
    Dificultad.BASICO: Decimal('2.5'),
    Dificultad.MEDIO: Decimal('3.5'),
    Dificultad.ALTO: Decimal('4.0'),  # nivel alcanzado, aún no dominado
}
NOTA_SIN_PRACTICAR = Decimal('1.0')
NOTA_DOMINADO = Decimal('5.0')


def calcular_nota_estudiante(actividad_halu_math, estudiante):
    """Devuelve la nota (Decimal, escala 1.0-5.0) de un estudiante para
    una ActividadHaluMath, o None si la actividad no tiene DBA asignados."""
    dbas = list(actividad_halu_math.dbas.all())
    if not dbas:
        return None

    dominios = {
        d.dba_id: d for d in DominioDBA.objects.filter(estudiante=estudiante, dba__in=dbas)
    }
    notas = []
    for dba in dbas:
        dominio = dominios.get(dba.pk)
        if dominio is None:
            notas.append(NOTA_SIN_PRACTICAR)
        elif dominio.dominado:
            notas.append(NOTA_DOMINADO)
        else:
            notas.append(NOTA_POR_NIVEL[dominio.nivel_actual])
    return (sum(notas) / len(notas)).quantize(Decimal('0.01'))


def sincronizar_calificacion_estudiante(actividad_halu_math, estudiante):
    """Crea o actualiza la Calificacion de un estudiante para esta
    actividad. La usan tanto el disparo automático como el botón manual
    'Recalcular notas ahora'."""
    nota = calcular_nota_estudiante(actividad_halu_math, estudiante)
    if nota is None:
        return
    Calificacion.objects.update_or_create(
        estudiante=estudiante,
        actividad_calificable=actividad_halu_math.actividad,
        defaults={
            'valor_numerico': nota,
            'observaciones': _(
                "Calculada automáticamente por Halu Math según el dominio de los DBA asignados."
            ),
            'institucion': actividad_halu_math.institucion,
        },
    )


def sincronizar_calificaciones_para_dominio(dominio):
    """Disparo automático: se llama justo después de guardar un
    DominioDBA (desde un ejercicio de opción múltiple o un reto del
    Laboratorio). Solo actualiza actividades cuya ventana siga abierta
    (sin fecha límite, o fecha límite hoy o en el futuro) — una vez
    cerrada, la nota deja de moverse sola y solo cambia con el botón
    manual o una edición directa del docente."""
    hoy = timezone.now().date()
    actividades = ActividadHaluMath.objects.filter(
        dbas=dominio.dba,
        actividad__curso__grado_id=dominio.estudiante.grado_actual_id,
        institucion_id=dominio.institucion_id,
    ).filter(
        Q(actividad__fecha_entrega_limite__isnull=True) | Q(actividad__fecha_entrega_limite__gte=hoy)
    ).select_related('actividad__curso')

    for ahm in actividades:
        curso = ahm.actividad.curso
        if curso.enfasis_id and curso.enfasis_id != getattr(dominio.estudiante, 'enfasis_id', None):
            continue
        sincronizar_calificacion_estudiante(ahm, dominio.estudiante)


def recalcular_todas(actividad_halu_math):
    """Botón manual: recalcula para todos los estudiantes del curso de la
    actividad, sin importar si la ventana ya cerró. Devuelve cuántos
    estudiantes se recalcularon."""
    curso = actividad_halu_math.actividad.curso
    estudiantes = Estudiante.objects.filter(
        institucion=actividad_halu_math.institucion, grado_actual=curso.grado,
    )
    if curso.enfasis_id:
        estudiantes = estudiantes.filter(enfasis_id=curso.enfasis_id)

    total = 0
    for estudiante in estudiantes:
        sincronizar_calificacion_estudiante(actividad_halu_math, estudiante)
        total += 1
    return total
