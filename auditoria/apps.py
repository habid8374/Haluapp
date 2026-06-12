from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'auditoria'
    verbose_name = 'Auditoría de Cambios'

    def ready(self):
        import auditoria.signals  # noqa: F401 — conecta los receivers
