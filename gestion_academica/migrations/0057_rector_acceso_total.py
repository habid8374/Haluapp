from django.db import migrations


# El rector/directivo es la máxima autoridad de la institución: debe poder
# acceder a todo (académico, finanzas, admisiones) si lo desea. Además de los
# candados por rol (que ya incluyen 'rector' en el código), aquí le damos al
# grupo 'rectores' los PERMISOS de Django necesarios para ver y operar los
# módulos, uniendo lo de coordinador + tesorería + secretaría y sumando el
# acceso a los módulos académico y de finanzas. Todo scoped por institución en
# las vistas (multi-institución intacto).

# CRUD académico core (para gestionar estudiantes, grados, notas, etc.).
ACADEMICO_CORE = []
for _model in [
    'estudiante', 'grado', 'materia', 'curso', 'periodoacademico',
    'calificacion', 'actividadcalificable', 'tipoactividad', 'deber',
    'entregadeber', 'mallacurricular', 'itemmalla', 'plansemanal',
    'itemplansemanal', 'anotacionobservador', 'lecciondiaria',
    'registroasistencia', 'descriptorlogro', 'mencion', 'eventoinstitucional',
    'directorcurso', 'bloquehorario', 'aula',
]:
    for _acc in ('view', 'add', 'change', 'delete'):
        ACADEMICO_CORE.append(('gestion_academica', _model, f'{_acc}_{_model}'))

MODULO_PERMS = [
    ('gestion_academica', 'usuario', 'acceso_modulo_academico'),
    ('finanzas', 'institucioneducativa', 'acceso_modulo_finanzas'),
]


def _ensure_permissions_exist():
    try:
        from django.apps import apps as global_apps
        from django.contrib.auth.management import create_permissions
    except Exception:
        return
    for app_label in ('gestion_academica', 'finanzas', 'admisiones', 'auth'):
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


def grant_rector(apps, schema_editor):
    _ensure_permissions_exist()
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    rectores, _ = Group.objects.get_or_create(name='rectores')

    perm_ids = set()

    # 1) Unión de permisos de coordinador + tesorería + secretaría.
    for gname in ('coordinadores', 'tesoreria', 'secretarias'):
        try:
            g = Group.objects.get(name=gname)
            perm_ids.update(g.permissions.values_list('pk', flat=True))
        except Group.DoesNotExist:
            pass

    # 2) Acceso a módulos + CRUD académico core.
    for app_label, model, codename in MODULO_PERMS + ACADEMICO_CORE:
        p = _get_permission(Permission, app_label, model, codename)
        if p:
            perm_ids.add(p.pk)

    if perm_ids:
        rectores.permissions.add(*Permission.objects.filter(pk__in=perm_ids))


def revoke_rector(apps, schema_editor):
    # Reversa conservadora: dejamos el grupo, solo limpiamos permisos.
    Group = apps.get_model('auth', 'Group')
    try:
        Group.objects.get(name='rectores').permissions.clear()
    except Group.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0056_setup_grupos_administrativos'),
        ('finanzas', '0006_institucioneducativa_acceso_modulo_finanzas'),
        ('admisiones', '0010_aspirante_apoyo_academico_especial_and_more'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(grant_rector, revoke_rector),
    ]
