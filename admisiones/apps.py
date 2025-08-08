# admisiones/apps.py
from django.apps import AppConfig

class AdmisionesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'admisiones'

    def ready(self):
        import admisiones.signals # Esta línea es crucial