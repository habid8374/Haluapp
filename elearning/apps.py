from django.apps import AppConfig


class ElearningConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "elearning"
    verbose_name = "E-learning (ventas complementarias)"

    def ready(self):
        import elearning.signals  # noqa: F401
