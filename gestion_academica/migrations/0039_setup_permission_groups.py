from django.db import migrations


DOCENTES_PERMISSIONS = [
    # Deberes
    ('gestion_academica', 'deber', 'view_deber'),
    ('gestion_academica', 'deber', 'add_deber'),
    ('gestion_academica', 'deber', 'change_deber'),
    ('gestion_academica', 'deber', 'delete_deber'),
    # Asistencia
    ('gestion_academica', 'registroasistencia', 'add_registroasistencia'),
    ('gestion_academica', 'registroasistencia', 'view_registroasistencia'),
    ('gestion_academica', 'registroasistencia', 'change_registroasistencia'),
    # Libro de notas (custom)
    ('gestion_academica', 'actividadcalificable', 'acceso_libro_notas_docente'),
    # Actividades calificables
    ('gestion_academica', 'actividadcalificable', 'view_actividadcalificable'),
    ('gestion_academica', 'actividadcalificable', 'add_actividadcalificable'),
    ('gestion_academica', 'actividadcalificable', 'change_actividadcalificable'),
    ('gestion_academica', 'actividadcalificable', 'delete_actividadcalificable'),
    # Lección diaria
    ('gestion_academica', 'lecciondiaria', 'add_lecciondiaria'),
    ('gestion_academica', 'lecciondiaria', 'view_lecciondiaria'),
    ('gestion_academica', 'lecciondiaria', 'change_lecciondiaria'),
    # Tipo actividad
    ('gestion_academica', 'tipoactividad', 'view_tipoactividad'),
    ('gestion_academica', 'tipoactividad', 'add_tipoactividad'),
    ('gestion_academica', 'tipoactividad', 'change_tipoactividad'),
    ('gestion_academica', 'tipoactividad', 'delete_tipoactividad'),
    # Plan semanal
    ('gestion_academica', 'plansemanal', 'view_plansemanal'),
    ('gestion_academica', 'plansemanal', 'add_plansemanal'),
    ('gestion_academica', 'plansemanal', 'change_plansemanal'),
    # Entrega deber
    ('gestion_academica', 'entregadeber', 'view_entregadeber'),
    ('gestion_academica', 'entregadeber', 'change_entregadeber'),
]

ESTUDIANTES_PERMISSIONS = [
    ('gestion_academica', 'deber', 'ver_mis_deberes'),
    ('gestion_academica', 'deber', 'puede_realizar_entrega_deber'),
    ('gestion_academica', 'entregadeber', 'add_entregadeber'),
    ('gestion_academica', 'entregadeber', 'view_entregadeber'),
]

COORDINADORES_PERMISSIONS = [
    # All docente perms plus coordinador-only ones
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
    ('gestion_academica', 'registroasistenciadocente', 'view_registroasistenciadocente'),
]

FAMILIARES_PERMISSIONS = [
    ('gestion_academica', 'deber', 'ver_deberes_estudiante_familiar'),
    ('gestion_academica', 'entregadeber', 'ver_deberes_estudiante_familiar'),
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


def setup_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    Usuario = apps.get_model('gestion_academica', 'Usuario')

    groups_config = [
        ('docentes', 'docente', DOCENTES_PERMISSIONS),
        ('estudiantes', 'estudiante', ESTUDIANTES_PERMISSIONS),
        ('coordinadores', 'coordinador', COORDINADORES_PERMISSIONS),
        ('familiares', 'familiar', FAMILIARES_PERMISSIONS),
    ]

    for group_name, rol, perms_list in groups_config:
        group, _ = Group.objects.get_or_create(name=group_name)

        perms_to_add = []
        for app_label, model, codename in perms_list:
            perm = _get_permission(Permission, app_label, model, codename)
            if perm:
                perms_to_add.append(perm)

        if perms_to_add:
            group.permissions.add(*perms_to_add)

        # Add all existing users with this rol to the group
        usuarios = Usuario.objects.filter(rol=rol)
        if usuarios.exists():
            group.user_set.add(*usuarios)


def teardown_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    for name in ('docentes', 'estudiantes', 'coordinadores', 'familiares'):
        Group.objects.filter(name=name).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0038_dba_predefinido'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(setup_groups, teardown_groups),
    ]
