from django.db import migrations


# Psicoorientador(a) → convivencia (Ley 1620), observador, bienestar y apoyo a
# PIAR (Decreto 1421). El acceso real de sus vistas es por ROL; este grupo se
# crea por consistencia (todos los roles tienen su grupo) y para futuros
# permisos, y para auto-asignar a los usuarios con rol 'psicologo'.
PSICOORIENTADORES_PERMISSIONS = [
    # Ver estudiantes (contexto psicosocial), sin editar notas
    ('gestion_academica', 'estudiante', 'view_estudiante'),
    # Observador del estudiante
    ('gestion_academica', 'anotacionobservador', 'view_anotacionobservador'),
    ('gestion_academica', 'anotacionobservador', 'add_anotacionobservador'),
    ('gestion_academica', 'anotacionobservador', 'change_anotacionobservador'),
    # Casos de convivencia (HALU Sentinel)
    ('gestion_academica', 'casoconvivencia', 'view_casoconvivencia'),
    ('gestion_academica', 'casoconvivencia', 'add_casoconvivencia'),
    ('gestion_academica', 'casoconvivencia', 'change_casoconvivencia'),
    ('gestion_academica', 'accioncaso', 'view_accioncaso'),
    ('gestion_academica', 'accioncaso', 'add_accioncaso'),
    # PIAR (crea borrador; el coordinador aprueba)
    ('piar', 'piar', 'view_piar'),
    ('piar', 'piar', 'add_piar'),
    ('piar', 'piar', 'change_piar'),
    ('piar', 'ajustepiar', 'view_ajustepiar'),
    ('piar', 'ajustepiar', 'add_ajustepiar'),
    ('piar', 'ajustepiar', 'change_ajustepiar'),
]


def _ensure_permissions_exist():
    try:
        from django.apps import apps as global_apps
        from django.contrib.auth.management import create_permissions
    except Exception:
        return
    for app_label in ('gestion_academica', 'piar', 'auth'):
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


def setup_group(apps, schema_editor):
    _ensure_permissions_exist()
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    Usuario = apps.get_model('gestion_academica', 'Usuario')

    group, _ = Group.objects.get_or_create(name='psicoorientadores')
    perms = [
        p for (a, m, c) in PSICOORIENTADORES_PERMISSIONS
        if (p := _get_permission(Permission, a, m, c)) is not None
    ]
    if perms:
        group.permissions.add(*perms)

    usuarios = Usuario.objects.filter(rol='psicologo')
    if usuarios.exists():
        group.user_set.add(*usuarios)


def teardown_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name='psicoorientadores').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0060_usuario_rol_psicoorientador'),
        ('piar', '0001_initial'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(setup_group, teardown_group),
    ]
