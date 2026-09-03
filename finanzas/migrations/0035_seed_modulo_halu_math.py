from django.db import migrations


# 'halu_math' es un módulo genuinamente nuevo (piloto de práctica adaptativa
# de matemáticas por DBA) — mismo criterio que 0034_seed_modulo_steam: esta
# migración SOLO crea la fila de catálogo y NO se la asigna a ninguna
# institución. El propietario la activa institución por institución desde
# el admin cuando corresponda.
MODULO = (
    'halu_math', 'Halu Math',
    'Práctica adaptativa de matemáticas por DBA: dificultad ajustada al desempeño del estudiante, con ejercicios generados por IA y curados por el docente.',
    'bi-calculator-fill', '/matematicas/', 130,
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
        ('finanzas', '0034_seed_modulo_steam'),
    ]

    operations = [
        migrations.RunPython(sembrar, revertir),
    ]
