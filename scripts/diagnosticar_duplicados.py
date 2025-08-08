#!/usr/bin/env python
"""
Script de diagnóstico para identificar y limpiar duplicados en Cuentas por Cobrar
"""
import os
import sys
import django

# Agregar el proyecto al path
sys.path.insert(0, os.path.abspath('..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proyecto_colegio.settings')
django.setup()

from django.db import transaction
from django.db.models import Count
from finanzas.models import CuentaPorCobrarEstudiante
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def diagnosticar_duplicados():
    """Identifica duplicados en cuentas por cobrar"""
    print("=== DIAGNÓSTICO DE DUPLICADOS EN CUENTAS POR COBRAR ===")
    
    # Buscar duplicados por estudiante, concepto y año/mes
    duplicados = CuentaPorCobrarEstudiante.objects.values(
        'estudiante', 'concepto_pago', 'año', 'mes'
    ).annotate(
        count=Count('id')
    ).filter(count__gt=1)
    
    if duplicados:
        print(f"\n⚠️  Se encontraron {len(duplicados)} grupos de duplicados:")
        for dup in duplicados:
            print(f"   - Estudiante: {dup['estudiante']}, Concepto: {dup['concepto_pago']}, "
                  f"Año: {dup['año']}, Mes: {dup['mes']} - {dup['count']} registros")
            
            # Mostrar los IDs específicos
            cuentas = CuentaPorCobrarEstudiante.objects.filter(
                estudiante=dup['estudiante'],
                concepto_pago=dup['concepto_pago'],
                año=dup['año'],
                mes=dup['mes']
            )
            ids = [c.id for c in cuentas]
            print(f"     IDs: {ids}")
    else:
        print("\n✅ No se encontraron duplicados por estudiante/concepto/año/mes")
    
    # Verificar duplicados por ID (esto no debería pasar normalmente)
    ids_duplicados = CuentaPorCobrarEstudiante.objects.values_list('id', flat=True)
    if len(ids_duplicados) != len(set(ids_duplicados)):
        print("\n⚠️  ¡ALERTA! Se encontraron IDs duplicados (esto es muy grave)")
    else:
        print("\n✅ No hay duplicados de IDs")
    
    # Verificar cuentas sin estudiante asociado
    cuentas_sin_estudiante = CuentaPorCobrarEstudiante.objects.filter(estudiante__isnull=True)
    if cuentas_sin_estudiante.exists():
        print(f"\n⚠️  Se encontraron {cuentas_sin_estudiante.count()} cuentas sin estudiante asociado")
        for cuenta in cuentas_sin_estudiante:
            print(f"   - ID: {cuenta.id}, Concepto: {cuenta.concepto_pago}")
    else:
        print("\n✅ Todas las cuentas tienen estudiante asociado")
    
    # Resumen general
    total_cuentas = CuentaPorCobrarEstudiante.objects.count()
    print(f"\n📊 Resumen:")
    print(f"   Total de cuentas: {total_cuentas}")
    
    return duplicados

def limpiar_duplicados_simulado():
    """Simula la limpieza de duplicados (sin ejecutar cambios reales)"""
    print("\n=== SIMULACIÓN DE LIMPIEZA DE DUPLICADOS ===")
    
    duplicados = CuentaPorCobrarEstudiante.objects.values(
        'estudiante', 'concepto_pago', 'año', 'mes'
    ).annotate(
        count=Count('id')
    ).filter(count__gt=1)
    
    for dup in duplicados:
        cuentas = CuentaPorCobrarEstudiante.objects.filter(
            estudiante=dup['estudiante'],
            concepto_pago=dup['concepto_pago'],
            año=dup['año'],
            mes=dup['mes']
        ).order_by('id')
        
        # Mantener el primero, eliminar los demás
        cuenta_a_mantener = cuentas.first()
        cuentas_a_eliminar = cuentas.exclude(id=cuenta_a_mantener.id)
        
        print(f"\n🗑️  Se eliminarían {cuentas_a_eliminar.count()} duplicados:")
        for cuenta in cuentas_a_eliminar:
            print(f"   - ID: {cuenta.id}, Monto: {cuenta.monto_asignado}")

if __name__ == "__main__":
    try:
        diagnosticar_duplicados()
        limpiar_duplicados_simulado()
        print("\n✅ Diagnóstico completado")
    except Exception as e:
        print(f"\n❌ Error durante el diagnóstico: {e}")
