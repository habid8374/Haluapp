import json
from pathlib import Path

from django.db import migrations

DATA_FILE = Path(__file__).resolve().parent / 'data' / 'cpc_catalogo.json'
LOTE = 1000


def sembrar(apps, schema_editor):
    CategoriaCPC = apps.get_model('presupuesto', 'CategoriaCPC')
    filas = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    objetos = [CategoriaCPC(**fila) for fila in filas]
    for inicio in range(0, len(objetos), LOTE):
        CategoriaCPC.objects.bulk_create(objetos[inicio:inicio + LOTE], ignore_conflicts=True)


def revertir(apps, schema_editor):
    CategoriaCPC = apps.get_model('presupuesto', 'CategoriaCPC')
    CategoriaCPC.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('presupuesto', '0005_seed_fuentes_financiacion'),
    ]

    operations = [
        migrations.RunPython(sembrar, revertir),
    ]
