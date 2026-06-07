from django.apps import AppConfig


class MensajeriaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mensajeria'
    verbose_name = 'Mensajería Directa'

    def ready(self):
        import mensajeria.signals  # noqa: F401
