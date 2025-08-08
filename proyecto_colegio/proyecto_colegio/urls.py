# proyecto_colegio/urls.py (El archivo principal de URLs del proyecto)

from django.contrib import admin
from django.urls import path, include # Asegúrate de importar include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('academico/', include('gestion_academica.urls')), # Incluye las URLs de tu aplicación
    path('accounts/', include('django.contrib.auth.urls')), # Para login, logout, etc.
    # Puedes añadir más inclusiones de otras apps aquí si las tienes
]

# Esto es para servir archivos de medios (como los subidos por FileField) durante el desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
