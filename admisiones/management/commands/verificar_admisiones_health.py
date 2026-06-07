"""Health-check operativo del módulo admisiones.

Este comando delega TODA la lógica de verificación al servicio reutilizable
``admisiones.services.health_check.ejecutar_health_check``.

La misma lógica la usa también la tarea Celery del dashboard de mantenimiento
del super-admin (ver ``finanzas.views.health_check_*``), lo que garantiza que
CLI y dashboard reporten exactamente lo mismo.

Uso:
    python manage.py verificar_admisiones_health
    python manage.py verificar_admisiones_health --institucion 1
    python manage.py verificar_admisiones_health --strict   (sale 1 si hay warnings)
"""
from __future__ import annotations

import sys

from django.core.management.base import BaseCommand

from admisiones.services.health_check import (
    NIVEL_ERR,
    NIVEL_INFO,
    NIVEL_OK,
    NIVEL_WARN,
    ejecutar_health_check,
)


class Command(BaseCommand):
    help = "Health-check operativo de HALU (Redis, Celery, Channels, plantillas, URLs, instituciones, conceptos, mora)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--institucion", type=int, default=None,
            help="ID de una institución específica (por defecto verifica todas).",
        )
        parser.add_argument(
            "--strict", action="store_true",
            help="Sale con código 1 si hay cualquier WARN (no solo ERROR).",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("\n=== HEALTH-CHECK HALU ==="))

        def imprimir(evento):
            mensaje = evento.mensaje
            if evento.nivel == NIVEL_INFO:
                # Encabezados de sección
                if evento.paso:
                    self.stdout.write(self.style.MIGRATE_HEADING(f"\n[{evento.paso}] {evento.titulo}"))
                else:
                    self.stdout.write(f"  {mensaje}")
                return
            prefijos = {
                NIVEL_OK: ("  [OK]   ", self.style.SUCCESS),
                NIVEL_WARN: ("  [WARN] ", self.style.WARNING),
                NIVEL_ERR: ("  [ERR]  ", self.style.ERROR),
            }
            prefijo, style = prefijos.get(evento.nivel, ("  [?]    ", lambda s: s))
            self.stdout.write(style(prefijo + mensaje))

        resultado = ejecutar_health_check(
            institucion_id=options.get("institucion"),
            progreso_callback=imprimir,
        )

        self.stdout.write("\n" + "=" * 50)
        if resultado.errores:
            self.stdout.write(self.style.ERROR(
                f"FAIL: {resultado.errores} errores, {resultado.warnings} warnings."
            ))
            sys.exit(1)
        if resultado.warnings and options.get("strict"):
            self.stdout.write(self.style.WARNING(
                f"STRICT FAIL: {resultado.warnings} warnings."
            ))
            sys.exit(1)
        self.stdout.write(self.style.SUCCESS(
            f"OK: 0 errores, {resultado.warnings} warnings."
        ))
