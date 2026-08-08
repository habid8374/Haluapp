from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cuestionarios', '0019_pregunta_tipo_respuesta_numerica'),
    ]

    operations = [
        migrations.AddField(
            model_name='preguntacuestionario',
            name='enunciado_simple',
            field=models.TextField(blank=True, default='', help_text='Versión simplificada del enunciado, generada con IA para apoyo a la lectura.', verbose_name='Enunciado en lectura fácil (IA)'),
        ),
        migrations.AddField(
            model_name='preguntacuestionario',
            name='imagen_alt',
            field=models.TextField(blank=True, default='', help_text='Texto alternativo de la imagen para lectores de pantalla, generado con IA.', verbose_name='Descripción de la imagen (IA)'),
        ),
    ]
