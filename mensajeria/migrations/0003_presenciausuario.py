import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('mensajeria', '0002_alter_mensaje_adjunto'),
    ]

    operations = [
        migrations.CreateModel(
            name='PresenciaUsuario',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('conexiones', models.PositiveIntegerField(default=0)),
                ('estado_manual', models.CharField(choices=[('DISPONIBLE', 'En línea'), ('AUSENTE', 'Ausente')], default='DISPONIBLE', max_length=12)),
                ('ausente_auto', models.BooleanField(default=False)),
                ('last_seen', models.DateTimeField(default=django.utils.timezone.now)),
                ('usuario', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='presencia', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Presencia de Usuario',
                'verbose_name_plural': 'Presencias de Usuarios',
            },
        ),
    ]
