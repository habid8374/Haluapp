import django.db.models.deletion
from django.db import migrations, models


def backfill_sede(apps, schema_editor):
    """Asigna sede a los estudiantes existentes:
    la de su aspirante de origen si la tiene; si no, la Sede Principal."""
    Estudiante = apps.get_model('gestion_academica', 'Estudiante')
    Sede = apps.get_model('simat', 'Sede')
    Aspirante = apps.get_model('admisiones', 'Aspirante')

    # estudiante_id → sede_id (desde el aspirante que lo originó)
    sede_por_estudiante = dict(
        Aspirante.objects
        .filter(estudiante_creado__isnull=False, sede__isnull=False)
        .values_list('estudiante_creado_id', 'sede_id')
    )
    # Sede Principal por institución (cache)
    principal = {}

    def principal_de(inst_id):
        if inst_id not in principal:
            s = (Sede.objects.filter(institucion_id=inst_id, es_principal=True).first()
                 or Sede.objects.filter(institucion_id=inst_id).first())
            principal[inst_id] = s.id if s else None
        return principal[inst_id]

    por_actualizar = []
    for e in Estudiante.objects.filter(sede__isnull=True).only('id', 'institucion_id'):
        sede_id = sede_por_estudiante.get(e.id) or principal_de(e.institucion_id)
        if sede_id:
            e.sede_id = sede_id
            por_actualizar.append(e)
        if len(por_actualizar) >= 500:
            Estudiante.objects.bulk_update(por_actualizar, ['sede'])
            por_actualizar = []
    if por_actualizar:
        Estudiante.objects.bulk_update(por_actualizar, ['sede'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0066_caracterizacion_simat'),
        ('simat', '0004_sede_principal_existentes'),
        ('admisiones', '0011_aspirante_simat_campos'),
    ]

    operations = [
        migrations.AddField(
            model_name='estudiante',
            name='sede',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='estudiantes', to='simat.sede', verbose_name='Sede',
            ),
        ),
        migrations.RunPython(backfill_sede, noop),
    ]
