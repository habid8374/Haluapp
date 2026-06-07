"""Detecta aspirantes duplicados por (institución, numero_documento).

Esta plataforma es SaaS multi-institución: ``numero_documento`` debe ser único
*dentro* de cada institución, NUNCA globalmente. Este comando recorre cada
institución y reporta los conflictos antes de que aplicar la constraint en BD.

Uso típico:
    python manage.py detectar_duplicados_aspirantes
    python manage.py detectar_duplicados_aspirantes --institucion 3
    python manage.py detectar_duplicados_aspirantes --exit-on-error
    python manage.py detectar_duplicados_aspirantes --excel duplicados.xlsx
"""
from __future__ import annotations

from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from admisiones.models import Aspirante
from finanzas.models import InstitucionEducativa


class Command(BaseCommand):
    help = (
        "Detecta aspirantes con numero_documento duplicado dentro de la misma "
        "institución. Pensado para auditar antes de añadir la UniqueConstraint."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--institucion",
            type=int,
            default=None,
            help="ID de una institución específica (por defecto, analiza todas).",
        )
        parser.add_argument(
            "--exit-on-error",
            action="store_true",
            help="Termina con código 1 si encuentra duplicados (útil en CI/pre-deploy).",
        )
        parser.add_argument(
            "--excel",
            type=str,
            default=None,
            help="Ruta para exportar los duplicados a un archivo Excel.",
        )

    def handle(self, *args, **options):
        instituciones_qs = InstitucionEducativa.objects.all()
        if options["institucion"]:
            instituciones_qs = instituciones_qs.filter(pk=options["institucion"])
            if not instituciones_qs.exists():
                raise CommandError(
                    f"No existe la institución con ID {options['institucion']}."
                )

        total_duplicados = 0
        reporte_filas: list[dict] = []

        for inst in instituciones_qs:
            duplicados = (
                Aspirante.objects.filter(institucion=inst)
                .exclude(numero_documento__isnull=True)
                .exclude(numero_documento__exact="")
                .values("numero_documento")
                .annotate(total=Count("id"))
                .filter(total__gt=1)
                .order_by("-total", "numero_documento")
            )

            if not duplicados:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[{inst.id}] {inst.nombre}: sin duplicados."
                    )
                )
                continue

            self.stdout.write(
                self.style.WARNING(
                    f"[{inst.id}] {inst.nombre}: {duplicados.count()} documentos duplicados."
                )
            )
            for dup in duplicados:
                aspirantes = (
                    Aspirante.objects.filter(
                        institucion=inst,
                        numero_documento=dup["numero_documento"],
                    )
                    .order_by("fecha_inscripcion")
                    .values("id", "nombres", "apellidos", "estado", "fecha_inscripcion")
                )
                total_duplicados += dup["total"]
                ids = ", ".join(str(a["id"]) for a in aspirantes)
                self.stdout.write(
                    f"  · documento={dup['numero_documento']} "
                    f"({dup['total']} registros, IDs: {ids})"
                )
                for a in aspirantes:
                    reporte_filas.append(
                        {
                            "institucion_id": inst.id,
                            "institucion": inst.nombre,
                            "numero_documento": dup["numero_documento"],
                            "aspirante_id": a["id"],
                            "nombres": a["nombres"],
                            "apellidos": a["apellidos"],
                            "estado": a["estado"],
                            "fecha_inscripcion": (
                                a["fecha_inscripcion"].isoformat()
                                if a["fecha_inscripcion"] else ""
                            ),
                        }
                    )

        if options["excel"] and reporte_filas:
            try:
                import pandas as pd  # type: ignore
            except ImportError:
                raise CommandError("Falta pandas para exportar a Excel.")
            df = pd.DataFrame(reporte_filas)
            df.to_excel(options["excel"], index=False)
            self.stdout.write(
                self.style.SUCCESS(f"Reporte exportado a {options['excel']}.")
            )

        if total_duplicados == 0:
            self.stdout.write(
                self.style.SUCCESS(
                    "Auditoría OK: no se detectaron duplicados. Puedes aplicar la UniqueConstraint."
                )
            )
            return

        msg = (
            f"Se detectaron {total_duplicados} registros conflictivos. "
            "Resuelve los duplicados (fusionar, eliminar, renumerar) ANTES de aplicar la constraint."
        )
        if options["exit_on_error"]:
            raise CommandError(msg)
        self.stdout.write(self.style.ERROR(msg))
