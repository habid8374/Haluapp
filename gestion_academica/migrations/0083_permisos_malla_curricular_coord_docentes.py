from django.db import migrations


# Bug de acceso pre-existente detectado al probar Halu STEAM Fase 3
# end-to-end: 'mallacurricular'/'itemmalla' NUNCA se le habían dado a los
# grupos 'coordinadores'/'docentes' (solo migración 0057, que se los da al
# grupo 'rectores'). Según CLAUDE.md, la Malla Curricular es un módulo del
# coordinador ("consultada por los docentes como referencia") — así que un
# coordinador real, sin estar también en 'rectores', quedaba bloqueado para
# gestionar mallas y para ver el nuevo reporte de cumplimiento STEM+.
# Mismo patrón que 0079_enfasis_permisos_coordinadores.py: se asigna al
# Group, nunca por usuario individual.
COORDINADORES_PERMISSIONS = [
    ('gestion_academica', 'mallacurricular', 'view_mallacurricular'),
    ('gestion_academica', 'mallacurricular', 'add_mallacurricular'),
    ('gestion_academica', 'mallacurricular', 'change_mallacurricular'),
    ('gestion_academica', 'mallacurricular', 'delete_mallacurricular'),
    ('gestion_academica', 'itemmalla', 'view_itemmalla'),
    ('gestion_academica', 'itemmalla', 'add_itemmalla'),
    ('gestion_academica', 'itemmalla', 'change_itemmalla'),
    ('gestion_academica', 'itemmalla', 'delete_itemmalla'),
]

# Los docentes solo consultan la malla como referencia para sus planes
# semanales — nunca la editan.
DOCENTES_PERMISSIONS = [
    ('gestion_academica', 'mallacurricular', 'view_mallacurricular'),
    ('gestion_academica', 'itemmalla', 'view_itemmalla'),
]


def _get_permission(Permission, app_label, model, codename):
    try:
        return Permission.objects.get(
            content_type__app_label=app_label,
            content_type__model=model,
            codename=codename,
        )
    except Permission.DoesNotExist:
        return None


def _perms_for(Permission, spec):
    perms = [_get_permission(Permission, app_label, model, codename) for app_label, model, codename in spec]
    return [p for p in perms if p]


def agregar_permisos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    coordinadores, _ = Group.objects.get_or_create(name='coordinadores')
    perms = _perms_for(Permission, COORDINADORES_PERMISSIONS)
    if perms:
        coordinadores.permissions.add(*perms)

    docentes, _ = Group.objects.get_or_create(name='docentes')
    perms = _perms_for(Permission, DOCENTES_PERMISSIONS)
    if perms:
        docentes.permissions.add(*perms)


def quitar_permisos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    try:
        coordinadores = Group.objects.get(name='coordinadores')
        perms = _perms_for(Permission, COORDINADORES_PERMISSIONS)
        if perms:
            coordinadores.permissions.remove(*perms)
    except Group.DoesNotExist:
        pass

    try:
        docentes = Group.objects.get(name='docentes')
        perms = _perms_for(Permission, DOCENTES_PERMISSIONS)
        if perms:
            docentes.permissions.remove(*perms)
    except Group.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0082_itemmalla_principios_stem'),
    ]

    operations = [
        migrations.RunPython(agregar_permisos, quitar_permisos),
    ]
