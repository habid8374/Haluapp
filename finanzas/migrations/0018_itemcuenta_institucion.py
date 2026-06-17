from django.db import migrations, models
import django.db.models.deletion


def backfill_institucion(apps, schema_editor):
    """Rellena ItemCuenta.institucion desde la cuenta asociada."""
    ItemCuenta = apps.get_model('finanzas', 'ItemCuenta')
    items = ItemCuenta.objects.filter(institucion__isnull=True).select_related('cuenta')
    for item in items.iterator():
        item.institucion_id = item.cuenta.institucion_id
        item.save(update_fields=['institucion'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0017_alter_institucioneducativa_brevo_sender_email_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemcuenta',
            name='institucion',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='items_cuenta',
                to='finanzas.institucioneducativa',
            ),
        ),
        migrations.RunPython(backfill_institucion, noop_reverse),
        migrations.AlterField(
            model_name='itemcuenta',
            name='institucion',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='items_cuenta',
                to='finanzas.institucioneducativa',
            ),
        ),
    ]
