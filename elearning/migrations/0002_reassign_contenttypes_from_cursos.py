# Migra ContentType de la app antigua "cursos" a "elearning" (permisos y admin).

from django.db import migrations


def _merge_permissions_into(Permission, source_ct, keep_ct):
    """Reasigna permisos de source_ct → keep_ct evitando UniqueViolation.

    Si en keep_ct ya existe un permiso con el mismo codename, se elimina la
    duplicación en source_ct en vez de intentar el UPDATE (que rompería la
    restricción auth_permission(content_type_id, codename)).
    """
    if source_ct.pk == keep_ct.pk:
        return
    existing = set(
        Permission.objects.filter(content_type=keep_ct).values_list("codename", flat=True)
    )
    Permission.objects.filter(content_type=source_ct, codename__in=existing).delete()
    Permission.objects.filter(content_type=source_ct).update(content_type=keep_ct)


def forwards(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")

    models_vm = (
        "curso",
        "modulo",
        "material",
        "evaluacion",
        "pregunta",
        "opcion",
        "inscripcioncurso",
        "progresomodulo",
    )

    for model in models_vm:
        olds = list(ContentType.objects.filter(app_label="cursos", model=model).order_by("id"))
        news = list(ContentType.objects.filter(app_label="elearning", model=model).order_by("id"))

        if olds and news:
            keep = news[0]
            for old_ct in olds:
                _merge_permissions_into(Permission, old_ct, keep)
                old_ct.delete()
            for dup in news[1:]:
                _merge_permissions_into(Permission, dup, keep)
                dup.delete()
        elif olds and not news:
            keep = olds[0]
            keep.app_label = "elearning"
            keep.save(update_fields=["app_label"])
            for dup in olds[1:]:
                _merge_permissions_into(Permission, dup, keep)
                dup.delete()
        elif news and len(news) > 1:
            keep = news[0]
            for dup in news[1:]:
                _merge_permissions_into(Permission, dup, keep)
                dup.delete()


def backwards(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(
        app_label="elearning",
        model__in=[
            "curso",
            "modulo",
            "material",
            "evaluacion",
            "pregunta",
            "opcion",
            "inscripcioncurso",
            "progresomodulo",
        ],
    ).update(app_label="cursos")


class Migration(migrations.Migration):

    dependencies = [
        ("elearning", "0001_initial"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]
