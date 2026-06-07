# Generated for F3.5 mini-extension: warnings on inscription cobro creation.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admisiones', '0005_aspirante_unique_doc_y_lote_taskid'),
    ]

    operations = [
        migrations.AddField(
            model_name='loteimportacionaspirantes',
            name='filas_con_advertencia',
            field=models.PositiveIntegerField(
                default=0,
                help_text=(
                    'Filas creadas correctamente pero con problemas no críticos '
                    '(p. ej. el aspirante se creó pero no se generó la cuenta de '
                    'inscripción por configuración faltante).'
                ),
                verbose_name='Filas con advertencia',
            ),
        ),
        migrations.AlterField(
            model_name='loteimportacionaspirantes',
            name='errores',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "Lista de diccionarios: {tipo, fila, documento, mensaje}. "
                    "tipo='error' detiene la fila; tipo='warning' permite continuar."
                ),
                verbose_name='Errores y advertencias por fila',
            ),
        ),
    ]
