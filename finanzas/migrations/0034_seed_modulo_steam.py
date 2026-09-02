from django.db import migrations


# A diferencia de 0031/0032 (que "envolvían" funcionalidad que YA era gratis
# para todos), 'steam' es un módulo genuinamente NUEVO: nadie lo ha tenido
# nunca. Por eso esta migración SOLO crea la fila de catálogo y
# deliberadamente NO se la asigna a ninguna institución — el propietario la
# activa institución por institución desde el admin cuando corresponda.
MODULO = (
    'steam', 'Halu STEAM',
    'Panel de coordinación para la modalidad técnica/STEAM: talleres, recursos interactivos y simulacros en un solo lugar.',
    'bi-stars', '/academico/steam/', 120,
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
        ('finanzas', '0033_institucioneducativa_idiomas_contratados'),
    ]

    operations = [
        migrations.RunPython(sembrar, revertir),
    ]
