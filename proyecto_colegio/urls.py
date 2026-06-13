from django.contrib import admin
from django.urls import path, include, reverse_lazy, re_path
from django.views.generic.base import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from allauth.account.views import LoginView
from django_ratelimit.decorators import ratelimit

from django.contrib.auth import views as auth_views
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)


# --- 1. IMPORTACIÓN CLAVE AÑADIDA ---
# Esta es la herramienta que le enseñará a Daphne a servir archivos estáticos.
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

# --- Personalización del Panel de Administración ---
admin.site.site_header = "Administración de HALU"
admin.site.site_title = "Portal de Administración HALU"
admin.site.index_title = "Bienvenido al Portal de Administración de HALU"
admin.site.site_url = reverse_lazy('gestion_academica:inicio_academico')

urlpatterns = [
    path('admin/', admin.site.urls),
           
    # ======================================================= #
    #     RUTAS DE AUTENTICACIÓN CORREGIDAS                   #
    # ======================================================= #
    # 1. Definimos explícitamente la URL /login/ que tú quieres.
    #    Asegúrate de que la plantilla esté en 'templates/registration/login.html'
    path('login/', ratelimit(key='ip', rate='10/m', method='POST', block=True)(
        LoginView.as_view(template_name='registration/login.html')
    ), name='login'),
    
    
    # 2. Incluimos el resto de las URLs de autenticación de Django (logout, password_reset, etc.)
    #    Estas quedarán bajo el prefijo /accounts/ (ej: /accounts/logout/)
    path('accounts/', include('django.contrib.auth.urls')),
    # ======================================================= #

    path('accounts/', include('allauth.urls')),
    path('elearning/', include('elearning.urls')),
    re_path(
        r"^cursos(?:/.*)?$",
        RedirectView.as_view(url="/elearning/catalogo/", permanent=False),
    ),
    
    
    # Inclusión de las URLs de tus aplicaciones
    path('admisiones/', include('admisiones.urls', namespace='admisiones')),
    path('academico/', include('gestion_academica.urls', namespace='gestion_academica')),
    path('academico/recursos/', include('recursos_educativos.urls', namespace='recursos_educativos')),
    path('finanzas/', include('finanzas.urls', namespace='finanzas')),
    path('finanzas/facturacion-electronica/', include('facturacion_electronica.urls', namespace='facturacion_electronica')),
    path('halu-control/', include('platform_control.urls', namespace='platform_control')),

    # Redirección de la raíz del sitio al dashboard académico
    path('', RedirectView.as_view(pattern_name='gestion_academica:inicio_academico', permanent=False)),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('cuestionarios/', include('cuestionarios.urls', namespace='cuestionarios')),
    path('mensajeria/', include('mensajeria.urls', namespace='mensajeria')),
    path('auditoria/', include('auditoria.urls', namespace='auditoria')),
    path('2fa/', include('autenticacion_2fa.urls', namespace='2fa')),
    path('simulacros/', include('simulacros.urls', namespace='simulacros')),
]

# --- 2. CONFIGURACIÓN PARA ARCHIVOS EN DESARROLLO ---
if settings.DEBUG:
    # Esta línea sirve los archivos que los usuarios suben (MEDIA_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    # Esta línea sirve los archivos estáticos de tu proyecto (STATICFILES_DIRS)
    urlpatterns += staticfiles_urlpatterns()