# finanzas/managers.py
"""Managers de modelos financieros.

Aquí vive la lógica de negocio reutilizable de cuentas por cobrar.
La generación de las 10 mensualidades anuales (Feb–Nov) y la cuenta de
matrícula del estudiante se centralizan en
``CuentaPorCobrarEstudianteManager.sincronizar_cuentas_automaticas``.

Decisiones clave (Fase B):

* Buscamos los ``ConceptoPago`` por **flag** ``es_pago_pension=True`` y
  ``es_pago_matricula=True``, **y filtrados por nivel de escolaridad**.
  Antes se buscaba por ``tipo_concepto.nombre__icontains='pensión'``, lo
  que rompía cuando el TipoConceptoPago se llamaba "Mensualidad".
* El **año lectivo** se toma del ``PeriodoAcademico`` activo de la
  institución (no de ``now().year``); fallback al año actual.
* No se crean ``ConceptoPago`` "al vuelo" desde aquí: deben existir
  previamente (creados por la signal ``post_save`` de ``NivelEscolaridad``
  o por el comando ``crear_conceptos``). Si no existen, se reporta como
  warning estructurado para que el admin lo solucione.
* Devuelve ``ResultadoSincronizacionCuentas``: tupla rica con los
  contadores y motivos de fallo, para que las vistas/management commands
  puedan mostrar mensajes claros al admin.
"""
from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from django.db import models, transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


# Motivos accionables por configuración (no errores técnicos del sistema).
MOTIVOS_WARNING_CUENTAS = frozenset({
    "estudiante_inactivo",
    "sin_grado",
    "sin_nivel_escolaridad",
    "sin_concepto_pension",
    "sin_concepto_matricula",
    "sin_periodo_activo",
})


@dataclass
class ResultadoSincronizacionCuentas:
    """Resultado de ``sincronizar_cuentas_automaticas``.

    Atributos:
        estudiante:        instancia del estudiante.
        año:               año lectivo aplicado.
        cuentas_pension_creadas:  pensiones nuevas creadas en este run.
        cuentas_pension_existentes: pensiones que ya existían.
        cuenta_matricula_creada:  bool, si se creó la matrícula nueva.
        cuenta_matricula_existente: bool, si la matrícula ya existía.
        motivo_falla:      None o etiqueta corta del problema.
        mensaje:           texto humano para mostrar al admin.
    """
    estudiante: object
    año: int = 0
    cuentas_pension_creadas: int = 0
    cuentas_pension_existentes: int = 0
    cuenta_matricula_creada: bool = False
    cuenta_matricula_existente: bool = False
    motivo_falla: Optional[str] = None
    mensaje: str = ""

    @property
    def es_exito(self) -> bool:
        return self.motivo_falla is None

    @property
    def es_warning(self) -> bool:
        return self.motivo_falla in MOTIVOS_WARNING_CUENTAS

    @property
    def total_cuentas_creadas(self) -> int:
        return self.cuentas_pension_creadas + (1 if self.cuenta_matricula_creada else 0)

    def resumen(self) -> str:
        if not self.es_exito:
            return f"[{self.motivo_falla}] {self.mensaje}"
        partes = [
            f"{self.cuentas_pension_creadas}/{10} pensiones nuevas",
            f"({self.cuentas_pension_existentes} ya existian)",
        ]
        if self.cuenta_matricula_creada:
            partes.append("matricula creada")
        elif self.cuenta_matricula_existente:
            partes.append("matricula ya existia")
        return f"Estudiante {self.estudiante}: " + ", ".join(partes) + f" (año {self.año})."


def _año_lectivo_para(institucion) -> int:
    """Año lectivo según ``PeriodoAcademico.activo`` o el actual."""
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
    except Exception:  # noqa: BLE001
        logger.warning(
            "No se pudo leer PeriodoAcademico activo para %s; uso año actual.",
            institucion, exc_info=True,
        )
    return timezone.localdate().year


class CuentaPorCobrarEstudianteManager(models.Manager):
    """Manager para centralizar la lógica de negocio de las Cuentas por Cobrar."""

    @transaction.atomic
    def sincronizar_cuentas_automaticas(self, estudiante) -> ResultadoSincronizacionCuentas:
        """Crea las cuentas de matrícula + 10 pensiones anuales para un estudiante.

        Es **idempotente** (usa ``get_or_create`` por mes/año/concepto).
        Aplica los descuentos activos del estudiante a cada cuenta.

        Devuelve un ``ResultadoSincronizacionCuentas`` con detalle del éxito
        o motivo de falla. Las vistas que llamen a este método pueden usar
        ``resultado.es_warning`` para mostrar mensajes accionables al admin
        (en vez de fallar silenciosamente).
        """
        from .models import ConceptoPago, NOMBRES_MESES_ESPANOL

        resultado = ResultadoSincronizacionCuentas(estudiante=estudiante)

        # ---- Validaciones tempranas ------------------------------------
        if not estudiante.activo:
            resultado.motivo_falla = "estudiante_inactivo"
            resultado.mensaje = (
                f"El estudiante {estudiante} no está activo; no se generan cuentas."
            )
            return resultado

        if not estudiante.grado_actual:
            resultado.motivo_falla = "sin_grado"
            resultado.mensaje = (
                f"El estudiante {estudiante} no tiene grado asignado."
            )
            return resultado

        nivel_escolar = estudiante.grado_actual.nivel_escolaridad
        if nivel_escolar is None:
            resultado.motivo_falla = "sin_nivel_escolaridad"
            resultado.mensaje = (
                f"El grado '{estudiante.grado_actual}' no tiene Nivel de Escolaridad. "
                "Asígnalo desde Gestion Academica -> Grados."
            )
            return resultado

        institucion = estudiante.institucion
        if institucion is None:
            resultado.motivo_falla = "sin_grado"
            resultado.mensaje = f"El estudiante {estudiante} no tiene institución."
            return resultado

        # ---- Año lectivo ------------------------------------------------
        año_lectivo = _año_lectivo_para(institucion)
        resultado.año = año_lectivo

        # ---- Refresco de precios en el perfil del estudiante -----------
        # Si los valores del estudiante están vacíos/0, los inicializamos
        # con los del nivel. NO los pisamos si ya tienen valor (puede venir
        # de un descuento o config personalizada).
        cambios_estudiante = []
        if not estudiante.valor_mensualidad or estudiante.valor_mensualidad <= 0:
            estudiante.valor_mensualidad = nivel_escolar.valor_pension_estandar
            cambios_estudiante.append("valor_mensualidad")
        if not estudiante.valor_matricula or estudiante.valor_matricula <= 0:
            estudiante.valor_matricula = nivel_escolar.valor_matricula_estandar
            cambios_estudiante.append("valor_matricula")
        if cambios_estudiante:
            estudiante.save(update_fields=cambios_estudiante)
            logger.info(
                "Precios inicializados desde nivel '%s' para estudiante %s: %s",
                nivel_escolar, estudiante, cambios_estudiante,
            )

        # ---- 1) Cuenta de matrícula del año lectivo --------------------
        try:
            concepto_matricula = ConceptoPago.objects.get(
                institucion=institucion,
                es_pago_matricula=True,
                nivel_escolaridad=nivel_escolar,
            )
        except ConceptoPago.DoesNotExist:
            resultado.motivo_falla = "sin_concepto_matricula"
            resultado.mensaje = (
                f"No existe ConceptoPago de matrícula para nivel "
                f"'{nivel_escolar}'. Crea/edita el Nivel para que la signal "
                "lo genere o ejecuta `manage.py crear_conceptos`."
            )
            return resultado
        except ConceptoPago.MultipleObjectsReturned:
            resultado.motivo_falla = "sin_concepto_matricula"
            resultado.mensaje = (
                f"Hay MÁS DE UN ConceptoPago de matrícula para nivel "
                f"'{nivel_escolar}'. Deja activo solo uno."
            )
            return resultado

        cuenta_mat, created_mat = self._crear_cuenta_individual(
            estudiante=estudiante,
            concepto=concepto_matricula,
            año=año_lectivo,
            mes=None,  # matrícula no es mensual
            monto_base=concepto_matricula.valor or estudiante.valor_matricula,
            fecha_vencimiento=(
                concepto_matricula.fecha_vencimiento_general
                or date(año_lectivo, 3, 31)
            ),
            institucion=institucion,
        )
        if created_mat:
            resultado.cuenta_matricula_creada = True
        else:
            resultado.cuenta_matricula_existente = True

        # ---- 2) Cuentas de pensión Feb–Nov -----------------------------
        conceptos_pension = list(
            ConceptoPago.objects.filter(
                institucion=institucion,
                es_pago_pension=True,
                nivel_escolaridad=nivel_escolar,
            )
        )
        if not conceptos_pension:
            resultado.motivo_falla = "sin_concepto_pension"
            resultado.mensaje = (
                f"No existen ConceptoPago de pensión para nivel "
                f"'{nivel_escolar}' año {año_lectivo}. Crea/edita el Nivel "
                "para que la signal los genere o ejecuta "
                "`manage.py crear_conceptos`."
            )
            return resultado

        # Indexamos por (mes, año) extraído del nombre y/o fecha del concepto.
        # Si la signal los creó, su fecha_vencimiento_general apunta al mes.
        for mes_num in range(2, 12):  # Feb–Nov
            nombre_mes = NOMBRES_MESES_ESPANOL.get(mes_num, "")
            concepto_mes = self._concepto_pension_para_mes(
                conceptos_pension, mes_num, año_lectivo, nombre_mes,
            )
            if concepto_mes is None:
                # Caso borde: hay conceptos de pensión pero no para este mes/año
                # exacto. No abortamos; continuamos con los demás meses.
                logger.warning(
                    "No hay ConceptoPago de pensión para mes %s año %s nivel %s. "
                    "Saltando.",
                    mes_num, año_lectivo, nivel_escolar,
                )
                continue

            fecha_vto = concepto_mes.fecha_vencimiento_general or self._ultimo_dia_mes(
                año_lectivo, mes_num
            )

            # Aplicamos descuentos activos del estudiante
            monto_base = concepto_mes.valor or estudiante.valor_mensualidad
            monto_final, observaciones = self._aplicar_descuentos(
                estudiante, concepto_mes, monto_base,
            )

            _, created = self._crear_cuenta_individual(
                estudiante=estudiante,
                concepto=concepto_mes,
                año=año_lectivo,
                mes=mes_num,
                monto_base=monto_final,
                fecha_vencimiento=fecha_vto,
                institucion=institucion,
                observaciones=observaciones,
            )
            if created:
                resultado.cuentas_pension_creadas += 1
            else:
                resultado.cuentas_pension_existentes += 1

        resultado.mensaje = resultado.resumen()
        logger.info(resultado.resumen())
        return resultado

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _concepto_pension_para_mes(self, conceptos, mes, año, nombre_mes):
        """Selecciona el ConceptoPago que corresponde al mes/año dado.

        Estrategia (en este orden):
          1. ``fecha_vencimiento_general.month == mes`` (más confiable).
          2. ``nombre_concepto`` contiene el nombre del mes y el año.
          3. Primer concepto si es el único.
        """
        if not conceptos:
            return None

        # 1) Por fecha de vencimiento
        for c in conceptos:
            if c.fecha_vencimiento_general and c.fecha_vencimiento_general.month == mes \
                    and c.fecha_vencimiento_general.year == año:
                return c

        # 2) Por nombre
        nombre_low = (nombre_mes or "").lower()
        año_str = str(año)
        for c in conceptos:
            nc = (c.nombre_concepto or "").lower()
            if nombre_low and nombre_low in nc and año_str in nc:
                return c

        # 3) Si hay solo uno, asumimos que aplica a todos
        if len(conceptos) == 1:
            return conceptos[0]

        return None

    @staticmethod
    def _ultimo_dia_mes(año, mes):
        from datetime import date
        ultimo = calendar.monthrange(año, mes)[1]
        return date(año, mes, ultimo)

    def _aplicar_descuentos(self, estudiante, concepto, monto_base):
        """Aplica descuentos activos del estudiante.

        Retorna ``(monto_final, observaciones_internas)``.
        """
        monto_final = monto_base
        descuentos_str = []

        # `descuentos` es un M2M opcional en algunos modelos; lo manejamos defensivamente.
        rel = getattr(estudiante, "descuentos", None)
        if rel is not None:
            try:
                qs_descuentos = rel.filter(activo=True)
            except Exception:  # noqa: BLE001
                qs_descuentos = []
            for descuento in qs_descuentos:
                aplica = (
                    not descuento.conceptos_aplicables.exists()
                    or descuento.conceptos_aplicables.filter(pk=concepto.pk).exists()
                )
                if not aplica:
                    continue

                if descuento.tipo == "PORCENTAJE":
                    monto_descuento = monto_base * (descuento.valor / Decimal("100.0"))
                else:
                    monto_descuento = descuento.valor

                monto_final -= monto_descuento
                descuentos_str.append(
                    f"{descuento.nombre}: -${monto_descuento:,.2f}"
                )

        if monto_final < 0:
            monto_final = Decimal("0.00")

        observaciones = f"Monto original: ${monto_base:,.2f}. "
        if descuentos_str:
            observaciones += "Descuentos aplicados: " + ", ".join(descuentos_str)
        return monto_final, observaciones

    def _crear_cuenta_individual(
        self,
        *,
        estudiante,
        concepto,
        año,
        mes,
        monto_base,
        fecha_vencimiento,
        institucion,
        observaciones: str = "",
    ):
        """``get_or_create`` blindado de la cuenta por cobrar."""
        defaults = {
            "monto_asignado": monto_base,
            "fecha_vencimiento_especifica": fecha_vencimiento,
            "institucion": institucion,
            "observaciones_internas": observaciones,
        }
        if mes is None:
            # Cuenta de matrícula: clave por (estudiante, concepto, año)
            cuenta, created = self.get_queryset().get_or_create(
                estudiante=estudiante,
                concepto_pago=concepto,
                año=año,
                defaults=defaults,
            )
        else:
            cuenta, created = self.get_queryset().get_or_create(
                estudiante=estudiante,
                concepto_pago=concepto,
                año=año,
                mes=mes,
                defaults=defaults,
            )
        return cuenta, created
