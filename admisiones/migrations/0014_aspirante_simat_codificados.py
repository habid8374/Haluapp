import django.db.models.deletion
from django.db import migrations, models

_SISBEN = [('1', 'Grupo 1'), ('2', 'Grupo 2'), ('3', 'Grupo 3'), ('4', 'Grupo 4'), ('5', 'Grupo 5'), ('6', 'Grupo 6'), ('NO APLICA', 'No aplica')]
_CARACTER = [('1', 'Académico'), ('2', 'Técnico'), ('0', 'No aplica')]
_ESPECIALIDAD = [('05', 'Académico'), ('06', 'Industrial'), ('08', 'Comercial'), ('09', 'Pedagógico'), ('10', 'Agropecuario'), ('11', 'Promoción social'), ('07', 'Otro'), ('00', 'No aplica')]
_METODOLOGIA = [('1', 'Educación tradicional'), ('2', 'Escuela nueva'), ('3', 'Post primaria'), ('4', 'Telesecundaria'), ('5', 'SER'), ('8', 'Etnoeducación'), ('9', 'Aceleración del aprendizaje'), ('10', 'Jóvenes en extraedad y adultos'), ('11', 'Preescolar escolarizado'), ('12', 'Preescolar no/semi escolarizado'), ('39', 'Secundaria activa'), ('43', 'Escuela nueva activa'), ('51', 'Otra')]
_SITUACION = [('0', 'No estudió el año anterior'), ('1', 'Aprobó'), ('2', 'Reprobó'), ('4', 'Pendiente de logros'), ('6', 'Viene de otra IE'), ('7', 'Ingresa por primera vez'), ('8', 'No culminó estudios')]
_CONDICION = [('3', 'Desertó'), ('5', 'Trasladado a otra IE'), ('9', 'No aplica')]
_RECURSO = [('1', 'SGP'), ('2', 'FNR'), ('3', 'Recursos adicionales MEN'), ('4', 'Otros recursos de la Nación'), ('5', 'Recursos propios de la SE')]
_INTERNADO = [('1', 'Internado'), ('2', 'Semi-internado'), ('3', 'Ninguno')]
_VALORACION = [('1', 'Superior'), ('2', 'Alto'), ('3', 'Básico'), ('4', 'Bajo')]
_SN = [('S', 'Sí'), ('N', 'No')]
_SINO = [('SI', 'Sí'), ('NO', 'No')]


class Migration(migrations.Migration):

    dependencies = [
        ('admisiones', '0013_aspirante_acudiente'),
        ('simat', '0001_initial'),
    ]

    operations = [
        migrations.AddField(model_name='aspirante', name='sisben_simat', field=models.CharField(blank=True, choices=_SISBEN, max_length=10, verbose_name='SISBÉN (grupo SIMAT)')),
        migrations.AddField(model_name='aspirante', name='caracter', field=models.CharField(blank=True, choices=_CARACTER, max_length=2, verbose_name='Carácter')),
        migrations.AddField(model_name='aspirante', name='especialidad', field=models.CharField(blank=True, choices=_ESPECIALIDAD, max_length=2, verbose_name='Especialidad (media)')),
        migrations.AddField(model_name='aspirante', name='metodologia', field=models.CharField(blank=True, choices=_METODOLOGIA, max_length=2, verbose_name='Metodología/Modelo educativo')),
        migrations.AddField(model_name='aspirante', name='situacion_va', field=models.CharField(blank=True, choices=_SITUACION, max_length=1, verbose_name='Situación académica año anterior')),
        migrations.AddField(model_name='aspirante', name='condicion_va', field=models.CharField(blank=True, choices=_CONDICION, max_length=1, verbose_name='Condición del alumno año anterior')),
        migrations.AddField(model_name='aspirante', name='fuente_recurso', field=models.CharField(blank=True, choices=_RECURSO, max_length=1, verbose_name='Fuente de recursos')),
        migrations.AddField(model_name='aspirante', name='tipo_internado', field=models.CharField(blank=True, choices=_INTERNADO, max_length=1, verbose_name='Internado')),
        migrations.AddField(model_name='aspirante', name='valoracion_p1', field=models.CharField(blank=True, choices=_VALORACION, max_length=1, verbose_name='Valoración período 1')),
        migrations.AddField(model_name='aspirante', name='valoracion_p2', field=models.CharField(blank=True, choices=_VALORACION, max_length=1, verbose_name='Valoración período 2')),
        migrations.AddField(model_name='aspirante', name='subsidiado', field=models.CharField(blank=True, choices=_SINO, max_length=2, verbose_name='¿Subsidiado?')),
        migrations.AddField(model_name='aspirante', name='es_nuevo', field=models.CharField(blank=True, choices=_SINO, max_length=2, verbose_name='¿Nuevo en la institución?')),
        migrations.AddField(model_name='aspirante', name='proviene_sector_privado', field=models.CharField(blank=True, choices=_SINO, max_length=2, verbose_name='¿Proviene del sector privado?')),
        migrations.AddField(model_name='aspirante', name='proviene_otro_municipio', field=models.CharField(blank=True, choices=_SINO, max_length=2, verbose_name='¿Proviene de otro municipio?')),
        migrations.AddField(model_name='aspirante', name='madre_cabeza_familia', field=models.CharField(blank=True, choices=_SN, max_length=1, verbose_name='¿Madre cabeza de familia?')),
        migrations.AddField(model_name='aspirante', name='hijo_madre_cabeza_familia', field=models.CharField(blank=True, choices=_SN, max_length=1, verbose_name='¿Hijo de madre cabeza de familia?')),
        migrations.AddField(model_name='aspirante', name='beneficiario_veterano', field=models.CharField(blank=True, choices=_SN, max_length=1, verbose_name='¿Beneficiario veterano fuerza pública?')),
        migrations.AddField(model_name='aspirante', name='beneficiario_heroe', field=models.CharField(blank=True, choices=_SN, max_length=1, verbose_name='¿Beneficiario héroe de la nación?')),
        migrations.AddField(model_name='aspirante', name='numero_convenio', field=models.CharField(blank=True, max_length=30, verbose_name='Número de convenio')),
        migrations.AddField(model_name='aspirante', name='institucion_bienestar', field=models.CharField(blank=True, max_length=120, verbose_name='Institución de bienestar (ICBF)')),
        migrations.AddField(model_name='aspirante', name='expulsor_departamento', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='simat.departamento', verbose_name='Depto. expulsor (víctima)')),
        migrations.AddField(model_name='aspirante', name='expulsor_municipio', field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='simat.municipio', verbose_name='Municipio expulsor (víctima)')),
    ]
