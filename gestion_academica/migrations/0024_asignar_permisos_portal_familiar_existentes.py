# Generated manually: permisos Meta de Familiar no se asignaban al usuario al crear el perfil.

from django.db import migrations


def asignar_permisos_portal_familiar_existentes(apps, schema_editor):
    Familiar = apps.get_model("gestion_academica", "Familiar")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    User = apps.get_model("gestion_academica", "Usuario")

    ct = ContentType.objects.filter(
        app_label="gestion_academica", model="familiar"
    ).first()
    if not ct:
        return

    codenames = (
        "acceso_portal_familiar",
        "ver_calificaciones_estudiante_familiar",
        "ver_boletin_estudiante_familiar",
        "ver_deberes_estudiante_familiar",
    )
    perms = list(
        Permission.objects.filter(content_type=ct, codename__in=codenames)
    )
    if not perms:
        return

    for fam in Familiar.objects.all().iterator(chunk_size=200):
        user = User.objects.filter(pk=fam.usuario_id).first()
        if user:
            user.user_permissions.add(*perms)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("gestion_academica", "0023_intentoactividad_multiples_intentos"),
    ]

    operations = [
        migrations.RunPython(
            asignar_permisos_portal_familiar_existentes,
            noop_reverse,
        ),
    ]
