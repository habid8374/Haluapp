import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admisiones', '0010_aspirante_apoyo_academico_especial_and_more'),
        ('simat', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='aspirante',
            name='primer_nombre',
            field=models.CharField(blank=True, max_length=60, verbose_name='Primer nombre'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='segundo_nombre',
            field=models.CharField(blank=True, max_length=60, verbose_name='Segundo nombre'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='primer_apellido',
            field=models.CharField(blank=True, max_length=60, verbose_name='Primer apellido'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='segundo_apellido',
            field=models.CharField(blank=True, max_length=60, verbose_name='Segundo apellido'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='lugar_expedicion_departamento',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='simat.departamento', verbose_name='Expedición documento · Departamento'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='lugar_expedicion_municipio',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='simat.municipio', verbose_name='Expedición documento · Municipio'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='nacionalidad',
            field=models.CharField(blank=True, max_length=60, verbose_name='Nacionalidad'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='pais_nacimiento',
            field=models.CharField(blank=True, max_length=60, verbose_name='País de nacimiento'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='departamento_nacimiento',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='simat.departamento', verbose_name='Nacimiento · Departamento'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='municipio_nacimiento',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='simat.municipio', verbose_name='Nacimiento · Municipio'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='departamento_residencia',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='simat.departamento', verbose_name='Residencia · Departamento'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='municipio_residencia',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='simat.municipio', verbose_name='Residencia · Municipio'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='barrio',
            field=models.CharField(blank=True, max_length=150, verbose_name='Barrio'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='campesino',
            field=models.BooleanField(default=False, verbose_name='¿Población campesina?'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='etnia_simat',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='simat.etnia', verbose_name='Etnia (código SIMAT)'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='resguardo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='simat.resguardo', verbose_name='Resguardo indígena'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='eps_simat',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='simat.eps', verbose_name='EPS (código SIMAT)'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='sede',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='simat.sede', verbose_name='Sede'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='jornada',
            field=models.CharField(blank=True, choices=[('MANANA', 'Mañana'), ('TARDE', 'Tarde'), ('NOCHE', 'Noche'), ('UNICA', 'Única'), ('COMPLETA', 'Completa'), ('FIN_DE_SEMANA', 'Fin de semana')], max_length=15, verbose_name='Jornada'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='grupo',
            field=models.CharField(blank=True, max_length=20, verbose_name='Grupo/Curso'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='modelo_educativo',
            field=models.CharField(blank=True, max_length=60, verbose_name='Modelo/Metodología educativa'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='fuente_recursos',
            field=models.CharField(blank=True, max_length=60, verbose_name='Fuente de recursos'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='internado',
            field=models.CharField(blank=True, max_length=20, verbose_name='Internado'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='matricula_contratada',
            field=models.BooleanField(default=False, verbose_name='¿Matrícula contratada?'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='repitente',
            field=models.BooleanField(default=False, verbose_name='¿Repitente?'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='situacion_academica_anterior',
            field=models.CharField(blank=True, max_length=60, verbose_name='Situación académica año anterior'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='simat_per_id',
            field=models.CharField(blank=True, max_length=20, verbose_name='SIMAT · PER_ID'),
        ),
        migrations.AddField(
            model_name='aspirante',
            name='simat_nui',
            field=models.CharField(blank=True, max_length=30, verbose_name='SIMAT · NUI'),
        ),
    ]
