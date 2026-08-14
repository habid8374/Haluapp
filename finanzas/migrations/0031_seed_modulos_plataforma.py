from django.db import migrations


# Catálogo inicial de módulos (codigo, nombre, descripcion, icono, prefijo_url, orden).
# Debe coincidir con finanzas.modulos.MODULOS_SEED.
MODULOS = [
    ('admisiones', 'Admisiones', 'Portal de aspirantes, importación y matrícula.', 'bi-clipboard-check', '/admisiones/', 10),
    ('simulacros', 'Simulacros (ICFES/Saber)', 'Banco de preguntas y simulacros tipo Saber.', 'bi-journal-check', '/simulacros/', 20),
    ('piar', 'PIAR (inclusión)', 'Planes Individuales de Ajuste Razonable (Decreto 1421).', 'bi-universal-access', '/piar/', 30),
]


def sembrar(apps, schema_editor):
    ModuloPlataforma = apps.get_model('finanzas', 'ModuloPlataforma')
    InstitucionEducativa = apps.get_model('finanzas', 'InstitucionEducativa')

    creados = []
    for codigo, nombre, desc, icono, prefijo, orden in MODULOS:
        obj, _ = ModuloPlataforma.objects.get_or_create(
            codigo=codigo,
            defaults={
                'nombre': nombre, 'descripcion': desc, 'icono': icono,
                'prefijo_url': prefijo, 'orden': orden, 'activo': True,
            },
        )
        creados.append(obj)

    # IMPORTANTE (compatibilidad): las instituciones YA existentes conservan
    # acceso a TODOS los módulos, para no quitarle nada a nadie al desplegar.
    # A partir de aquí, el propietario desmarca desde el admin lo que un colegio
    # no haya comprado.
    for inst in InstitucionEducativa.objects.all():
        inst.modulos_contratados.add(*creados)


def revertir(apps, schema_editor):
    ModuloPlataforma = apps.get_model('finanzas', 'ModuloPlataforma')
    ModuloPlataforma.objects.filter(
        codigo__in=[m[0] for m in MODULOS]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0030_moduloplataforma_and_more'),
    ]

    operations = [
        migrations.RunPython(sembrar, revertir),
    ]
