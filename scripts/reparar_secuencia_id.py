#!/usr/bin/env python
"""
Repara la secuencia del PK de finanzas_cuentaporcobrarestudiante.

- SQLite: tabla sqlite_sequence y PRAGMA table_info.
- PostgreSQL: pg_sequences / setval sobre la secuencia del campo id.
"""
import os
import sys
import django

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "proyecto_colegio.settings")
django.setup()

import logging
from django.db import connection
from django.db.models import Max

from finanzas.models import CuentaPorCobrarEstudiante

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TABLE = "finanzas_cuentaporcobrarestudiante"


def diagnosticar_secuencia():
    """Compara el último id de la tabla con el valor de la secuencia (o sqlite_sequence)."""
    print("=== DIAGNÓSTICO DE SECUENCIA DE AUTOINCREMENTO ===")

    ultimo_id = CuentaPorCobrarEstudiante.objects.aggregate(max_id=Max("id"))["max_id"] or 0
    print(f"Último ID en la tabla: {ultimo_id}")

    sec_actual = 0
    vendor = connection.vendor

    if vendor == "sqlite":
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT seq FROM sqlite_sequence
                WHERE name = %s
                """,
                [TABLE],
            )
            resultado = cursor.fetchone()
            if resultado:
                sec_actual = resultado[0]
                print(f"Secuencia actual en SQLite: {sec_actual}")
            else:
                print("⚠️  No existe fila en sqlite_sequence para esta tabla")
                sec_actual = 0

    elif vendor == "postgresql":
        seq_name = f"{TABLE}_id_seq"
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COALESCE(s.last_value, 0)
                FROM pg_sequences s
                WHERE s.schemaname = 'public' AND s.sequencename = %s
                """,
                [seq_name],
            )
            row = cursor.fetchone()
            if row:
                sec_actual = int(row[0])
                print(f"Último valor en secuencia PostgreSQL ({seq_name}): {sec_actual}")
            else:
                print(f"⚠️  No se encontró la secuencia {seq_name} en pg_sequences")
                sec_actual = 0
    else:
        print(f"Motor no soportado por este script: {vendor}")
        return 0, ultimo_id

    if sec_actual < ultimo_id:
        print("⚠️  La secuencia está desactualizada respecto al MAX(id)")
    else:
        print("✅ La secuencia parece coherente con los datos")

    return sec_actual, ultimo_id


def reparar_secuencia():
    """Alinea la secuencia para que el próximo INSERT no choque con PK existente."""
    print("\n=== REPARANDO SECUENCIA ===")

    ultimo_id = CuentaPorCobrarEstudiante.objects.aggregate(max_id=Max("id"))["max_id"] or 0
    vendor = connection.vendor

    if vendor == "sqlite":
        nuevo_valor = ultimo_id + 1
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT OR REPLACE INTO sqlite_sequence (name, seq)
                VALUES (%s, %s)
                """,
                [TABLE, nuevo_valor],
            )
        print(f"✅ sqlite_sequence actualizada a: {nuevo_valor}")

    elif vendor == "postgresql":
        with connection.cursor() as cursor:
            if ultimo_id > 0:
                cursor.execute(
                    "SELECT setval(pg_get_serial_sequence(%s, 'id'), %s, true)",
                    [TABLE, ultimo_id],
                )
                print(f"✅ setval alineado con MAX(id)={ultimo_id} (próximo id será {ultimo_id + 1})")
            else:
                cursor.execute(
                    "SELECT setval(pg_get_serial_sequence(%s, 'id'), 1, false)",
                    [TABLE],
                )
                print("✅ Tabla vacía: secuencia reiniciada para empezar en id=1")

    else:
        raise RuntimeError(f"Motor no soportado: {vendor}")


def verificar_tabla():
    """Muestra columnas según el motor."""
    print("\n=== ESTRUCTURA DE LA TABLA ===")
    vendor = connection.vendor

    with connection.cursor() as cursor:
        if vendor == "sqlite":
            # PRAGMA no admite binding del nombre de tabla en todas las versiones de SQLite.
            cursor.execute(f"PRAGMA table_info({TABLE})")
            columnas = cursor.fetchall()
            for col in columnas:
                print(f"  - {col[1]}: {col[2]} (PK: {col[5]})")

        elif vendor == "postgresql":
            cursor.execute(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position
                """,
                [TABLE],
            )
            for name, dtype, nullable in cursor.fetchall():
                print(f"  - {name}: {dtype} (nullable: {nullable})")
        else:
            print(f"  (omitido: motor {vendor})")


def contar_registros():
    total = CuentaPorCobrarEstudiante.objects.count()
    print(f"\n📊 Total de registros: {total}")
    return total


if __name__ == "__main__":
    try:
        verificar_tabla()
        contar_registros()
        sec_actual, ultimo_id = diagnosticar_secuencia()

        if connection.vendor == "sqlite":
            if sec_actual < ultimo_id or sec_actual == 0:
                reparar_secuencia()
            else:
                print("✅ No se requiere reparación")
        elif connection.vendor == "postgresql":
            # Reparar si la secuencia va atrasada o no hay fila en pg_sequences (sec_actual queda 0 con datos).
            if sec_actual < ultimo_id or (ultimo_id > 0 and sec_actual == 0):
                reparar_secuencia()
            else:
                print("✅ No se requiere reparación (secuencia >= MAX(id))")
        else:
            print(f"No se ejecuta reparación automática para {connection.vendor}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
