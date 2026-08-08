"""Crea una 'Sede Principal' para cada institución que aún no tenga sedes.

Aditivo e idempotente: no toca instituciones que ya tengan al menos una sede.
El código DANE de la sede se inicializa con el DANE de la institución (ajustable
luego desde el CRUD de Sedes).
"""
from django.db import migrations


def crear_sedes_principales(apps, schema_editor):
    InstitucionEducativa = apps.get_model('finanzas', 'InstitucionEducativa')
    Sede = apps.get_model('simat', 'Sede')
    con_sede = set(Sede.objects.values_list('institucion_id', flat=True))
    nuevas = []
    for inst in InstitucionEducativa.objects.all().only('id', 'codigo_dane'):
        if inst.id in con_sede:
            continue
        nuevas.append(Sede(
            institucion_id=inst.id,
            nombre='Sede Principal',
            codigo_dane_sede=(inst.codigo_dane or '')[:20],
            zona='URBANA',
            es_principal=True,
            activa=True,
        ))
    if nuevas:
        Sede.objects.bulk_create(nuevas)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('simat', '0003_seed_municipios'),
        ('finanzas', '0026_institucion_config_simat'),
    ]

    operations = [
        migrations.RunPython(crear_sedes_principales, noop),
    ]
