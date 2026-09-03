from django.db import migrations


# Permisos de Simulaciones STEAM (PhET) para los grupos 'coordinadores' y
# 'docentes'. Mismo patrón que 0081 (permisos_proyectos_insignias_steam):
# asigna al Group, nunca por usuario.
#
# Ambos grupos SOLO consultan el catálogo (view_simulacionsteam) — el
# catálogo público lo cura la plataforma vía /admin/ (superusuario); un
# colegio no crea/edita simulaciones desde la interfaz en esta fase.
# Ambos grupos SÍ pueden asignar/quitar simulaciones a sus cursos
# (add/view/delete de la asignación) — no incluye 'change' porque editar
# una asignación es simplemente quitarla y volver a asignarla.
COORDINADORES_PERMISSIONS = [
    ('gestion_academica', 'simulacionsteam', 'view_simulacionsteam'),
    ('gestion_academica', 'asignacionsimulacionsteam', 'view_asignacionsimulacionsteam'),
    ('gestion_academica', 'asignacionsimulacionsteam', 'add_asignacionsimulacionsteam'),
    ('gestion_academica', 'asignacionsimulacionsteam', 'delete_asignacionsimulacionsteam'),
]

DOCENTES_PERMISSIONS = [
    ('gestion_academica', 'simulacionsteam', 'view_simulacionsteam'),
    ('gestion_academica', 'asignacionsimulacionsteam', 'view_asignacionsimulacionsteam'),
    ('gestion_academica', 'asignacionsimulacionsteam', 'add_asignacionsimulacionsteam'),
    ('gestion_academica', 'asignacionsimulacionsteam', 'delete_asignacionsimulacionsteam'),
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


def _sincronizar(Group, Permission, nombre_grupo, lista_permisos, agregar):
    group, _ = Group.objects.get_or_create(name=nombre_grupo)
    perms = [
        _get_permission(Permission, app_label, model, codename)
        for app_label, model, codename in lista_permisos
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
    _sincronizar(Group, Permission, 'coordinadores', COORDINADORES_PERMISSIONS, agregar=True)
    _sincronizar(Group, Permission, 'docentes', DOCENTES_PERMISSIONS, agregar=True)


def quitar_permisos(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    _sincronizar(Group, Permission, 'coordinadores', COORDINADORES_PERMISSIONS, agregar=False)
    _sincronizar(Group, Permission, 'docentes', DOCENTES_PERMISSIONS, agregar=False)


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0085_seed_simulaciones_steam'),
    ]

    operations = [
        migrations.RunPython(agregar_permisos, quitar_permisos),
    ]
