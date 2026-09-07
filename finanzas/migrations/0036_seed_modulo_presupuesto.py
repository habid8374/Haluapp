from django.db import migrations


# 'presupuesto' es un módulo nuevo (Fase 1 — Núcleo Presupuestal del FSE,
# ver Decreto 1075 de 2015) — mismo criterio que 0034/0035: esta migración
# SOLO crea la fila de catálogo y NO se la asigna a ninguna institución. El
# propietario la activa institución por institución (colegios oficiales)
# desde el admin cuando corresponda.
MODULO = (
    'presupuesto', 'Presupuesto FSE',
    'Ciclo presupuestal del Fondo de Servicios Educativos: apropiación, CDP, RP, obligación y orden de pago (Decreto 1075 de 2015).',
    'bi-bank2', '/presupuesto/', 140,
)


def sembrar(apps, schema_editor):
    ModuloPlataforma = apps.get_model('finanzas', 'ModuloPlataforma')
    codigo, nombre, desc, icono, prefijo, orden = MODULO
    ModuloPlataforma.objects.get_or_create(
        codigo=codigo,
        defaults={
            'nombre': nombre, 'descripcion': desc, 'icono': icono,
            'prefijo_url': prefijo, 'orden': orden, 'activo': True,
        },
    )


def revertir(apps, schema_editor):
    ModuloPlataforma = apps.get_model('finanzas', 'ModuloPlataforma')
    ModuloPlataforma.objects.filter(codigo=MODULO[0]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0035_seed_modulo_halu_math'),
    ]

    operations = [
        migrations.RunPython(sembrar, revertir),
    ]
