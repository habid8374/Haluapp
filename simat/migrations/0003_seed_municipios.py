"""Siembra los municipios DIVIPOLA (DANE) y los enlaza a su departamento.

Fuente: listado oficial DIVIPOLA del DANE (simat/data/municipios.json),
municipios únicos de 5 dígitos (1.122 registros).
"""
import json
import os

from django.db import migrations

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')


def sembrar(apps, schema_editor):
    Departamento = apps.get_model('simat', 'Departamento')
    Municipio = apps.get_model('simat', 'Municipio')
    dep_por_codigo = {d.codigo: d for d in Departamento.objects.all()}
    with open(os.path.join(DATA_DIR, 'municipios.json'), encoding='utf-8') as f:
        filas = json.load(f)
    objetos = []
    for m in filas:
        dep = dep_por_codigo.get(m['depto'])
        if dep is None:
            continue
        objetos.append(Municipio(codigo=m['codigo'], nombre=m['nombre'], departamento=dep))
    Municipio.objects.bulk_create(objetos, ignore_conflicts=True)


def limpiar(apps, schema_editor):
    apps.get_model('simat', 'Municipio').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('simat', '0002_seed_catalogos'),
    ]

    operations = [
        migrations.RunPython(sembrar, limpiar),
    ]
