from django.db import migrations, models

_TD = [
    ('TI', 'Tarjeta de Identidad'), ('CC', 'Cédula de Ciudadanía'),
    ('RC', 'Registro Civil'), ('PA', 'Pasaporte'), ('CE', 'Cédula de Extranjería'),
    ('NES', 'NES — Número establecido por la Secretaría'),
    ('PEP', 'PEP — Permiso Especial de Permanencia'), ('VISA', 'Visa'),
    ('TMF', 'TMF — Tarjeta de Movilidad Fronteriza'), ('OT', 'Otro'),
]


class Migration(migrations.Migration):

    dependencies = [
        ('gestion_academica', '0072_caracterizacion_simat_codificados'),
    ]

    operations = [
        migrations.AlterField(
            model_name='estudiante',
            name='tipo_documento',
            field=models.CharField(blank=True, choices=_TD, max_length=5, null=True, verbose_name='Tipo de Documento'),
        ),
        migrations.AlterField(
            model_name='familiar',
            name='tipo_documento',
            field=models.CharField(blank=True, choices=_TD, max_length=5, null=True, verbose_name='Tipo de Documento'),
        ),
    ]
