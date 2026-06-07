"""Reconciliación entre Mercado Pago y la BD local de Halu (Fase 3).

Cuándo usarlo:
- El webhook puede haberse perdido (caída de servidor, MP no reintentó, firma
  mal configurada por un par de horas...). Este comando consulta los pagos
  APROBADOS en MP en un rango de fechas y verifica que cada uno tenga su
  ``PagoRegistrado`` local.
- Al final del día / cierre semanal por institución.

Estrategia:
1. Para cada institución (o la indicada con --institucion) que tenga
   credenciales MP:
2. Llama a ``payment.search`` paginado entre ``--desde`` y ``--hasta``.
3. Para cada pago APROBADO:
   - Si la ``external_reference`` apunta a una ``CuentaPorCobrarEstudiante``
     de la institución y NO existe ``PagoRegistrado`` con ese
     ``referencia_transaccion``, lo crea (a menos que --dry-run).
   - Reporta acciones tomadas.

Aislamiento SaaS:
- Cada institución se procesa con SUS credenciales y SUS cuentas; nunca se
  cruza información entre tenants.

Uso:
    python manage.py reconciliar_pagos_mercadopago --desde 2026-05-01
    python manage.py reconciliar_pagos_mercadopago --institucion 3 --desde 2026-05-01 --hasta 2026-05-12
    python manage.py reconciliar_pagos_mercadopago --desde 2026-05-01 --dry-run
"""
from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from finanzas.mercadopago_client import (
    MercadoPagoError,
    MercadoPagoSinCredenciales,
    buscar_pagos_aprobados,
)
from finanzas.models import (
    CuentaPorCobrarEstudiante,
    InstitucionEducativa,
    PagoRegistrado,
)


PAGE_SIZE = 50


class Command(BaseCommand):
    help = (
        "Reconcilia pagos APROBADOS en Mercado Pago contra los PagoRegistrado "
        "locales de cada institución. Crea los faltantes."
    )

    def add_arguments(self, parser):
        parser.add_argument("--institucion", type=int, default=None,
                            help="ID de una institución específica.")
        parser.add_argument("--desde", required=True,
                            help="Fecha inicial (YYYY-MM-DD).")
        parser.add_argument("--hasta", default=None,
                            help="Fecha final (YYYY-MM-DD). Por defecto: hoy.")
        parser.add_argument("--dry-run", action="store_true",
                            help="No crea registros, solo reporta.")

    def handle(self, *args, **options):
        try:
            desde = dt.date.fromisoformat(options["desde"])
        except ValueError:
            raise CommandError("--desde debe ser YYYY-MM-DD")
        if options["hasta"]:
            try:
                hasta = dt.date.fromisoformat(options["hasta"])
            except ValueError:
                raise CommandError("--hasta debe ser YYYY-MM-DD")
        else:
            hasta = dt.date.today()
        if hasta < desde:
            raise CommandError("--hasta no puede ser anterior a --desde.")

        instituciones = InstitucionEducativa.objects.all()
        if options["institucion"]:
            instituciones = instituciones.filter(pk=options["institucion"])
            if not instituciones.exists():
                raise CommandError(
                    f"No existe la institución con ID {options['institucion']}."
                )

        dry_run = options["dry_run"]
        total_creados = 0
        total_existentes = 0
        total_huerfanos = 0

        for inst in instituciones:
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"\n=== {inst} (id={inst.id}) ==="
            ))
            try:
                resumen = self._reconciliar_institucion(inst, desde, hasta, dry_run)
            except MercadoPagoSinCredenciales as exc:
                self.stdout.write(self.style.WARNING(f"  · {exc}"))
                continue
            except MercadoPagoError as exc:
                self.stdout.write(self.style.ERROR(f"  · Error MP: {exc}"))
                continue
            total_creados += resumen["creados"]
            total_existentes += resumen["existentes"]
            total_huerfanos += resumen["huerfanos"]

        self.stdout.write(self.style.MIGRATE_HEADING("\n=== Resumen global ==="))
        self.stdout.write(f"Creados: {total_creados}")
        self.stdout.write(f"Ya existentes: {total_existentes}")
        self.stdout.write(f"Huérfanos (sin cuenta local): {total_huerfanos}")
        if dry_run:
            self.stdout.write(self.style.WARNING("Ejecutado en modo --dry-run; no se creó nada."))

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------

    def _reconciliar_institucion(self, inst, desde, hasta, dry_run):
        creados = 0
        existentes = 0
        huerfanos = 0
        offset = 0

        while True:
            body = buscar_pagos_aprobados(inst, desde=desde, hasta=hasta,
                                          limit=PAGE_SIZE, offset=offset)
            results = body.get("results") or []
            paging = body.get("paging") or {}
            total = paging.get("total") or 0

            if not results:
                break

            for pago in results:
                payment_id = str(pago.get("id") or "")
                external_ref = str(pago.get("external_reference") or "")
                monto = pago.get("transaction_amount")

                if not payment_id or not external_ref or not external_ref.isdigit():
                    huerfanos += 1
                    self.stdout.write(
                        f"  ? Pago {payment_id or '?'}: external_reference inválida ('{external_ref}')."
                    )
                    continue

                # Verifica existencia local; SIEMPRE filtrando por institución.
                if PagoRegistrado.objects.filter(
                    referencia_transaccion=payment_id,
                    institucion=inst,
                ).exists():
                    existentes += 1
                    continue

                cuenta = (
                    CuentaPorCobrarEstudiante.objects
                    .select_related("estudiante", "concepto_pago")
                    .filter(pk=int(external_ref), institucion=inst)
                    .first()
                )
                if not cuenta:
                    huerfanos += 1
                    self.stdout.write(self.style.WARNING(
                        f"  ! Pago {payment_id} (ref={external_ref}): no hay cuenta local en esta institución."
                    ))
                    continue

                if dry_run:
                    creados += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"  [dry-run] Crearía PagoRegistrado para cuenta {cuenta.id} (pago {payment_id}, monto {monto})."
                    ))
                    continue

                estudiante = cuenta.estudiante
                if not estudiante:
                    huerfanos += 1
                    self.stdout.write(self.style.WARNING(
                        f"  ! Cuenta {cuenta.id} sin estudiante asociado; no se puede crear PagoRegistrado."
                    ))
                    continue

                PagoRegistrado.objects.create(
                    cuenta=cuenta,
                    estudiante=estudiante,
                    valor_pagado=Decimal(str(monto or "0")),
                    metodo_pago="MERCADO_PAGO",
                    referencia_transaccion=payment_id,
                    institucion=inst,
                    observacion=f"Reconciliado desde MP (payment_id={payment_id}).",
                )
                creados += 1
                self.stdout.write(self.style.SUCCESS(
                    f"  + PagoRegistrado creado para cuenta {cuenta.id} (pago {payment_id}, monto {monto})."
                ))

            offset += len(results)
            if offset >= total:
                break

        self.stdout.write(
            f"  Reconciliados: creados={creados}, existentes={existentes}, huerfanos={huerfanos}"
        )
        return {"creados": creados, "existentes": existentes, "huerfanos": huerfanos}
