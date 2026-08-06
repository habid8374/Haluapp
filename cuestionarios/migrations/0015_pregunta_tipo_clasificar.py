from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cuestionarios', '0014_pregunta_imagen_completar'),
    ]

    operations = [
        migrations.AlterField(
            model_name='preguntacuestionario',
            name='tipo',
            field=models.CharField(choices=[('opcion_multiple', 'Opción Única'), ('seleccion_multiple', 'Selección Múltiple'), ('verdadero_falso', 'Verdadero/Falso'), ('texto_libre', 'Texto Libre'), ('emparejamiento', 'Emparejamiento'), ('completar', 'Completar (rellenar espacios)'), ('clasificar', 'Clasificar en categorías')], default='opcion_multiple', max_length=20),
        ),
    ]
