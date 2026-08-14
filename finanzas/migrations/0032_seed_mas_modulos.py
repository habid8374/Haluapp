from django.db import migrations


# Más módulos reales de la plataforma (codigo, nombre, descripcion, icono,
# prefijo_url, orden). El campo prefijo_url admite VARIAS rutas separadas por
# espacio (ej. los juegos interactivos).
MODULOS = [
    ('recursos_educativos', 'Recursos educativos', 'Biblioteca de recursos y material de apoyo.', 'bi-collection-play', '/academico/recursos/', 40),
    ('evaluacion_docente', 'Evaluación docente', 'Evaluación de desempeño de los docentes.', 'bi-clipboard-data', '/evaluacion-docente/', 50),
    ('autoevaluacion', 'Autoevaluación institucional', 'Autoevaluación institucional anual (guía 34).', 'bi-graph-up', '/autoevaluacion/', 60),
    ('recursos_interactivos', 'Recursos interactivos (juegos)', 'Crucigramas, sopas de letras, memoria, flashcards, quiz de audio, secuencias, trazado y rompecabezas.', 'bi-controller',
        '/crucigramas/ /sopa-letras/ /memoria/ /flashcards/ /quiz-audio/ /secuencias/ /trazado/ /rompecabezas/', 70),
    ('cuestionarios', 'Cuestionarios / Evaluaciones', 'Editor de cuestionarios y evaluaciones en línea.', 'bi-ui-checks', '/cuestionarios/', 80),
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

    # Compatibilidad: las instituciones YA existentes conservan acceso a estos
    # módulos (no se le quita nada a nadie). El propietario desmarca lo que un
    # colegio no haya comprado.
    for inst in InstitucionEducativa.objects.all():
        inst.modulos_contratados.add(*creados)


def revertir(apps, schema_editor):
    ModuloPlataforma = apps.get_model('finanzas', 'ModuloPlataforma')
    ModuloPlataforma.objects.filter(codigo__in=[m[0] for m in MODULOS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0031_seed_modulos_plataforma'),
    ]

    operations = [
        migrations.RunPython(sembrar, revertir),
    ]
