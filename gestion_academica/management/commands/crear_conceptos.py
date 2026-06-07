"""Sincroniza los ConceptoPago estándar (Inscripción / Matrícula / Pensiones)
para todos los NivelEscolaridad existentes.

Antes este comando creaba conceptos por institución (sin nivel) con valor 0
y sin los flags ``es_pago_*``. Ahora delega en
``finanzas.services.sincronizar_conceptos_de_nivel`` que es la MISMA función
que usa la signal post_save de ``NivelEscolaridad``.

Uso típico:

    python manage.py crear_conceptos
    python manage.py crear_conceptos --institucion 1
    python manage.py crear_conceptos --año 2026

El comando es idempotente: puede correrse cuantas veces se quiera.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from finanzas.models import InstitucionEducativa
from finanzas.services import sincronizar_conceptos_de_nivel
from gestion_academica.models import NivelEscolaridad


class Command(BaseCommand):
    help = (
        "Sincroniza los ConceptoPago estándar (Inscripción/Matrícula/Pensiones) "
        "para todos los NivelEscolaridad. Idempotente."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--institucion", type=int, default=None,
            help="ID de una institución específica (por defecto procesa todas).",
        )
        parser.add_argument(
            "--año", type=int, default=None,
            help="Año lectivo (por defecto el del PeriodoAcademico activo o el actual).",
        )

    def handle(self, *args, **options):
        instituciones = InstitucionEducativa.objects.all()
        if options.get("institucion"):
            instituciones = instituciones.filter(pk=options["institucion"])

        if not instituciones.exists():
            self.stdout.write(self.style.WARNING(
                "No hay instituciones para procesar."
            ))
            return

        año = options.get("año")
        total_creados = total_actualizados = total_sin_cambios = 0

        for inst in instituciones:
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"\n>> {inst} (id={inst.pk})"
            ))
            niveles = NivelEscolaridad.objects.filter(institucion=inst).order_by("orden", "nombre")
            if not niveles.exists():
                self.stdout.write(self.style.WARNING(
                    "   Sin Niveles de Escolaridad. Crea al menos uno desde "
                    "Gestion Academica -> Niveles."
                ))
                continue

            for nivel in niveles:
                try:
                    resultado = sincronizar_conceptos_de_nivel(nivel, año=año)
                    total_creados += resultado.creados
                    total_actualizados += resultado.actualizados
                    total_sin_cambios += resultado.sin_cambios
                    self.stdout.write(self.style.SUCCESS(
                        f"   [OK] {resultado.resumen()}"
                    ))
                except Exception as exc:  # noqa: BLE001
                    self.stdout.write(self.style.ERROR(
                        f"   [ERR] Nivel '{nivel}': {exc}"
                    ))

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(
            f"Resumen total: {total_creados} creados, "
            f"{total_actualizados} actualizados, "
            f"{total_sin_cambios} sin cambios."
        ))
