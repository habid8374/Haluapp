from django.db import migrations


# Permisos del catálogo de Énfasis / Talleres (modalidad técnica) para el
# grupo 'coordinadores'. Mismo patrón que la migración 0039
# (setup_permission_groups): asigna al Group, nunca por usuario individual.
ENFASIS_PERMISSIONS = [
    ('gestion_academica', 'enfasis', 'view_enfasis'),
    ('gestion_academica', 'enfasis', 'add_enfasis'),
    ('gestion_academica', 'enfasis', 'change_enfasis'),
    ('gestion_academica', 'enfasis', 'delete_enfasis'),
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


def agregar_permisos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    group, _ = Group.objects.get_or_create(name='coordinadores')
    perms = [
        _get_permission(Permission, app_label, model, codename)
        for app_label, model, codename in ENFASIS_PERMISSIONS
    ]
    perms = [p for p in perms if p]
    if perms:
        group.permissions.add(*perms)


def quitar_permisos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    try:
        group = Group.objects.get(name='coordinadores')
    except Group.DoesNotExist:
        return
    perms = [
        _get_permission(Permission, app_label, model, codename)
        for app_label, model, codename in ENFASIS_PERMISSIONS
    ]
    perms = [p for p in perms if p]
    if perms:
        group.permissions.remove(*perms)


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0078_enfasis_taller_tecnico'),
    ]

    operations = [
        migrations.RunPython(agregar_permisos, quitar_permisos),
    ]
