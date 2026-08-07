from django.db import migrations, models

TIPO_DOC = [('TI', 'Tarjeta de Identidad'), ('CC', 'Cédula de Ciudadanía'), ('RC', 'Registro Civil'), ('PA', 'Pasaporte'), ('CE', 'Cédula de Extranjería'), ('OT', 'Otro')]
PARENTESCO = [('PADRE', 'Padre'), ('MADRE', 'Madre'), ('ABUELO', 'Abuelo(a)'), ('TIO', 'Tío(a)'), ('HERMANO', 'Hermano(a)'), ('TUTOR', 'Tutor legal'), ('OTRO', 'Otro')]


class Migration(migrations.Migration):

    dependencies = [
        ('admisiones', '0012_backfill_nombres_simat'),
    ]

    operations = [
        migrations.AddField(model_name='aspirante', name='acudiente_nombres', field=models.CharField(blank=True, max_length=150, verbose_name='Acudiente · Nombres')),
        migrations.AddField(model_name='aspirante', name='acudiente_apellidos', field=models.CharField(blank=True, max_length=150, verbose_name='Acudiente · Apellidos')),
        migrations.AddField(model_name='aspirante', name='acudiente_tipo_documento', field=models.CharField(blank=True, choices=TIPO_DOC, max_length=2, null=True, verbose_name='Acudiente · Tipo de documento')),
        migrations.AddField(model_name='aspirante', name='acudiente_documento', field=models.CharField(blank=True, max_length=20, verbose_name='Acudiente · Documento')),
        migrations.AddField(model_name='aspirante', name='acudiente_parentesco', field=models.CharField(blank=True, choices=PARENTESCO, max_length=15, verbose_name='Acudiente · Parentesco')),
        migrations.AddField(model_name='aspirante', name='acudiente_email', field=models.EmailField(blank=True, max_length=254, verbose_name='Acudiente · Correo')),
        migrations.AddField(model_name='aspirante', name='acudiente_telefono', field=models.CharField(blank=True, max_length=20, verbose_name='Acudiente · Teléfono')),
    ]
