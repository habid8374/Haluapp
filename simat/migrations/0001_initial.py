import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('finanzas', '0025_institucion_bloqueo_secciones'),
    ]

    operations = [
        migrations.CreateModel(
            name='Departamento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(max_length=2, unique=True, verbose_name='Código DANE')),
                ('nombre', models.CharField(max_length=120, verbose_name='Nombre')),
            ],
            options={
                'verbose_name': 'Departamento (DANE)',
                'verbose_name_plural': 'Departamentos (DANE)',
                'ordering': ['nombre'],
            },
        ),
        migrations.CreateModel(
            name='Etnia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(max_length=20, unique=True, verbose_name='Código oficial')),
                ('nombre', models.CharField(max_length=255, verbose_name='Nombre')),
                ('habilitado', models.BooleanField(default=True, verbose_name='Habilitado')),
            ],
            options={
                'verbose_name': 'Etnia (SIMAT)',
                'verbose_name_plural': 'Etnias (SIMAT)',
                'ordering': ['nombre'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Resguardo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(max_length=20, unique=True, verbose_name='Código oficial')),
                ('nombre', models.CharField(max_length=255, verbose_name='Nombre')),
                ('habilitado', models.BooleanField(default=True, verbose_name='Habilitado')),
            ],
            options={
                'verbose_name': 'Resguardo (SIMAT)',
                'verbose_name_plural': 'Resguardos (SIMAT)',
                'ordering': ['nombre'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='EPS',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(max_length=20, unique=True, verbose_name='Código oficial')),
                ('nombre', models.CharField(max_length=255, verbose_name='Nombre')),
                ('habilitado', models.BooleanField(default=True, verbose_name='Habilitado')),
            ],
            options={
                'verbose_name': 'EPS (SIMAT)',
                'verbose_name_plural': 'EPS (SIMAT)',
                'ordering': ['nombre'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='CajaCompensacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(max_length=20, unique=True, verbose_name='Código oficial')),
                ('nombre', models.CharField(max_length=255, verbose_name='Nombre')),
                ('habilitado', models.BooleanField(default=True, verbose_name='Habilitado')),
            ],
            options={
                'verbose_name': 'Caja de Compensación (SIMAT)',
                'verbose_name_plural': 'Cajas de Compensación (SIMAT)',
                'ordering': ['nombre'],
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Municipio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('codigo', models.CharField(max_length=5, unique=True, verbose_name='Código DANE')),
                ('nombre', models.CharField(max_length=150, verbose_name='Nombre')),
                ('departamento', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='municipios', to='simat.departamento', verbose_name='Departamento')),
            ],
            options={
                'verbose_name': 'Municipio (DANE)',
                'verbose_name_plural': 'Municipios (DANE)',
                'ordering': ['nombre'],
            },
        ),
        migrations.CreateModel(
            name='Sede',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=200, verbose_name='Nombre de la sede')),
                ('codigo_dane_sede', models.CharField(blank=True, help_text='Código DANE de 12 dígitos asignado por el MEN a la sede.', max_length=20, verbose_name='Código DANE de la sede')),
                ('consecutivo', models.CharField(blank=True, help_text='Consecutivo de sede que exige el SIMAT.', max_length=20, verbose_name='Consecutivo de la sede')),
                ('zona', models.CharField(blank=True, choices=[('URBANA', 'Urbana'), ('RURAL', 'Rural')], max_length=10, verbose_name='Zona')),
                ('jornada_principal', models.CharField(blank=True, choices=[('MANANA', 'Mañana'), ('TARDE', 'Tarde'), ('NOCHE', 'Noche'), ('UNICA', 'Única'), ('COMPLETA', 'Completa'), ('FIN_DE_SEMANA', 'Fin de semana')], max_length=15, verbose_name='Jornada principal')),
                ('es_principal', models.BooleanField(default=False, verbose_name='¿Sede principal?')),
                ('activa', models.BooleanField(default=True, verbose_name='Activa')),
                ('institucion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sedes', to='finanzas.institucioneducativa', verbose_name='Institución')),
            ],
            options={
                'verbose_name': 'Sede',
                'verbose_name_plural': 'Sedes',
                'ordering': ['institucion', '-es_principal', 'nombre'],
            },
        ),
        migrations.AddConstraint(
            model_name='sede',
            constraint=models.UniqueConstraint(fields=('institucion', 'nombre'), name='uniq_sede_institucion_nombre'),
        ),
    ]
