from django.db import migrations, models
import django.db.models.deletion


def backfill_nivel_materia(apps, schema_editor):
    """Rellena Materia.nivel_escolaridad infiriéndolo de los grados donde ya se
    dicta la materia (vía Curso). Solo se asigna cuando NO es ambiguo: si todos
    los cursos de esa materia están en grados de un mismo nivel, se toma ese
    nivel. Si hay varios niveles distintos, o no hay cursos, se deja vacío para
    que el coordinador lo defina."""
    Materia = apps.get_model('gestion_academica', 'Materia')
    Curso = apps.get_model('gestion_academica', 'Curso')
    for materia in Materia.objects.all().iterator():
        if materia.nivel_escolaridad_id:
            continue
        niveles = set(
            Curso.objects.filter(materia_id=materia.pk)
            .exclude(grado__nivel_escolaridad__isnull=True)
            .values_list('grado__nivel_escolaridad_id', flat=True)
            .distinct()
        )
        if len(niveles) == 1:
            materia.nivel_escolaridad_id = niveles.pop()
            materia.save(update_fields=['nivel_escolaridad'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0058_estudiante_bloqueo_acceso'),
    ]

    operations = [
        migrations.AddField(
            model_name='materia',
            name='nivel_escolaridad',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='materias',
                to='gestion_academica.nivelescolaridad',
                verbose_name='Nivel de Escolaridad',
            ),
        ),
        migrations.RunPython(backfill_nivel_materia, noop_reverse),
        migrations.AlterUniqueTogether(
            name='materia',
            unique_together={
                ('nombre_materia', 'nivel_escolaridad', 'institucion'),
                ('codigo_materia', 'institucion'),
            },
        ),
    ]
