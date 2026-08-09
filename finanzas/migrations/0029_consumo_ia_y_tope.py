from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('finanzas', '0028_institucion_simat_prestacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='institucioneducativa',
            name='ia_tope_mensual_cop',
            field=models.DecimalField(
                decimal_places=0, default=0, max_digits=12,
                help_text='Costo estimado máximo de IA por mes para esta institución. 0 = sin tope.',
                verbose_name='Tope de IA mensual (COP)',
            ),
        ),
        migrations.AddField(
            model_name='institucioneducativa',
            name='ia_bloquear_al_superar',
            field=models.BooleanField(
                default=True,
                help_text='Si está activo, al alcanzar el tope se pausan las funciones de IA (aviso amable). '
                          'Si no, solo se registra el consumo.',
                verbose_name='Bloquear IA al superar el tope',
            ),
        ),
        migrations.CreateModel(
            name='ConsumoIA',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('anio', models.PositiveIntegerField(verbose_name='Año')),
                ('mes', models.PositiveSmallIntegerField(verbose_name='Mes')),
                ('operaciones', models.PositiveIntegerField(default=0, verbose_name='Operaciones de IA')),
                ('tokens_in', models.BigIntegerField(default=0, verbose_name='Tokens de entrada')),
                ('tokens_out', models.BigIntegerField(default=0, verbose_name='Tokens de salida')),
                ('costo_estimado_cop', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Costo estimado (COP)')),
                ('actualizado', models.DateTimeField(auto_now=True)),
                ('institucion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='consumos_ia', to='finanzas.institucioneducativa', verbose_name='Institución')),
            ],
            options={
                'verbose_name': 'Consumo de IA',
                'verbose_name_plural': 'Consumos de IA',
                'ordering': ['-anio', '-mes', 'institucion'],
            },
        ),
        migrations.AddConstraint(
            model_name='consumoia',
            constraint=models.UniqueConstraint(fields=('institucion', 'anio', 'mes'), name='uniq_consumo_ia_inst_mes'),
        ),
    ]
