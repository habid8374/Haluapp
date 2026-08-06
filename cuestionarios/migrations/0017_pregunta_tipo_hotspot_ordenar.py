from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cuestionarios', '0016_pregunta_tipo_etiquetar'),
    ]

    operations = [
        migrations.AlterField(
            model_name='preguntacuestionario',
            name='tipo',
            field=models.CharField(choices=[('opcion_multiple', 'Opción Única'), ('seleccion_multiple', 'Selección Múltiple'), ('verdadero_falso', 'Verdadero/Falso'), ('texto_libre', 'Texto Libre'), ('emparejamiento', 'Emparejamiento'), ('completar', 'Completar (rellenar espacios)'), ('clasificar', 'Clasificar en categorías'), ('etiquetar', 'Etiquetar imagen (esquema)'), ('hotspot', 'Zonas activas (clic en la imagen)'), ('ordenar', 'Ordenar / Línea de tiempo')], default='opcion_multiple', max_length=20),
        ),
    ]
