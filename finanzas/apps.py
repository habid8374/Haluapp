# finanzas/apps.py
from django.apps import AppConfig

class FinanzasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'finanzas'

    def ready(self):
        print("Cargando señales de Finanzas...") # Añadimos esto para ver si se carga
        import finanzas.signals