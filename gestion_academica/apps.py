# gestion_academica/apps.py
from django.apps import AppConfig


class GestionAcademicaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'gestion_academica'
    verbose_name = "Módulo de Gestión Académica"

    def ready(self):
        # Registra las señales del módulo.
        import gestion_academica.signals
        # Conecta el signal de PagoRegistrado (app finanzas) una vez que
        # todos los modelos están cargados.
        gestion_academica.signals._connect_pago_signal()
        # Reagrupa el índice del admin de Django en categorías temáticas
        # (ver proyecto_colegio/admin_site.py) — evita que cada una de las
        # ~25 apps aparezca como una caja suelta y desordenada.
        from proyecto_colegio.admin_site import instalar as _instalar_admin_agrupado
        _instalar_admin_agrupado()