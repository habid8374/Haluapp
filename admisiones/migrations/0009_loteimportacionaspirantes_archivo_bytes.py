import admisiones.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admisiones', '0008_aspirante_campos_observador'),
    ]

    operations = [
        migrations.AddField(
            model_name='loteimportacionaspirantes',
            name='archivo_bytes',
            field=models.BinaryField(
                blank=True, null=True,
                verbose_name='Contenido del archivo (bytes)',
                help_text='Copia en BD para que Celery pueda leerlo sin acceso al disco.',
            ),
        ),
        migrations.AlterField(
            model_name='loteimportacionaspirantes',
            name='archivo',
            field=models.FileField(
                blank=True, null=True,
                upload_to=admisiones.models._ruta_archivo_lote_importacion,
                verbose_name='Archivo Excel',
            ),
        ),
    ]
