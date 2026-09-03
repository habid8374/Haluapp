"""Motor adaptativo de Halu Math: maestría por racha (streak).

Deliberadamente más simple que el motor real de DreamBox (que analiza
cada clic/tiempo/patrón de interacción) — este es el diseño explícito
aprobado para el piloto: 3 aciertos seguidos suben de nivel; al llegar a
Alto con la racha completa, el DBA queda dominado. Un error resetea la
racha sin bajar de nivel (no hay "downleveling" en v1).
"""
import random

from django.db.models import Q
from django.utils import timezone

from .models import Dificultad, DominioDBA, EjercicioMath

UMBRAL_RACHA = 5  # aciertos seguidos para subir de nivel / dominar

_ORDEN_NIVELES = [Dificultad.BASICO, Dificultad.MEDIO, Dificultad.ALTO]

# ─── Evaluación por fluidez (fase 2 de 3) ───────────────────────────────────
# Un acierto correcto pero lento/dubitativo demuestra que el estudiante llegó
# al resultado, no que domina el concepto con soltura (el caso real que
# motivó esto: "tardó 45 segundos en una suma simple y acertó, no tiene
# fluidez conceptual, solo cálculo manual lento"). Por eso NO se penaliza la
# progresión de nivel (Básico→Medio→Alto ya mide si el concepto es correcto,
# no la velocidad) pero SÍ se exige, además de la racha normal, una racha de
# aciertos fluidos en el nivel Alto para marcar el DBA como dominado — ver
# DominioDBA.racha_fluida_actual y procesar_respuesta más abajo.

_UMBRAL_TIEMPO_MS = {
    Dificultad.BASICO: 8_000,
    Dificultad.MEDIO: 15_000,
    Dificultad.ALTO: 25_000,
}
UMBRAL_CAMBIOS_FLUIDO = 1  # como máximo 1 cambio de opción/valor antes de enviar, para contar como fluido


def calcular_es_fluido(nivel, tiempo_respuesta_ms, cambios_antes_de_enviar):
    """Índice de fluidez combinado: tiempo de respuesta + cuántas veces
    cambió de opción/valor antes de enviar. Sin telemetría (tiempo_respuesta_ms
    es None — p. ej. un cliente que no la envió) no se penaliza: se asume
    fluido, para no castigar por un dato que el cliente simplemente no
    mandó."""
    if tiempo_respuesta_ms is None:
        return True
    umbral_tiempo = _UMBRAL_TIEMPO_MS.get(nivel, _UMBRAL_TIEMPO_MS[Dificultad.MEDIO])
    return tiempo_respuesta_ms <= umbral_tiempo and cambios_antes_de_enviar <= UMBRAL_CAMBIOS_FLUIDO


def procesar_respuesta(dominio: DominioDBA, es_correcta: bool, es_fluido: bool = True) -> DominioDBA:
    """Actualiza el estado de dominio de un estudiante sobre un DBA a
    partir de un intento. Persiste el cambio y devuelve el dominio
    actualizado."""
    dominio.intentos_totales += 1
    if es_correcta:
        dominio.aciertos_totales += 1
        dominio.racha_actual += 1
        dominio.racha_maxima = max(dominio.racha_maxima, dominio.racha_actual)
        dominio.racha_fluida_actual = dominio.racha_fluida_actual + 1 if es_fluido else 0
        if dominio.racha_actual >= UMBRAL_RACHA:
            indice_actual = _ORDEN_NIVELES.index(dominio.nivel_actual)
            if indice_actual < len(_ORDEN_NIVELES) - 1:
                dominio.nivel_actual = _ORDEN_NIVELES[indice_actual + 1]
                dominio.racha_actual = 0
                dominio.racha_fluida_actual = 0
            elif not dominio.dominado and dominio.racha_fluida_actual >= UMBRAL_RACHA:
                dominio.dominado = True
                dominio.fecha_dominado = timezone.now()
    else:
        dominio.racha_actual = 0
        dominio.racha_fluida_actual = 0
    dominio.save()
    return dominio


def elegir_siguiente_ejercicio(dominio: DominioDBA, institucion):
    """Selecciona un ejercicio del nivel actual del estudiante para ese
    DBA, público o privado de su institución, evitando (cuando sea
    posible) los últimos vistos."""
    from .models import IntentoEjercicioMath

    banco = EjercicioMath.objects.filter(
        dba=dominio.dba, nivel_dificultad=dominio.nivel_actual, activo=True,
    ).filter(Q(es_publica=True) | Q(institucion=institucion))

    vistos_recientes = list(
        IntentoEjercicioMath.objects.filter(estudiante=dominio.estudiante, ejercicio__dba=dominio.dba)
        .order_by('-creado_en').values_list('ejercicio_id', flat=True)[:5]
    )
    sin_repetir = banco.exclude(pk__in=vistos_recientes)
    return sin_repetir.order_by('?').first() or banco.order_by('?').first()


# ─── Retos calificados del Laboratorio Matemático ──────────────────────────
# A diferencia del banco de ejercicios (opción múltiple, necesita contenido
# autorado o generado por IA), un reto de manipulativo es puramente
# numérico: se genera en Python en cada intento, sin banco de contenido.

_RANGOS_RECTA_NUMERICA = {
    Dificultad.BASICO: (0, 20, (5, 10)),
    Dificultad.MEDIO: (0, 100, (10, 20, 25)),
    Dificultad.ALTO: (0, 500, (25, 50, 100)),
}


def generar_reto_recta_numerica(nivel):
    """Devuelve {'inicio': int, 'objetivo': int} dentro del rango del nivel,
    con el objetivo siempre distinto del inicio y dentro de [0, máximo]."""
    minimo, maximo, saltos_posibles = _RANGOS_RECTA_NUMERICA[nivel]
    for _intento in range(10):
        inicio = random.randint(minimo, maximo)
        salto = random.choice(saltos_posibles) * random.choice([1, -1])
        objetivo = inicio + salto
        if minimo <= objetivo <= maximo and objetivo != inicio:
            return {'inicio': inicio, 'objetivo': objetivo}
    # Fallback determinista si el sorteo no cuadró en 10 intentos (rango muy chico)
    return {'inicio': minimo, 'objetivo': min(maximo, minimo + saltos_posibles[0])}


_RANGOS_BLOQUES_BASE10 = {
    Dificultad.BASICO: (1, 20),
    Dificultad.MEDIO: (21, 60),
    Dificultad.ALTO: (61, 99),
}


def generar_reto_bloques_base10(nivel):
    """Devuelve {'objetivo': int} — el total que el estudiante debe formar
    agrupando unidades en decenas."""
    minimo, maximo = _RANGOS_BLOQUES_BASE10[nivel]
    return {'objetivo': random.randint(minimo, maximo)}
