from django.apps import AppConfig


class SimatConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'simat'
    verbose_name = 'SIMAT / SIMPADE'

    def ready(self):
        from . import signals  # noqa: F401  (registra las señales)
