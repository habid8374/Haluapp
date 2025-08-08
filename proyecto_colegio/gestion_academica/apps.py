from django.apps import AppConfig

class GestionAcademicaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gestion_academica'

    def ready(self):
        import gestion_academica.signals  # 👈 Esto es lo que hace que Django lo cargue
