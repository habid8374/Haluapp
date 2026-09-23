from django.db import migrations


def _get_permission(Permission, app_label, model, codename):
    try:
        return Permission.objects.get(
            content_type__app_label=app_label,
            content_type__model=model,
            codename=codename,
        )
    except Permission.DoesNotExist:
        return None


def fix_permission(apps, schema_editor):
    """La migración 0039 quiso otorgar 'acceso_libro_notas_docente' a los
    grupos 'docentes' y 'coordinadores', pero buscó el permiso bajo el
    modelo 'actividadcalificable' — el permiso en realidad está
    declarado en Meta.permissions del modelo Docente. La búsqueda
    fallaba silenciosamente y el permiso nunca se asignó. Se corrige
    aquí, de forma idempotente (group.permissions.add() no duplica)."""
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')

    perm = _get_permission(Permission, 'gestion_academica', 'docente', 'acceso_libro_notas_docente')
    if not perm:
        return

    for group_name in ('docentes', 'coordinadores'):
        group = Group.objects.filter(name=group_name).first()
        if group:
            group.permissions.add(perm)


def unfix_permission(apps, schema_editor):
    """No revertimos: quitar este permiso podría afectar asignaciones
    manuales hechas después. Dejar como no-op es lo seguro."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0103_add_es_ciberacoso'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(fix_permission, unfix_permission),
    ]
