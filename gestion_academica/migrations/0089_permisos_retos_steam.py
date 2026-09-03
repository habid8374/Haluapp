from django.db import migrations


# Permisos de Retos STEAM (plantillas de ingeniería/robótica) para
# 'coordinadores' y 'docentes'. Mismo patrón que 0086
# (permisos_simulaciones_steam): solo view — el catálogo lo cura la
# plataforma vía /admin/; usar una plantilla al crear un Proyecto STEAM ya
# lo permite add_proyectosteam (migración 0081), no hace falta un permiso
# nuevo para eso.
PERMISOS = [
    ('gestion_academica', 'retosteam', 'view_retosteam'),
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


def _sincronizar(Group, Permission, nombre_grupo, agregar):
    group, _ = Group.objects.get_or_create(name=nombre_grupo)
    perms = [
        _get_permission(Permission, app_label, model, codename)
        for app_label, model, codename in PERMISOS
    ]
    perms = [p for p in perms if p]
    if not perms:
        return
    if agregar:
        group.permissions.add(*perms)
    else:
        group.permissions.remove(*perms)


def agregar_permisos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    _sincronizar(Group, Permission, 'coordinadores', agregar=True)
    _sincronizar(Group, Permission, 'docentes', agregar=True)


def quitar_permisos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    _sincronizar(Group, Permission, 'coordinadores', agregar=False)
    _sincronizar(Group, Permission, 'docentes', agregar=False)


class Migration(migrations.Migration):

    dependencies = [
        ("gestion_academica", "0088_seed_retos_steam"),
    ]

    operations = [
        migrations.RunPython(agregar_permisos, quitar_permisos),
    ]
