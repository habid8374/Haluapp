from django.contrib import admin
from django.urls import path, include, reverse_lazy, re_path
from django.views.generic.base import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from allauth.account.views import LoginView
from django_ratelimit.decorators import ratelimit

from gestion_academica.forms import HaluPasswordResetForm

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

def health_check(request):
    return JsonResponse({"status": "ok"})

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('admin/', admin.site.urls),
           
    # ======================================================= #
    #     RUTAS DE AUTENTICACIÓN CORREGIDAS                   #
    # ======================================================= #
    # 1. Definimos explícitamente la URL /login/ que tú quieres.
    #    Asegúrate de que la plantilla esté en 'templates/registration/login.html'
    path('login/', ratelimit(key='ip', rate='10/m', method='POST', block=True)(
        LoginView.as_view(template_name='registration/login.html')
    ), name='login'),

    # 1.b Restablecimiento de contraseña con plantillas propias (HALU PULSE).
    #     HaluPasswordResetForm envía el correo con la cuenta Brevo/SMTP que
    #     cada institución ya tiene configurada (ver gestion_academica.forms),
    #     no con una cuenta global del sistema. Debe ir ANTES del include de
    #     abajo para que gane esta definición sobre la de Django por defecto.
    path('accounts/password_reset/', ratelimit(key='ip', rate='5/m', method='POST', block=True)(
        auth_views.PasswordResetView.as_view(
            template_name='registration/password_reset_form.html',
            form_class=HaluPasswordResetForm,
            email_template_name='registration/password_reset_email.txt',
            html_email_template_name='registration/password_reset_email.html',
            subject_template_name='registration/password_reset_subject.txt',
        )
    ), name='password_reset'),

    # 2. Incluimos el resto de las URLs de autenticación de Django (logout, password_reset, etc.)
    #    Estas quedarán bajo el prefijo /accounts/ (ej: /accounts/logout/)
    path('accounts/', include('django.contrib.auth.urls')),
    # ======================================================= #

    # PWA: sirve /manifest.json, /serviceworker.js y /offline/ desde la raíz.
    path('', include('pwa.urls')),

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
    # Rate-limit del login móvil (oráculo de adivinación de contraseñas).
    path('api/token/', ratelimit(key='ip', rate='10/m', method='POST', block=True)(
        TokenObtainPairView.as_view()
    ), name='token_obtain_pair'),
    path('api/token/refresh/', ratelimit(key='ip', rate='30/m', method='POST', block=True)(
        TokenRefreshView.as_view()
    ), name='token_refresh'),
    path('cuestionarios/', include('cuestionarios.urls', namespace='cuestionarios')),
    path('mensajeria/', include('mensajeria.urls', namespace='mensajeria')),
    path('auditoria/', include('auditoria.urls', namespace='auditoria')),
    path('2fa/', include('autenticacion_2fa.urls', namespace='2fa')),
    path('simulacros/', include('simulacros.urls', namespace='simulacros')),
    path('piar/', include('piar.urls', namespace='piar')),
    path('evaluacion-docente/', include('evaluacion_docente.urls', namespace='evaluacion_docente')),
    path('autoevaluacion/', include('autoevaluacion_institucional.urls', namespace='autoevaluacion_institucional')),
    path('crucigramas/', include('crucigramas.urls', namespace='crucigramas')),
    path('sopa-letras/', include('sopa_letras.urls', namespace='sopa_letras')),
    path('memoria/', include('memoria.urls', namespace='memoria')),
    path('flashcards/', include('flashcards.urls', namespace='flashcards')),
    path('quiz-audio/', include('quiz_audio.urls', namespace='quiz_audio')),
    path('secuencias/', include('secuencias.urls', namespace='secuencias')),
    path('trazado/', include('trazado.urls', namespace='trazado')),
    path('passkeys/', include('passkeys.urls', namespace='passkeys')),
]

# --- 2. CONFIGURACIÓN PARA ARCHIVOS EN DESARROLLO ---
if settings.DEBUG:
    # Esta línea sirve los archivos que los usuarios suben (MEDIA_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    # Esta línea sirve los archivos estáticos de tu proyecto (STATICFILES_DIRS)
    urlpatterns += staticfiles_urlpatterns()