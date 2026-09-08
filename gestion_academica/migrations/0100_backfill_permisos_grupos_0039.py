from django.db import migrations


# La migración 0039 (setup_permission_groups) crea los grupos docentes,
# estudiantes, coordinadores y familiares y les intenta asignar permisos,
# pero NO llama a `_ensure_permissions_exist()` como sí hacen las
# migraciones posteriores (0056, 0061, 0099). En una instalación NUEVA,
# donde todas las migraciones se aplican en una sola corrida de
# `migrate`, los permisos de modelo de gestion_academica todavía no
# existen cuando 0039 se ejecuta (Django los crea con el signal
# post_migrate, que corre solo al final de TODA la corrida) — así que
# `_get_permission()` devuelve None para cada uno y ningún permiso queda
# realmente asignado a estos 4 grupos. Confirmado con una instalación
# limpia: los 4 grupos existen, pero con 0 de los permisos que 0039
# pretendía darles.
#
# Esto es grave porque afecta a los roles con más usuarios de la
# plataforma (docente, estudiante, coordinador, familiar): cualquier
# vista protegida con @permission_required (no con un chequeo de `rol`)
# les da acceso denegado. Esta migración reasigna exactamente los mismos
# permisos que 0039 quiso dar, de forma segura e idempotente — si algún
# entorno ya los tiene (por ejemplo, producción, si allí las migraciones
# se aplicaron en corridas separadas), esto no cambia nada.

DOCENTES_PERMISSIONS = [
    ('gestion_academica', 'deber', 'view_deber'),
    ('gestion_academica', 'deber', 'add_deber'),
    ('gestion_academica', 'deber', 'change_deber'),
    ('gestion_academica', 'deber', 'delete_deber'),
    ('gestion_academica', 'registroasistencia', 'add_registroasistencia'),
    ('gestion_academica', 'registroasistencia', 'view_registroasistencia'),
    ('gestion_academica', 'registroasistencia', 'change_registroasistencia'),
    ('gestion_academica', 'actividadcalificable', 'acceso_libro_notas_docente'),
    ('gestion_academica', 'actividadcalificable', 'view_actividadcalificable'),
    ('gestion_academica', 'actividadcalificable', 'add_actividadcalificable'),
    ('gestion_academica', 'actividadcalificable', 'change_actividadcalificable'),
    ('gestion_academica', 'actividadcalificable', 'delete_actividadcalificable'),
    ('gestion_academica', 'lecciondiaria', 'add_lecciondiaria'),
    ('gestion_academica', 'lecciondiaria', 'view_lecciondiaria'),
    ('gestion_academica', 'lecciondiaria', 'change_lecciondiaria'),
    ('gestion_academica', 'tipoactividad', 'view_tipoactividad'),
    ('gestion_academica', 'tipoactividad', 'add_tipoactividad'),
    ('gestion_academica', 'tipoactividad', 'change_tipoactividad'),
    ('gestion_academica', 'tipoactividad', 'delete_tipoactividad'),
    ('gestion_academica', 'plansemanal', 'view_plansemanal'),
    ('gestion_academica', 'plansemanal', 'add_plansemanal'),
    ('gestion_academica', 'plansemanal', 'change_plansemanal'),
    ('gestion_academica', 'entregadeber', 'view_entregadeber'),
    ('gestion_academica', 'entregadeber', 'change_entregadeber'),
]

# 'ver_mis_deberes' y 'puede_realizar_entrega_deber' NO son permisos del
# modelo Deber — 0039 los buscaba ahí y por eso nunca se resolvían ni
# siquiera arreglando el problema de timing de arriba. Están declarados
# en `Estudiante.Meta.permissions` (models.py ~línea 590). El codename
# 'puede_realizar_entrega_deber' también existe, por separado, en
# `EntregaDeber.Meta.permissions` — no importa cuál de las dos filas se
# asigne, ambas producen el mismo permiso efectivo
# 'gestion_academica.puede_realizar_entrega_deber' al verificar con
# has_perm (Django no distingue por modelo, solo por app_label+codename).
ESTUDIANTES_PERMISSIONS = [
    ('gestion_academica', 'estudiante', 'ver_mis_deberes'),
    ('gestion_academica', 'estudiante', 'puede_realizar_entrega_deber'),
    ('gestion_academica', 'entregadeber', 'add_entregadeber'),
    ('gestion_academica', 'entregadeber', 'view_entregadeber'),
]

COORDINADORES_PERMISSIONS = DOCENTES_PERMISSIONS + [
    ('gestion_academica', 'registroasistenciadocente', 'view_registroasistenciadocente'),
]

# Mismo problema: 'ver_deberes_estudiante_familiar' está declarado en
# `Familiar.Meta.permissions` (~línea 1018), no en Deber/EntregaDeber.
FAMILIARES_PERMISSIONS = [
    ('gestion_academica', 'familiar', 'ver_deberes_estudiante_familiar'),
]


def _ensure_permissions_exist():
    try:
        from django.apps import apps as global_apps
        from django.contrib.auth.management import create_permissions
    except Exception:
        return
    for app_label in ('gestion_academica', 'auth'):
        try:
            create_permissions(global_apps.get_app_config(app_label), verbosity=0)
        except Exception:
            pass


def _get_permission(Permission, app_label, model, codename):
    try:
        return Permission.objects.get(
            content_type__app_label=app_label,
            content_type__model=model,
            codename=codename,
        )
    except Permission.DoesNotExist:
        return None


def backfill_permisos(apps, schema_editor):
    _ensure_permissions_exist()

    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    grupos_config = [
        ('docentes', DOCENTES_PERMISSIONS),
        ('estudiantes', ESTUDIANTES_PERMISSIONS),
        ('coordinadores', COORDINADORES_PERMISSIONS),
        ('familiares', FAMILIARES_PERMISSIONS),
    ]

    for group_name, perms_list in grupos_config:
        try:
            group = Group.objects.get(name=group_name)
        except Group.DoesNotExist:
            continue
        perms_to_add = [
            p for (a, m, c) in perms_list
            if (p := _get_permission(Permission, a, m, c)) is not None
        ]
        if perms_to_add:
            group.permissions.add(*perms_to_add)


def noop_reverse(apps, schema_editor):
    """No revertimos: estos permisos deberían haber estado asignados desde
    la 0039 original — quitarlos al bajar esta migración no tiene sentido."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0099_grupo_administradores_y_permisos_noticia'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(backfill_permisos, noop_reverse),
    ]
