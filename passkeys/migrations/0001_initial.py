import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CredencialWebAuthn",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("credential_id", models.TextField(unique=True, verbose_name="ID de credencial")),
                ("public_key", models.TextField(verbose_name="Llave pública")),
                ("sign_count", models.BigIntegerField(default=0)),
                ("transports", models.CharField(blank=True, default="", max_length=255)),
                ("nombre_dispositivo", models.CharField(blank=True, default="", max_length=120, verbose_name="Nombre del dispositivo")),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("ultimo_uso", models.DateTimeField(blank=True, null=True)),
                ("usuario", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="credenciales_webauthn",
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Usuario",
                )),
            ],
            options={
                "verbose_name": "Credencial WebAuthn",
                "verbose_name_plural": "Credenciales WebAuthn",
                "ordering": ["-creado_en"],
            },
        ),
    ]
