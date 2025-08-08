# gestion_academica/apps.py
from django.apps import AppConfig


class GestionAcademicaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gestion_academica'
    verbose_name = "Módulo de Gestión Académica"

    def ready(self):
        # Esta es la única línea que necesitas para registrar las señales.
        import gestion_academica.signals