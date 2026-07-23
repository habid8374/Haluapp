from django.apps import AppConfig


class PasskeysConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'passkeys'
    verbose_name = 'Passkeys / Huella (WebAuthn)'
