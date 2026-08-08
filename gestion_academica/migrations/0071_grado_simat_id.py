import unicodedata

from django.db import migrations, models


def _norm(s):
    s = (s or '').lower().strip()
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def prefill_simat_grado(apps, schema_editor):
    """Sugiere el ID SIMAT del grado a partir del nombre/orden (editable después)."""
    Grado = apps.get_model('gestion_academica', 'Grado')
    por_nombre = [
        (('primera infancia', 'parvulo', 'materno', 'caminador', 'sala cuna'), '-3'),
        (('pre-jardin', 'prejardin', 'pre jardin', 'parvulos'), '-2'),
        (('jardin', 'kinder', 'kínder'), '-1'),
        (('transicion', 'grado 0', 'grado cero', 'preescolar'), '0'),
        (('primero', 'primer '), '1'),
        (('segundo',), '2'), (('tercero',), '3'), (('cuarto',), '4'),
        (('quinto',), '5'), (('sexto',), '6'), (('septimo',), '7'),
        (('octavo',), '8'), (('noveno',), '9'),
        (('decimo',), '10'), (('undecimo', 'once'), '11'),
        (('duodecimo', 'doce'), '12'), (('trece', 'decimo tercero'), '13'),
    ]
    for g in Grado.objects.all().only('pk', 'nombre', 'orden', 'simat_grado_id'):
        if g.simat_grado_id:
            continue
        n = _norm(g.nombre)
        cod = ''
        # CLEI / ciclos de adultos
        for i in range(1, 6):
            if f'clei {i}' in n or f'ciclo {i}' in n:
                cod = str(20 + i)
                break
        if not cod:
            for claves, valor in por_nombre:
                if any(k in n for k in claves):
                    cod = valor
                    break
        if not cod and g.orden and 1 <= g.orden <= 11:
            cod = str(g.orden)
        if cod:
            g.simat_grado_id = cod
            g.save(update_fields=['simat_grado_id'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0070_perfilaccesibilidad'),
    ]

    operations = [
        migrations.AddField(
            model_name='grado',
            name='simat_grado_id',
            field=models.CharField(
                blank=True, max_length=3,
                choices=[
                    ('-3', 'Primera Infancia (-3)'), ('-2', 'Pre-Jardín (-2)'),
                    ('-1', 'Jardín / Kínder (-1)'), ('0', 'Transición / Grado 0'),
                    ('1', 'Primero'), ('2', 'Segundo'), ('3', 'Tercero'), ('4', 'Cuarto'),
                    ('5', 'Quinto'), ('6', 'Sexto'), ('7', 'Séptimo'), ('8', 'Octavo'),
                    ('9', 'Noveno'), ('10', 'Décimo'), ('11', 'Once'),
                    ('12', 'Doce (Normal Superior)'), ('13', 'Trece (Normal Superior)'),
                    ('21', 'CLEI 1 (adultos)'), ('22', 'CLEI 2 (adultos)'),
                    ('23', 'CLEI 3 (adultos)'), ('24', 'CLEI 4 (adultos)'),
                    ('25', 'CLEI 5 (adultos)'),
                ],
                help_text='Código oficial del grado en el SIMAT, para el reporte de matrícula.',
                verbose_name='ID de grado SIMAT (MEN)',
            ),
        ),
        migrations.RunPython(prefill_simat_grado, noop),
    ]
