# Generated manually for entrada/salida y modalidad de liquidación docente.

from django.db import migrations, models
from django.utils import timezone


def backfill_dia_y_entrada(apps, schema_editor):
    Reg = apps.get_model("gestion_academica", "RegistroAsistenciaDocente")
    for r in Reg.objects.all().iterator(chunk_size=300):
        if r.dia is not None:
            continue
        d = timezone.localdate(r.fecha) if r.fecha else timezone.localdate()
        he = r.fecha if r.estado == "PRESENTE" else None
        Reg.objects.filter(pk=r.pk).update(dia=d, hora_entrada=he)


def dedupe_docente_dia(apps, schema_editor):
    Reg = apps.get_model("gestion_academica", "RegistroAsistenciaDocente")
    from django.db.models import Count

    grupos = (
        Reg.objects.exclude(dia__isnull=True)
        .values("docente_id", "dia")
        .annotate(n=Count("id"))
        .filter(n__gt=1)
    )
    for g in grupos:
        doc_id, dia = g["docente_id"], g["dia"]
        lst = list(Reg.objects.filter(docente_id=doc_id, dia=dia).order_by("pk"))
        if len(lst) <= 1:
            continue
        keeper = lst[0]
        he = keeper.hora_entrada
        hs = keeper.hora_salida
        estado = keeper.estado
        for x in lst[1:]:
            if x.hora_entrada and (he is None or x.hora_entrada < he):
                he = x.hora_entrada
            if x.hora_salida and (hs is None or x.hora_salida > hs):
                hs = x.hora_salida
            if x.estado == "PRESENTE":
                estado = "PRESENTE"
        keeper.hora_entrada = he
        keeper.hora_salida = hs
        keeper.estado = estado
        keeper.save(update_fields=["hora_entrada", "hora_salida", "estado"])
        for x in lst[1:]:
            x.delete()


def ensure_dia_not_null(apps, schema_editor):
    Reg = apps.get_model("gestion_academica", "RegistroAsistenciaDocente")
    for r in Reg.objects.filter(dia__isnull=True).iterator(chunk_size=200):
        d = timezone.localdate(r.fecha) if r.fecha else timezone.localdate()
        Reg.objects.filter(pk=r.pk).update(dia=d)


class Migration(migrations.Migration):

    dependencies = [
        ("gestion_academica", "0021_alter_periodoacademico_año_escolar"),
    ]

    operations = [
        migrations.AddField(
            model_name="docente",
            name="modalidad_liquidacion",
            field=models.CharField(
                choices=[
                    ("POR_HORA", "Por horas laboradas"),
                    ("SALARIO_FIJO", "Salario fijo (planta / directivo)"),
                ],
                default="SALARIO_FIJO",
                help_text="Por horas: útil para liquidar con marcas entrada/salida. Salario fijo: control de asistencia sin cálculo automático de horas pagadas.",
                max_length=20,
                verbose_name="Modalidad de liquidación",
            ),
        ),
        migrations.AddField(
            model_name="docente",
            name="valor_hora_docencia",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Opcional. Referencia para docentes por hora; no reemplaza la nómina legal.",
                max_digits=12,
                null=True,
                verbose_name="Valor hora (referencia)",
            ),
        ),
        migrations.AddField(
            model_name="registroasistenciadocente",
            name="dia",
            field=models.DateField(blank=True, db_index=True, null=True, verbose_name="Día de la jornada"),
        ),
        migrations.AddField(
            model_name="registroasistenciadocente",
            name="hora_entrada",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Marca de entrada"),
        ),
        migrations.AddField(
            model_name="registroasistenciadocente",
            name="hora_salida",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Marca de salida"),
        ),
        migrations.RunPython(backfill_dia_y_entrada, migrations.RunPython.noop),
        migrations.RunPython(dedupe_docente_dia, migrations.RunPython.noop),
        migrations.RunPython(ensure_dia_not_null, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="registroasistenciadocente",
            name="dia",
            field=models.DateField(db_index=True, verbose_name="Día de la jornada"),
        ),
        migrations.AlterField(
            model_name="registroasistenciadocente",
            name="estado",
            field=models.CharField(
                choices=[
                    ("PRESENTE", "Presente"),
                    ("AUSENTE", "Ausente"),
                    ("JUSTIFICADO", "Justificado"),
                ],
                default="PRESENTE",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="registroasistenciadocente",
            name="fecha",
            field=models.DateTimeField(auto_now=True, verbose_name="Última actualización"),
        ),
        migrations.AlterUniqueTogether(
            name="registroasistenciadocente",
            unique_together={("docente", "dia")},
        ),
        migrations.AlterModelOptions(
            name="registroasistenciadocente",
            options={
                "ordering": ["-dia", "-hora_entrada"],
                "verbose_name": "Registro de Asistencia de Docente",
                "verbose_name_plural": "Asistencias de Docentes",
            },
        ),
    ]
