import django.db.models.deletion
from django.db import migrations, models


def seed_grupos(apps, schema_editor):
    """Crea un grupo '01' por cada grado existente y asigna a cada estudiante
    el grupo '01' de su grado_actual. Colegios que no manejen secciones quedan
    con un único grupo por grado, transparente para el usuario."""
    Grado = apps.get_model('gestion_academica', 'Grado')
    Grupo = apps.get_model('gestion_academica', 'Grupo')
    Estudiante = apps.get_model('gestion_academica', 'Estudiante')
    Sede = apps.get_model('simat', 'Sede')

    # Sede Principal por institución (cache)
    principal = {}

    def principal_de(inst_id):
        if inst_id not in principal:
            s = (Sede.objects.filter(institucion_id=inst_id, es_principal=True).first()
                 or Sede.objects.filter(institucion_id=inst_id).first())
            principal[inst_id] = s.id if s else None
        return principal[inst_id]

    # grado_id → grupo '01' id
    grupo_por_grado = {}
    for grado in Grado.objects.all().only('pk', 'institucion_id'):
        grupo, _creado = Grupo.objects.get_or_create(
            institucion_id=grado.institucion_id,
            grado_id=grado.pk,
            jornada='',
            nombre='01',
            defaults={'sede_id': principal_de(grado.institucion_id), 'activo': True},
        )
        grupo_por_grado[grado.pk] = grupo.pk

    # Asigna el grupo '01' del grado_actual a cada estudiante sin grupo.
    por_actualizar = []
    for e in Estudiante.objects.filter(grupo__isnull=True, grado_actual__isnull=False).only('grado_actual_id'):
        gid = grupo_por_grado.get(e.grado_actual_id)
        if gid:
            e.grupo_id = gid
            por_actualizar.append(e)
        if len(por_actualizar) >= 500:
            Estudiante.objects.bulk_update(por_actualizar, ['grupo'])
            por_actualizar = []
    if por_actualizar:
        Estudiante.objects.bulk_update(por_actualizar, ['grupo'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0067_estudiante_sede'),
        ('simat', '0004_sede_principal_existentes'),
        ('finanzas', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Grupo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('jornada', models.CharField(blank=True, choices=[('MANANA', 'Mañana'), ('TARDE', 'Tarde'), ('NOCHE', 'Noche'), ('UNICA', 'Única'), ('COMPLETA', 'Completa'), ('FIN_DE_SEMANA', 'Fin de semana')], max_length=15, verbose_name='Jornada')),
                ('nombre', models.CharField(help_text='Código o letra de la sección, ej. 01, 02, A, B.', max_length=20, verbose_name='Nombre del grupo')),
                ('activo', models.BooleanField(default=True, verbose_name='Activo')),
                ('grado', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='grupos', to='gestion_academica.grado', verbose_name='Grado')),
                ('institucion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='grupos', to='finanzas.institucioneducativa', verbose_name='Institución')),
                ('sede', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='grupos', to='simat.sede', verbose_name='Sede')),
            ],
            options={
                'verbose_name': 'Grupo',
                'verbose_name_plural': 'Grupos',
                'ordering': ['grado__orden', 'nombre'],
            },
        ),
        migrations.AddConstraint(
            model_name='grupo',
            constraint=models.UniqueConstraint(fields=('institucion', 'grado', 'jornada', 'nombre'), name='uniq_grupo_institucion_grado_jornada_nombre'),
        ),
        migrations.AddField(
            model_name='estudiante',
            name='grupo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='estudiantes', to='gestion_academica.grupo', verbose_name='Grupo/Sección'),
        ),
        migrations.RunPython(seed_grupos, noop),
    ]
