from django.db import migrations, models
import django.db.models.deletion


def backfill_municipio_etc(apps, schema_editor):
    """Mapea el antiguo código DANE de texto al FK DIVIPOLA."""
    Institucion = apps.get_model('finanzas', 'InstitucionEducativa')
    Municipio = apps.get_model('simat', 'Municipio')
    for inst in Institucion.objects.exclude(simat_codigo_municipio_dane='').only(
        'pk', 'simat_codigo_municipio_dane'
    ):
        codigo = (inst.simat_codigo_municipio_dane or '').strip()
        if not codigo:
            continue
        mpio = Municipio.objects.filter(codigo=codigo).first()
        if mpio:
            inst.simat_municipio_etc_id = mpio.pk
            inst.save(update_fields=['simat_municipio_etc'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0026_institucion_config_simat'),
        ('simat', '0003_seed_municipios'),
    ]

    operations = [
        migrations.AddField(
            model_name='institucioneducativa',
            name='simat_municipio_etc',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='+', to='simat.municipio',
                help_text='Municipio/distrito de la Secretaría de Educación (ETC). '
                          'Se elige de la lista oficial DIVIPOLA; el código DANE se toma de ahí.',
                verbose_name='SIMAT · Municipio (ETC)',
            ),
        ),
        migrations.RunPython(backfill_municipio_etc, noop),
        migrations.RemoveField(
            model_name='institucioneducativa',
            name='simat_codigo_municipio_dane',
        ),
        migrations.AddField(
            model_name='institucioneducativa',
            name='simat_consecutivo_sede_automatico',
            field=models.BooleanField(
                default=True,
                help_text='Si está activo, al crear una sede el sistema le asigna el '
                          'consecutivo (Principal=01, anexas 02, 03…) y queda editable. Si se '
                          'desactiva, el consecutivo se digita manualmente en cada sede.',
                verbose_name='SIMAT · Numerar consecutivo de sedes automáticamente',
            ),
        ),
    ]
