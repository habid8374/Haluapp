from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cuestionarios', '0013_migrar_preguntas_legacy'),
    ]

    operations = [
        migrations.AddField(
            model_name='preguntacuestionario',
            name='imagen',
            field=models.ImageField(blank=True, help_text='Opcional: gráfica, esquema o imagen para interpretar.', null=True, upload_to='cuestionarios/preguntas/%Y/%m/', verbose_name='Imagen / gráfico de la pregunta'),
        ),
        migrations.AlterField(
            model_name='preguntacuestionario',
            name='tipo',
            field=models.CharField(choices=[('opcion_multiple', 'Opción Única'), ('seleccion_multiple', 'Selección Múltiple'), ('verdadero_falso', 'Verdadero/Falso'), ('texto_libre', 'Texto Libre'), ('emparejamiento', 'Emparejamiento'), ('completar', 'Completar (rellenar espacios)')], default='opcion_multiple', max_length=20),
        ),
        migrations.AddField(
            model_name='respuestaestudiante',
            name='respuesta_completar',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
