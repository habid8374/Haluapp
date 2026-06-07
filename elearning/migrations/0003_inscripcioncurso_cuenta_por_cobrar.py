import django.db.models.deletion
from django.db import migrations, models


def vincular_cuentas_legacy(apps, schema_editor):
    InscripcionCurso = apps.get_model("elearning", "InscripcionCurso")
    CuentaPorCobrarEstudiante = apps.get_model("finanzas", "CuentaPorCobrarEstudiante")

    for ins in InscripcionCurso.objects.filter(cuenta_por_cobrar__isnull=True).iterator(chunk_size=200):
        curso = ins.curso
        precio = getattr(curso, "precio", None)
        if precio is None or precio <= 0:
            continue
        marker = f"inscripción id={ins.pk}"
        cuenta = (
            CuentaPorCobrarEstudiante.objects.filter(
                estudiante_id=ins.estudiante_id,
                observaciones_internas__icontains=marker,
            )
            .order_by("-pk")
            .first()
        )
        if cuenta:
            ins.cuenta_por_cobrar_id = cuenta.pk
            ins.save(update_fields=["cuenta_por_cobrar_id"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("elearning", "0002_reassign_contenttypes_from_cursos"),
        ("finanzas", "0007_auditoriaexportacioncontable"),
    ]

    operations = [
        migrations.AddField(
            model_name="inscripcioncurso",
            name="cuenta_por_cobrar",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="inscripciones_elearning",
                to="finanzas.cuentaporcobrarestudiante",
            ),
        ),
        migrations.RunPython(vincular_cuentas_legacy, noop_reverse),
    ]
