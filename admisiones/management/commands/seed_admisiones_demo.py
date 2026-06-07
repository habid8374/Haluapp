"""Crea datos sandbox para QA del módulo admisiones (Fase 3.5).

Este comando es idempotente: si ya existen los registros demo no los duplica.
Pensado para ambientes de desarrollo y staging — NO ejecutar en producción.

Genera (dentro de UNA institución, indicada con ``--institucion``):
- 3 ``DocumentoRequerido`` (tarjeta identidad, foto, último boletín).
- 4 ``HorarioDisponible`` (próximos 7 días, mañana y tarde).
- 5 ``Aspirante`` en distintos estados (INSCRITO, EN_PROCESO, ADMITIDO,
  APROBADO_MATRICULA, MATRICULADO).

Uso típico:
    python manage.py seed_admisiones_demo --institucion 1
    python manage.py seed_admisiones_demo --institucion 1 --grado "Sexto"
    python manage.py seed_admisiones_demo --institucion 1 --reset

Aislamiento SaaS:
- Todos los registros se crean asociados a la institución indicada; nunca
  cruzan tenants. Sin ``--institucion`` aborta.
"""
from __future__ import annotations

import datetime as dt

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from admisiones.models import (
    Aspirante,
    CitaAgendada,
    DocumentoRequerido,
    HorarioDisponible,
)
from finanzas.models import InstitucionEducativa
from gestion_academica.models import Grado


DOCUMENTOS_DEMO = [
    {
        "nombre": "Tarjeta de Identidad",
        "descripcion": "Foto/escaneo legible de ambos lados.",
        "es_obligatorio": True,
    },
    {
        "nombre": "Foto tipo carné",
        "descripcion": "Foto reciente, fondo blanco, formato JPG/PNG.",
        "es_obligatorio": True,
    },
    {
        "nombre": "Último boletín académico",
        "descripcion": "PDF del último boletín emitido por el colegio anterior.",
        "es_obligatorio": False,
    },
]


ASPIRANTES_DEMO = [
    {
        "nombres": "DEMO Ana",
        "apellidos": "Rodríguez",
        "numero_documento": "DEMO-1001",
        "email_contacto": "demo.ana@example.test",
        "estado": Aspirante.EstadoAdmision.INSCRITO,
        "sexo": "F",
    },
    {
        "nombres": "DEMO Juan",
        "apellidos": "Gómez",
        "numero_documento": "DEMO-1002",
        "email_contacto": "demo.juan@example.test",
        "estado": Aspirante.EstadoAdmision.EN_PROCESO,
        "sexo": "M",
    },
    {
        "nombres": "DEMO Sofía",
        "apellidos": "Martínez",
        "numero_documento": "DEMO-1003",
        "email_contacto": "demo.sofia@example.test",
        "estado": Aspirante.EstadoAdmision.ADMITIDO,
        "sexo": "F",
    },
    {
        "nombres": "DEMO Carlos",
        "apellidos": "Pérez",
        "numero_documento": "DEMO-1004",
        "email_contacto": "demo.carlos@example.test",
        "estado": Aspirante.EstadoAdmision.APROBADO_MATRICULA,
        "sexo": "M",
    },
    {
        "nombres": "DEMO Valentina",
        "apellidos": "Lopez",
        "numero_documento": "DEMO-1005",
        "email_contacto": "demo.valentina@example.test",
        "estado": Aspirante.EstadoAdmision.INSCRITO,
        "sexo": "F",
    },
]


class Command(BaseCommand):
    help = "Crea datos sandbox para QA del módulo admisiones."

    def add_arguments(self, parser):
        parser.add_argument(
            "--institucion", type=int, required=True,
            help="ID de la InstitucionEducativa donde sembrar los datos.",
        )
        parser.add_argument(
            "--grado", type=str, default=None,
            help="Nombre del grado a usar (debe existir en la institución). "
                 "Si no se pasa, usa el primer grado disponible.",
        )
        parser.add_argument(
            "--reset", action="store_true",
            help="Elimina los registros DEMO previos antes de crear.",
        )

    def handle(self, *args, **options):
        try:
            institucion = InstitucionEducativa.objects.get(pk=options["institucion"])
        except InstitucionEducativa.DoesNotExist:
            raise CommandError(
                f"No existe la institución con ID {options['institucion']}."
            )

        grado = self._resolver_grado(institucion, options.get("grado"))

        if options["reset"]:
            self._reset(institucion)

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"Sembrando datos demo en '{institucion}' (grado='{grado.nombre}')..."
        ))

        self._crear_documentos(institucion, grado)
        self._crear_horarios(institucion)
        creados, ya_existian = self._crear_aspirantes(institucion, grado)

        self.stdout.write(self.style.SUCCESS(
            f"\nResumen: {creados} aspirantes nuevos, {ya_existian} ya existían."
        ))
        self.stdout.write(
            self.style.WARNING(
                "Recuerda: estos registros son SOLO para QA. "
                "Limpia con `--reset` antes de pasar a producción."
            )
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolver_grado(self, institucion, nombre):
        qs = Grado.objects.filter(institucion=institucion)
        if nombre:
            grado = qs.filter(nombre__iexact=nombre).first()
            if not grado:
                raise CommandError(
                    f"No existe el grado '{nombre}' en la institución '{institucion}'. "
                    f"Crea uno antes (admin → Gestión Académica → Grados)."
                )
            return grado
        grado = qs.first()
        if not grado:
            raise CommandError(
                f"La institución '{institucion}' no tiene ningún grado creado. "
                "Crea al menos uno en gestion_academica antes de sembrar."
            )
        return grado

    def _reset(self, institucion):
        # Solo borra REGISTROS demo (los que crea este comando), nunca tocan datos
        # reales. Identificamos por prefijo "DEMO " en nombres y "DEMO-" en
        # documento.
        n_aspirantes = Aspirante.objects.filter(
            institucion=institucion,
            numero_documento__startswith="DEMO-",
        ).count()
        Aspirante.objects.filter(
            institucion=institucion,
            numero_documento__startswith="DEMO-",
        ).delete()
        n_horarios = HorarioDisponible.objects.filter(
            institucion=institucion,
            entrevistador__isnull=True,
            fecha_hora_inicio__gte=timezone.now() - dt.timedelta(days=1),
        ).count()
        # No borramos documentos requeridos ni horarios reales por seguridad.
        self.stdout.write(self.style.WARNING(
            f"  Reset: {n_aspirantes} aspirantes DEMO eliminados "
            f"(horarios y documentos demo NO se borran para preservar referencias)."
        ))

    def _crear_documentos(self, institucion, grado):
        for spec in DOCUMENTOS_DEMO:
            doc, created = DocumentoRequerido.objects.get_or_create(
                institucion=institucion,
                nombre=spec["nombre"],
                defaults={
                    "descripcion": spec["descripcion"],
                    "es_obligatorio": spec["es_obligatorio"],
                },
            )
            if created:
                doc.grados_aplicables.add(grado)
                self.stdout.write(self.style.SUCCESS(
                    f"  + DocumentoRequerido '{doc.nombre}' creado."
                ))
            else:
                # Aseguramos que el grado esté entre los aplicables.
                if not doc.grados_aplicables.filter(pk=grado.pk).exists():
                    doc.grados_aplicables.add(grado)
                self.stdout.write(
                    f"  · DocumentoRequerido '{doc.nombre}' ya existía."
                )

    def _crear_horarios(self, institucion):
        ahora = timezone.now()
        # Próximos 4 días hábiles, 9:00 y 14:00.
        slots = []
        dia = ahora + dt.timedelta(days=1)
        while len(slots) < 4:
            if dia.weekday() < 5:  # Lunes a viernes
                slots.append(dia.replace(hour=9, minute=0, second=0, microsecond=0))
                if len(slots) < 4:
                    slots.append(dia.replace(hour=14, minute=0, second=0, microsecond=0))
            dia += dt.timedelta(days=1)

        for fecha in slots:
            horario, created = HorarioDisponible.objects.get_or_create(
                institucion=institucion,
                fecha_hora_inicio=fecha,
                tipo_cita="entrevista",
                defaults={
                    "duracion_minutos": 30,
                    "cupos_disponibles": 1,
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(
                    f"  + HorarioDisponible {fecha:%Y-%m-%d %H:%M} creado."
                ))
            else:
                self.stdout.write(
                    f"  · HorarioDisponible {fecha:%Y-%m-%d %H:%M} ya existía."
                )

    def _crear_aspirantes(self, institucion, grado):
        creados = 0
        ya_existian = 0
        fecha_nac = dt.date.today() - dt.timedelta(days=365 * 12)  # ~12 años

        for spec in ASPIRANTES_DEMO:
            existente = Aspirante.objects.filter(
                institucion=institucion,
                numero_documento=spec["numero_documento"],
            ).first()
            if existente:
                ya_existian += 1
                self.stdout.write(
                    f"  · Aspirante {spec['numero_documento']} ya existía (estado={existente.estado})."
                )
                continue

            aspirante = Aspirante(
                institucion=institucion,
                nombres=spec["nombres"],
                apellidos=spec["apellidos"],
                numero_documento=spec["numero_documento"],
                email_contacto=spec["email_contacto"],
                grado_aspira=grado,
                fecha_nacimiento=fecha_nac,
                sexo=spec["sexo"],
                estado=Aspirante.EstadoAdmision.INSCRITO,
                requiere_pago_inscripcion=True,
            )
            # Evita disparar correos durante el seed.
            aspirante._omitir_correo_bienvenida = True
            aspirante.save()
            aspirante.procesar_inscripcion_completa()

            # Posiciona el aspirante en el estado destino sin enviar correos.
            destino = spec["estado"]
            if destino != Aspirante.EstadoAdmision.INSCRITO:
                aspirante._omitir_correo_estado = True
                aspirante.estado = destino
                aspirante.save(update_fields=["estado"])

            creados += 1
            self.stdout.write(self.style.SUCCESS(
                f"  + Aspirante {aspirante.numero_documento} ({aspirante.nombres} {aspirante.apellidos}) "
                f"creado en estado {aspirante.estado}."
            ))

        return creados, ya_existian
