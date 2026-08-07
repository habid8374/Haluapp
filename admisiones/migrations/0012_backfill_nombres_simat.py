"""Backfill: separa `nombres`/`apellidos` existentes en primer/segundo.

Heurística: primer token = primer nombre/apellido; el resto = segundo.
Es IMPERFECTA con nombres compuestos (ej. "Ana María" o "De la Cruz"), por lo
que queda para revisión manual posterior. Solo rellena si el campo destino está
vacío (idempotente). No sobrescribe datos ya capturados.
"""
from django.db import migrations


def _split_dos(texto):
    partes = (texto or '').split()
    if not partes:
        return '', ''
    return partes[0], ' '.join(partes[1:])


def backfill(apps, schema_editor):
    Aspirante = apps.get_model('admisiones', 'Aspirante')
    por_actualizar = []
    qs = Aspirante.objects.filter(primer_nombre='', primer_apellido='').only(
        'id', 'nombres', 'apellidos', 'primer_nombre', 'segundo_nombre',
        'primer_apellido', 'segundo_apellido',
    )
    for a in qs.iterator():
        pn, sn = _split_dos(a.nombres)
        pa, sa = _split_dos(a.apellidos)
        a.primer_nombre, a.segundo_nombre = pn[:60], sn[:60]
        a.primer_apellido, a.segundo_apellido = pa[:60], sa[:60]
        por_actualizar.append(a)
        if len(por_actualizar) >= 500:
            Aspirante.objects.bulk_update(
                por_actualizar,
                ['primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido'],
            )
            por_actualizar = []
    if por_actualizar:
        Aspirante.objects.bulk_update(
            por_actualizar,
            ['primer_nombre', 'segundo_nombre', 'primer_apellido', 'segundo_apellido'],
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('admisiones', '0011_aspirante_simat_campos'),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
