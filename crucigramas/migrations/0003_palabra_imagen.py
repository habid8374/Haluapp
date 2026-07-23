from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crucigramas", "0002_fechas"),
    ]

    operations = [
        migrations.AddField(
            model_name="palabracrucigrama",
            name="imagen",
            field=models.ImageField(
                blank=True, null=True, upload_to="crucigramas/pistas/",
                verbose_name="Imagen de pista (opcional)",
            ),
        ),
    ]
