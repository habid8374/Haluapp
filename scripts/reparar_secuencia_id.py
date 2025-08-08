#!/usr/bin/env python
"""
Script para reparar la secuencia de autoincremento en SQLite
"""
import os
import sys
import django

# Agregar el proyecto al path
sys.path.insert(0, os.path.abspath('..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proyecto_colegio.settings')
django.setup()

from django.db import connection
from finanzas.models import CuentaPorCobrarEstudiante
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def diagnosticar_secuencia():
    """Diagnostica el problema con la secuencia de autoincremento"""
    print("=== DIAGNÓSTICO DE SECUENCIA DE AUTOINCREMENTO ===")
    
    # Obtener el último ID existente
    ultimo_id = CuentaPorCobrarEstudiante.objects.aggregate(
        max_id=models.Max('id')
    )['max_id'] or 0
    
    print(f"Último ID en la tabla: {ultimo_id}")
    
    # Verificar la secuencia de SQLite
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT seq FROM sqlite_sequence 
            WHERE name = 'finanzas_cuentaporcobrarestudiante'
        """)
        resultado = cursor.fetchone()
        
        if resultado:
            secuencia_actual = resultado[0]
            print(f"Secuencia actual en SQLite: {secuencia_actual}")
            
            if secuencia_actual < ultimo_id:
                print("⚠️  La secuencia está desactualizada")
                return secuencia_actual, ultimo_id
            else:
                print("✅ La secuencia está actualizada")
                return secuencia_actual, ultimo_id
        else:
            print("⚠️  No existe secuencia para esta tabla")
            return 0, ultimo_id

def reparar_secuencia():
    """Repara la secuencia de autoincremento"""
    print("\n=== REPARANDO SECUENCIA ===")
    
    # Obtener el último ID
    ultimo_id = CuentaPorCobrarEstudiante.objects.aggregate(
        max_id=models.Max('id')
    )['max_id'] or 0
    
    nuevo_valor = ultimo_id + 1
    
    with connection.cursor() as cursor:
        # Actualizar o crear la secuencia
        cursor.execute("""
            INSERT OR REPLACE INTO sqlite_sequence (name, seq) 
            VALUES ('finanzas_cuentaporcobrarestudiante', ?)
        """, [nuevo_valor])
        
        print(f"✅ Secuencia actualizada a: {nuevo_valor}")

def verificar_tabla():
    """Verifica la estructura de la tabla"""
    print("\n=== VERIFICANDO ESTRUCTURA DE TABLA ===")
    
    with connection.cursor() as cursor:
        cursor.execute("""
            PRAGMA table_info(finanzas_cuentaporcobrarestudiante)
        """)
        columnas = cursor.fetchall()
        
        print("Estructura de columnas:")
        for col in columnas:
            print(f"  - {col[1]}: {col[2]} (PK: {col[5]})")

def contar_registros():
    """Cuenta los registros actuales"""
    total = CuentaPorCobrarEstudiante.objects.count()
    print(f"\n📊 Total de registros: {total}")
    return total

if __name__ == "__main__":
    try:
        from django.db import models
        
        # Importar después de setup
        from finanzas.models import CuentaPorCobrarEstudiante
        
        # Verificar estructura
        verificar_tabla()
        
        # Contar registros
        total = contar_registros()
        
        # Diagnosticar secuencia
        sec_actual, ultimo_id = diagnosticar_secuencia()
        
        # Si hay problema, reparar
        if sec_actual < ultimo_id or sec_actual == 0:
            reparar_secuencia()
        else:
            print("✅ No se requiere reparación")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
