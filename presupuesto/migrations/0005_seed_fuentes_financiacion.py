import json
from pathlib import Path

from django.db import migrations

DATA_FILE = Path(__file__).resolve().parent / 'data' / 'fuentes_financiacion.json'


def sembrar(apps, schema_editor):
    FuenteFinanciacion = apps.get_model('presupuesto', 'FuenteFinanciacion')
    filas = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    FuenteFinanciacion.objects.bulk_create(
        [FuenteFinanciacion(**fila) for fila in filas],
        ignore_conflicts=True,
    )


def revertir(apps, schema_editor):
    FuenteFinanciacion = apps.get_model('presupuesto', 'FuenteFinanciacion')
    filas = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    codigos = [fila['codigo_fuente'] for fila in filas]
    FuenteFinanciacion.objects.filter(codigo_fuente__in=codigos).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('presupuesto', '0004_categoriacpc_fuentefinanciacion_rp_categoria_cpc_and_more'),
    ]

    operations = [
        migrations.RunPython(sembrar, revertir),
    ]
