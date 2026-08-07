"""Siembra los catálogos oficiales del SIMAT desde simat/data/*.json.

Fuente: plantilla oficial Anexo 6A del MEN (hojas ETNIAS, RESGUARDOS,
CAJAS DE COMPENSACION, EPS) + departamentos DIVIPOLA (DANE).
Los municipios DIVIPOLA se cargan aparte (listado oficial pendiente).
"""
import json
import os

from django.db import migrations

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')


def _load(nombre):
    with open(os.path.join(DATA_DIR, nombre), encoding='utf-8') as f:
        return json.load(f)


def sembrar(apps, schema_editor):
    Departamento = apps.get_model('simat', 'Departamento')
    Etnia = apps.get_model('simat', 'Etnia')
    Resguardo = apps.get_model('simat', 'Resguardo')
    EPS = apps.get_model('simat', 'EPS')
    CajaCompensacion = apps.get_model('simat', 'CajaCompensacion')

    Departamento.objects.bulk_create(
        [Departamento(codigo=d['codigo'], nombre=d['nombre']) for d in _load('departamentos.json')],
        ignore_conflicts=True,
    )
    for modelo, archivo in [
        (Etnia, 'etnias.json'),
        (Resguardo, 'resguardos.json'),
        (EPS, 'eps.json'),
        (CajaCompensacion, 'cajas_compensacion.json'),
    ]:
        modelo.objects.bulk_create(
            [modelo(codigo=r['codigo'], nombre=r['nombre'], habilitado=r.get('habilitado', True))
             for r in _load(archivo)],
            ignore_conflicts=True,
        )


def limpiar(apps, schema_editor):
    for m in ['Departamento', 'Etnia', 'Resguardo', 'EPS', 'CajaCompensacion']:
        apps.get_model('simat', m).objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('simat', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(sembrar, limpiar),
    ]
