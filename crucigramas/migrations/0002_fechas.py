from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crucigramas", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="crucigrama",
            name="fecha_inicio",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Disponible desde"),
        ),
        migrations.AddField(
            model_name="crucigrama",
            name="fecha_fin",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Plazo final"),
        ),
    ]
