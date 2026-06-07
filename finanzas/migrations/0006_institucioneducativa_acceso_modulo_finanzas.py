# Permiso canónico de acceso al módulo de finanzas + asignación retroactiva a grupos con permisos legacy.

from django.db import migrations


def _grant_acceso_finanzas(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    Group = apps.get_model("auth", "Group")

    ct = ContentType.objects.filter(app_label="finanzas", model="institucioneducativa").first()
    if not ct:
        return

    Permission.objects.get_or_create(
        codename="acceso_modulo_finanzas",
        content_type=ct,
        defaults={
            "name": "Puede acceder al módulo de finanzas (panel, reportes y exportaciones)",
        },
    )
    new_perm = Permission.objects.get(content_type=ct, codename="acceso_modulo_finanzas")

    legacy = {"view_pagoregistrado", "view_gasto", "view_cuentaporcobrarestudiante"}
    for group in Group.objects.iterator():
        codes = set(
            group.permissions.filter(content_type__app_label="finanzas").values_list(
                "codename", flat=True
            )
        )
        if codes.intersection(legacy):
            group.permissions.add(new_perm)


def _noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("finanzas", "0005_institucioneducativa_google_api_key_and_mp_secret"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="institucioneducativa",
            options={
                "verbose_name": "Institución Educativa",
                "verbose_name_plural": "Instituciones Educativas",
                "permissions": [
                    (
                        "can_manage_institutions",
                        "Puede gestionar instituciones educativas",
                    ),
                    (
                        "acceso_modulo_finanzas",
                        "Puede acceder al módulo de finanzas (panel, reportes y exportaciones)",
                    ),
                ],
            },
        ),
        migrations.RunPython(_grant_acceso_finanzas, _noop_reverse),
    ]
