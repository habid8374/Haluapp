import json
from pathlib import Path

from django.db import migrations, models

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
        # 84 de los ~9.933 títulos reales del DANE superan 255 caracteres
        # (hasta 690) — se ensancha el campo ANTES de sembrar para no
        # truncar datos oficiales. Va en la misma migración (y misma
        # transacción atómica) que la siembra, así el esquema ya está
        # ancho cuando bulk_create corre.
        migrations.AlterField(
            model_name='categoriacpc',
            name='titulo',
            field=models.TextField(verbose_name='Título'),
        ),
        migrations.RunPython(sembrar, revertir),
    ]
