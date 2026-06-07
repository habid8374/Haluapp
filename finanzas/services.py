# finanzas/services.py
"""Servicios de negocio del módulo Finanzas.

Contienen la lógica reutilizable que NO debe vivir directamente en views,
signals o management commands para garantizar consistencia entre puntos
de entrada (admin, signal, comando manual, scripts).

Servicios actuales:

* ``sincronizar_conceptos_de_nivel(nivel, *, año=None)``: para un
  ``NivelEscolaridad`` dado, asegura que existan los ``ConceptoPago``
  estándar de ese nivel para la institución correspondiente:
  - 1 ``Inscripción``    (``es_pago_inscripcion=True``, ``valor=valor_inscripcion_estandar``)
  - 1 ``Matrícula AAAA`` (``es_pago_matricula=True``,    ``valor=valor_matricula_estandar``)
  - 10 ``Pensión <mes> AAAA`` Feb–Nov
                          (``es_pago_pension=True``,     ``valor=valor_pension_estandar``)

  Es **idempotente**: si ya existen los conceptos para ese nivel/año, los
  reusa y solo actualiza los valores cuando cambian (sin duplicar).
"""
from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


# Nombres canónicos de los TipoConceptoPago. Mantenerlos aquí evita que
# distintos puntos del código los re-creen con variantes (Mensualidad vs
# Pensión, Matrícula vs Matriculas, etc.).
TIPO_INSCRIPCION = "Inscripción"
TIPO_MATRICULA = "Matrícula"
TIPO_PENSION = "Pensión"

# Meses del año lectivo en los que se cobra mensualidad. Por convención
# colombiana son 10: Feb (2) → Nov (11). Si una institución necesita
# distinto, basta con mover esta constante.
MESES_PENSION = tuple(range(2, 12))


@dataclass
class ResultadoSincronizacionConceptos:
    """Resultado estructurado del servicio de sincronización por nivel."""
    nivel: object
    año: int
    inscripcion: object | None = None
    matricula: object | None = None
    pensiones: list = field(default_factory=list)
    creados: int = 0
    actualizados: int = 0
    sin_cambios: int = 0

    @property
    def total(self) -> int:
        return self.creados + self.actualizados + self.sin_cambios

    def resumen(self) -> str:
        return (
            f"Nivel '{self.nivel}' año {self.año}: "
            f"{self.creados} creados, {self.actualizados} actualizados, "
            f"{self.sin_cambios} sin cambios."
        )


def _año_lectivo_para(institucion, año: Optional[int] = None) -> int:
    """Devuelve el año lectivo a usar.

    Prioriza el ``PeriodoAcademico`` activo de la institución; si no hay,
    usa el año actual del calendario.
    """
    if año is not None:
        return int(año)

    try:
        from gestion_academica.models import PeriodoAcademico
        periodo = (
            PeriodoAcademico.objects
            .filter(institucion=institucion, activo=True)
            .order_by("-año_escolar")
            .first()
        )
        if periodo and periodo.año_escolar:
            return int(periodo.año_escolar)
    except Exception:  # noqa: BLE001 - degradación silenciosa, log y fallback
        logger.warning(
            "No se pudo leer PeriodoAcademico activo para %s; uso año actual.",
            institucion, exc_info=True,
        )
    return timezone.localdate().year


def _get_or_create_tipo(institucion, nombre: str):
    from .models import TipoConceptoPago

    tipo, _ = TipoConceptoPago.objects.get_or_create(
        institucion=institucion,
        nombre=nombre,
        defaults={"descripcion": f"{nombre} (creado automáticamente desde Niveles)."},
    )
    return tipo


def _sync_concepto(
    *,
    institucion,
    nivel,
    tipo,
    nombre_concepto: str,
    valor: Decimal,
    fecha_vencimiento_general: date | None,
    flags_extra: dict,
    año: int,
) -> tuple[object, str]:
    """Crea o actualiza un único ConceptoPago de forma idempotente.

    Retorna ``(concepto, accion)`` donde ``accion`` ∈
    ``{"creado", "actualizado", "sin_cambios"}``.
    """
    from .models import ConceptoPago

    defaults = {
        "tipo_concepto": tipo,
        "valor": valor,
        "automatico": True,
        "nivel_escolaridad": nivel,
        "fecha_vencimiento_general": fecha_vencimiento_general,
        **flags_extra,
    }

    # Identidad del concepto: nombre + tipo + institución (mismo unique_together).
    concepto, created = ConceptoPago.objects.get_or_create(
        institucion=institucion,
        nombre_concepto=nombre_concepto,
        tipo_concepto=tipo,
        defaults=defaults,
    )
    if created:
        return concepto, "creado"

    # ¿Hay diferencias en los campos que controlamos? Si el admin ya editó
    # manualmente algún valor (p. ej. subió la pensión $100k), lo respetamos.
    # Solo refrescamos el `nivel_escolaridad` y los flags si están vacíos.
    cambios = []
    if concepto.nivel_escolaridad_id != getattr(nivel, "pk", None):
        concepto.nivel_escolaridad = nivel
        cambios.append("nivel_escolaridad")

    for flag, valor_flag in flags_extra.items():
        if getattr(concepto, flag) != valor_flag:
            setattr(concepto, flag, valor_flag)
            cambios.append(flag)

    # Si el valor del concepto sigue siendo 0, actualizar al valor del nivel
    # (es el caso típico cuando el admin agregó el concepto manualmente sin
    # poner el monto).
    if (concepto.valor or Decimal("0")) <= Decimal("0") and valor > Decimal("0"):
        concepto.valor = valor
        cambios.append("valor")

    if not concepto.automatico:
        concepto.automatico = True
        cambios.append("automatico")

    if cambios:
        concepto.save(update_fields=cambios)
        return concepto, "actualizado"
    return concepto, "sin_cambios"


@transaction.atomic
def sincronizar_conceptos_de_nivel(nivel, *, año: int | None = None) -> ResultadoSincronizacionConceptos:
    """Asegura los ConceptoPago estándar para un ``NivelEscolaridad``.

    Crea (o actualiza) en la institución del nivel:
      - 1 Inscripción
      - 1 Matrícula <año>
      - 10 Pensiones (Feb–Nov) <año>

    Es **idempotente** y **respeta valores editados a mano** (solo sube
    montos en 0 al `valor_*_estandar` del nivel; el resto los conserva).

    Args:
        nivel: instancia de ``gestion_academica.NivelEscolaridad``.
        año:   año lectivo. Si es None, se toma del PeriodoAcademico
               activo o del año actual.

    Returns:
        ``ResultadoSincronizacionConceptos`` con el detalle por concepto.
    """
    from .models import NOMBRES_MESES_ESPANOL

    if nivel is None or nivel.pk is None:
        raise ValueError("Se requiere un NivelEscolaridad ya guardado en BD.")

    institucion = nivel.institucion
    if institucion is None:
        raise ValueError(
            f"El NivelEscolaridad {nivel} no tiene institución asociada; "
            "no se pueden generar Conceptos de Pago."
        )

    año_lectivo = _año_lectivo_para(institucion, año=año)
    resultado = ResultadoSincronizacionConceptos(nivel=nivel, año=año_lectivo)

    # ---------------- Tipos canónicos ----------------
    tipo_inscripcion = _get_or_create_tipo(institucion, TIPO_INSCRIPCION)
    tipo_matricula = _get_or_create_tipo(institucion, TIPO_MATRICULA)
    tipo_pension = _get_or_create_tipo(institucion, TIPO_PENSION)

    # ---------------- 1. Inscripción ----------------
    # La inscripción NO depende del año lectivo (es única por nivel/institución).
    concepto_insc, accion_insc = _sync_concepto(
        institucion=institucion,
        nivel=nivel,
        tipo=tipo_inscripcion,
        nombre_concepto=f"Inscripción {nivel.nombre}",
        valor=nivel.valor_inscripcion_estandar or Decimal("0"),
        fecha_vencimiento_general=None,
        flags_extra={
            "es_pago_inscripcion": True,
            "es_pago_matricula": False,
            "es_pago_pension": False,
        },
        año=año_lectivo,
    )
    resultado.inscripcion = concepto_insc
    _contabilizar(resultado, accion_insc)

    # ---------------- 2. Matrícula <año> ----------------
    # Vence típicamente al fin del primer mes del año (enero/marzo). Usamos 31/03
    # como default conservador; el admin puede cambiarlo a mano.
    fecha_venc_matricula = date(año_lectivo, 3, 31)
    concepto_mat, accion_mat = _sync_concepto(
        institucion=institucion,
        nivel=nivel,
        tipo=tipo_matricula,
        nombre_concepto=f"Matrícula {nivel.nombre} {año_lectivo}",
        valor=nivel.valor_matricula_estandar or Decimal("0"),
        fecha_vencimiento_general=fecha_venc_matricula,
        flags_extra={
            "es_pago_inscripcion": False,
            "es_pago_matricula": True,
            "es_pago_pension": False,
        },
        año=año_lectivo,
    )
    resultado.matricula = concepto_mat
    _contabilizar(resultado, accion_mat)

    # ---------------- 3. Pensiones Feb–Nov ----------------
    valor_pension = nivel.valor_pension_estandar or Decimal("0")
    for mes_num in MESES_PENSION:
        nombre_mes = NOMBRES_MESES_ESPANOL.get(mes_num, str(mes_num))
        ultimo_dia = calendar.monthrange(año_lectivo, mes_num)[1]
        fecha_venc = date(año_lectivo, mes_num, ultimo_dia)
        concepto_pen, accion_pen = _sync_concepto(
            institucion=institucion,
            nivel=nivel,
            tipo=tipo_pension,
            nombre_concepto=f"Pensión {nombre_mes} {año_lectivo} - {nivel.nombre}",
            valor=valor_pension,
            fecha_vencimiento_general=fecha_venc,
            flags_extra={
                "es_pago_inscripcion": False,
                "es_pago_matricula": False,
                "es_pago_pension": True,
            },
            año=año_lectivo,
        )
        resultado.pensiones.append(concepto_pen)
        _contabilizar(resultado, accion_pen)

    logger.info(resultado.resumen())
    return resultado


def _contabilizar(resultado: ResultadoSincronizacionConceptos, accion: str) -> None:
    if accion == "creado":
        resultado.creados += 1
    elif accion == "actualizado":
        resultado.actualizados += 1
    else:
        resultado.sin_cambios += 1
