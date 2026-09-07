from django.db import migrations


# Catálogo BASE de ejemplo — no es una copia certificada del Catálogo
# General de Cuentas (CGC) vigente de la Contaduría General de la Nación.
# Trae solo las cuentas más comunes de un FSE (caja/bancos, cuentas por
# pagar, gastos de funcionamiento típicos e ingresos por transferencias)
# para que el módulo sea usable desde el día uno. El contador de cada
# institución debe revisarlo/completarlo contra la resolución CGN vigente
# antes de cerrar una vigencia fiscal real.
CUENTAS = [
    # (codigo, nombre, naturaleza, permite_movimientos, codigo_padre)
    ('1', 'ACTIVOS', 'DEBITO', False, None),
    ('11', 'Efectivo y equivalentes al efectivo', 'DEBITO', False, '1'),
    ('1105', 'Caja', 'DEBITO', True, '11'),
    ('1110', 'Bancos', 'DEBITO', True, '11'),
    ('13', 'Cuentas por cobrar', 'DEBITO', False, '1'),
    ('1385', 'Anticipos y avances entregados', 'DEBITO', True, '13'),

    ('2', 'PASIVOS', 'CREDITO', False, None),
    ('24', 'Cuentas por pagar', 'CREDITO', False, '2'),
    ('2401', 'Adquisición de bienes y servicios nacionales', 'CREDITO', True, '24'),
    ('2436', 'Retención en la fuente e impuesto de timbre', 'CREDITO', True, '24'),
    ('2440', 'Impuestos, contribuciones y tasas por pagar (ReteICA)', 'CREDITO', True, '24'),
    ('2445', 'Estampillas por pagar', 'CREDITO', True, '24'),

    ('3', 'PATRIMONIO', 'CREDITO', False, None),
    ('32', 'Patrimonio institucional', 'CREDITO', True, '3'),

    ('4', 'INGRESOS', 'CREDITO', False, None),
    ('44', 'Transferencias y subvenciones', 'CREDITO', False, '4'),
    ('4428', 'Sistema General de Participaciones (SGP)', 'CREDITO', True, '44'),
    ('45', 'Ingresos por venta de servicios (recursos propios)', 'CREDITO', True, '4'),

    ('5', 'GASTOS', 'DEBITO', False, None),
    ('51', 'Gastos de administración y operación', 'DEBITO', False, '5'),
    ('5111', 'Sueldos y salarios', 'DEBITO', True, '51'),
    ('5120', 'Materiales y suministros', 'DEBITO', True, '51'),
    ('5124', 'Mantenimiento de bienes muebles e inmuebles', 'DEBITO', True, '51'),
    ('5130', 'Servicios públicos', 'DEBITO', True, '51'),
    ('5134', 'Honorarios', 'DEBITO', True, '51'),
]


def sembrar(apps, schema_editor):
    CatalogoGeneralCuentas = apps.get_model('presupuesto', 'CatalogoGeneralCuentas')
    padres = {}
    # primera pasada: crear todas sin padre para poder resolver referencias en cualquier orden
    for codigo, nombre, naturaleza, permite_mov, _padre in CUENTAS:
        obj, _ = CatalogoGeneralCuentas.objects.get_or_create(
            codigo=codigo,
            defaults={'nombre': nombre, 'naturaleza': naturaleza, 'permite_movimientos': permite_mov},
        )
        padres[codigo] = obj
    # segunda pasada: asignar cuenta_padre
    for codigo, _n, _nat, _pm, padre_codigo in CUENTAS:
        if padre_codigo:
            obj = padres[codigo]
            obj.cuenta_padre = padres[padre_codigo]
            obj.save(update_fields=['cuenta_padre'])


def revertir(apps, schema_editor):
    CatalogoGeneralCuentas = apps.get_model('presupuesto', 'CatalogoGeneralCuentas')
    codigos = [c[0] for c in CUENTAS]
    CatalogoGeneralCuentas.objects.filter(codigo__in=codigos).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('presupuesto', '0002_catalogogeneralcuentas_and_more'),
    ]

    operations = [
        migrations.RunPython(sembrar, revertir),
    ]
