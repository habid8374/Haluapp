# settings.py (al principio del archivo)
import os
from dotenv import load_dotenv

load_dotenv() # Esto lee las variables de tu archivo .env

import os
from django.contrib.auth import get_user_model # Aunque se usa en la función comentada, se mantiene
from django.shortcuts import redirect # Aunque se usa en la función comentada, se mantiene
from pathlib import Path
from datetime import timedelta


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')

# --- CONFIGURACIÓN PARA REVERSE PROXY (NGROK, HEROKU, ETC.) ---
# Estas líneas le dicen a Django que confíe en las cabeceras del proxy
# para construir correctamente las URLs de retorno con https://
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

CSRF_TRUSTED_ORIGINS = ['http://72.60.27.222']

# Application definition

SUPERADMIN_MASTER_PASSWORD = os.environ.get('SUPERADMIN_MASTER_PASSWORD')

INSTALLED_APPS = [
    # 1. TUS APLICACIONES PRIMERO
    'daphne',
    'channels',
    'admisiones.apps.AdmisionesConfig',
    'finanzas.apps.FinanzasConfig',
    'gestion_academica.apps.GestionAcademicaConfig',
    'cuestionarios.apps.CuestionariosConfig',
    
    
    # 2. APPS DE TERCEROS DESPUÉS (si tienes más, van aquí)
    'corsheaders',  # Para permitir CORS desde la app móvil
    'import_export',
    'crispy_forms',
    'crispy_bootstrap5',
    'rest_framework.authtoken',
    'django.contrib.humanize',
    'rest_framework_simplejwt',
    
            
    # 3. APPS DE DJANGO AL FINAL
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django_celery_results',

     # --- APPS DE ALLAUTH (AÑADIR ESTE BLOQUE) ---
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    # Proveedor específico para Google
    'allauth.socialaccount.providers.google',
]

SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# --- Comportamiento de la cuenta ---

# CRÍTICO: Le dice a allauth que tu modelo de Usuario NO usa un campo de 'username'.
ACCOUNT_USER_MODEL_USERNAME_FIELD = None

# Reemplaza a la antigua configuración ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_USERNAME_REQUIRED = False

# Reemplaza a la antigua configuración ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_AUTHENTICATION_METHOD = 'email'

# Reemplaza a la antigua configuración ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_REQUIRED = True

# Asegura que cada email sea único en la plataforma.
ACCOUNT_UNIQUE_EMAIL = True

# No requerir una segunda verificación de email por ahora.
ACCOUNT_EMAIL_VERIFICATION = 'none'


# URLs a las que redirigir después del login/logout
LOGIN_REDIRECT_URL = 'gestion_academica:inicio_academico'
LOGOUT_REDIRECT_URL = 'login'

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # Debe estar al principio
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', 
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'proyecto_colegio.middleware.InstitucionActivaMiddleware', # <-- AÑADE ESTA LÍNEA AQUÍ
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    
    
    # --- MIDDLEWARE PARA REGISTRO INICIAL ---
    # Si quieres que el sistema SIEMPRE redirija a registro_inicial si no hay usuarios,
    # descomenta esta línea después de crear el archivo proyecto_colegio/middleware.py
    #'proyecto_colegio.middleware.RedireccionRegistroInicialMiddleware', # ¡AÑADIDO!
]

REST_FRAMEWORK = {
    # Define los métodos de autenticación por defecto en el orden que se probarán.
    'DEFAULT_AUTHENTICATION_CLASSES': (
        # 1. Intenta autenticar con Token JWT (para la app móvil)
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        
        # 2. Si falla, intenta con la sesión de Django (para el panel web)
        'rest_framework.authentication.SessionAuthentication',
        
        # 3. Como último recurso, prueba la autenticación básica (opcional)
        'rest_framework.authentication.BasicAuthentication',
    ),
    
    # Define los permisos por defecto para todas las vistas de API.
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    )
}

ROOT_URLCONF = 'proyecto_colegio.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Directorios de plantillas a nivel de proyecto. Aquí irán base.html, base_academico.html, base_finanzas.html, etc.
        'DIRS': [BASE_DIR / 'templates'], # Usando pathlib.Path para construir la ruta
        'APP_DIRS': True, # Para que Django busque plantillas dentro de las carpetas 'templates' de cada app
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'gestion_academica.context_processors.branding_processor',
                
            ],
        },
    },
]

WSGI_APPLICATION = 'proyecto_colegio.wsgi.application'



# Database
# https://docs.djangoproject.com/en/5.2/topics/i18n/

if DEBUG:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'OPTIONS': {'timeout': 20},
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2', # ¡Ajustado!
            'NAME': os.getenv('DB_NAME'),
            'USER': os.getenv('DB_USER'),
            'PASSWORD': os.getenv('DB_PASSWORD'),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', ''),
        }
    }


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8}, # Recomendación: al menos 8 caracteres
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

# Configuración de Idioma y Zona Horaria
LANGUAGE_CODE = 'es-co' # Más específico para español de Colombia si es tu principal
TIME_ZONE = 'America/Bogota' # Correcto para Barranquilla
USE_I18N = True # Para habilitar la internacionalización
USE_TZ = True # Para habilitar el soporte de zona horaria


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = '/static/'

# Directorios donde Django buscará archivos estáticos además de los directorios 'static' de las apps
STATICFILES_DIRS = [
    BASE_DIR / 'static', # Usando pathlib.Path. Debe apuntar a tu carpeta 'static' en la raíz del proyecto
]

# La RUTA ABSOLUTA donde collectstatic recolectará todos los archivos estáticos para producción.
STATIC_ROOT = BASE_DIR / 'staticfiles_collected' # Usando pathlib.Path


# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- CONFIGURACIÓN DE AUTENTICACIÓN ---
AUTH_USER_MODEL = 'gestion_academica.Usuario' # ¡CRUCIAL! Debe ser exacto
LOGIN_URL = 'login' # Nombre de la URL de login (generalmente de django.contrib.auth.urls)
LOGIN_REDIRECT_URL = 'gestion_academica:inicio_academico' # A dónde ir después de un login exitoso
LOGOUT_REDIRECT_URL = 'login' # A dónde ir después de un logout exitoso (puede ser otra página)

# --- CONFIGURACIÓN DE ARCHIVOS MEDIA (Subidos por usuarios) ---
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media' # Usando pathlib.Path


# --- CONFIGURACIÓN DE DJANGO CRISPY FORMS ---
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"


# --- CONFIGURACIÓN GLOBAL DEL SOFTWARE (Inamovible por interfaz) ---
SOFTWARE_NAME = "HALU - Sistema de Gestión Escolar"
SOFTWARE_LOGO_URL = "core/img/logo_mi_software.png" # Ruta relativa dentro de STATICFILES_DIRS
SOFTWARE_SLOGAN = "Conectando mentes, creando futuros."
SOFTWARE_CONTACT_EMAIL = "haluplataformaescolar@gmail.com"

# --- CONFIGURACIÓN DE ENVÍO DE CORREO ELECTRÓNICO ---

# Para desarrollo: imprime los correos en la consola en lugar de enviarlos.
#EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Cuando vayas a producción, comentarás la línea de arriba y descomentarás
# y rellenarás una configuración como esta (ejemplo para Gmail):
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'tu_correo@gmail.com'  # Tu dirección de correo
EMAIL_HOST_PASSWORD = 'tu_contraseña_de_aplicacion' # ¡Usa una contraseña de aplicación, no tu contraseña real!

# Dirección de correo por defecto desde la que se enviarán los correos
DEFAULT_FROM_EMAIL = 'Admisiones Colegio HALU <noreply@halu.com>'

GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')



# --- (Opcional) CONFIGURACIÓN DE SIMPLE JWT ---
# Puedes añadir esto para configurar la duración de los tokens, etc.
# from datetime import timedelta
# 

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60), # Aumentado a 60 minutos
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": False,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": False,

    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": "",
    "AUDIENCE": None,
    "ISSUER": None,
    "JSON_ENCODER": None,
    "JWK_URL": None,
    "LEEWAY": 0,

    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",

    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",

    "JTI_CLAIM": "jti",

    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=5),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=1),

    "TOKEN_OBTAIN_SERIALIZER": "rest_framework_simplejwt.serializers.TokenObtainPairSerializer",
    "TOKEN_REFRESH_SERIALIZER": "rest_framework_simplejwt.serializers.TokenRefreshSerializer",
    "TOKEN_VERIFY_SERIALIZER": "rest_framework_simplejwt.serializers.TokenVerifySerializer",
    "TOKEN_BLACKLIST_SERIALIZER": "rest_framework_simplejwt.serializers.TokenBlacklistSerializer",
    "SLIDING_TOKEN_OBTAIN_SERIALIZER": "rest_framework_simplejwt.serializers.TokenObtainSlidingSerializer",
    "SLIDING_TOKEN_REFRESH_SERIALIZER": "rest_framework_simplejwt.serializers.TokenRefreshSlidingSerializer",
}

# --- CONFIGURACIÓN DE CORS PARA APP MÓVIL ---
CORS_ALLOWED_ORIGINS = [
    'http://localhost:8081',
    'http://127.0.0.1:8081',
    'http://72.60.27.222', # ¡Ajustado a tu IP!
]

CORS_ALLOW_ALL_ORIGINS = False  # Solo para desarrollo, cambiar en producción

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'ngrok-skip-browser-warning',  # Para ngrok
]

# --- CONFIGURACIÓN DE LOGS PARA VER MENSAJES INFO EN CONSOLA ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": "debug.log",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
}

# --- CONFIGURACIÓN DE CELERY ---
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = 'django-db' # Guarda los resultados en la BD de Django
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'America/Bogota' # Usa tu zona horaria

# ✅ Limita la concurrencia mientras usas SQLite (evita "database is locked")
CELERY_WORKER_CONCURRENCY = 1

# --- CONFIGURACIÓN DE DJANGO CHANNELS ---
# Apunta al archivo de enrutamiento principal de tu proyecto
ASGI_APPLICATION = 'proyecto_colegio.asgi.application'

# Configuración del "canal de comunicación" que usará Redis
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            # Usa la variable de entorno REDIS_HOST si existe, de lo contrario, usa localhost
            "hosts": [os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379')],
        },
    },
}


# Static files configuration for development on DEBUG=False
if not DEBUG:
    STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles_collected')

    STATICFILES_DIRS = [
        os.path.join(BASE_DIR, "static"),
        # Puedes agregar otras carpetas de estáticos aquí si las tienes
    ]
