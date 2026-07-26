import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0001_initial'),
        ('mensajeria', '0003_presenciausuario'),
    ]

    operations = [
        migrations.AddField(
            model_name='presenciausuario',
            name='institucion',
            field=models.ForeignKey(
                blank=True, editable=False, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='presencias', to='finanzas.institucioneducativa',
            ),
        ),
    ]
