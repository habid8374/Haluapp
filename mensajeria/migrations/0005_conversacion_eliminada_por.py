from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mensajeria', '0004_presenciausuario_institucion'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversacion',
            name='eliminada_por_a',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='conversacion',
            name='eliminada_por_b',
            field=models.BooleanField(default=False),
        ),
    ]
