from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trazado", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="tablerotrazado",
            name="estilo_letra",
            field=models.CharField(
                choices=[("CURSIVA", "Cursiva (ligada)"), ("IMPRENTA", "Imprenta (palo)")],
                default="CURSIVA", max_length=10, verbose_name="Tipo de letra de la guía",
            ),
        ),
    ]
