# settings.py (al principio del archivo)
import os
from dotenv import load_dotenv

load_dotenv() # Esto lee las variables de tu archivo .env

import os
from django.contrib.auth import get_user_model # Aunque se usa en la función comentada, se mantiene
from django.shortcuts import redirect # Aunque se usa en la función comentada, se mantiene
from pathlib import Path
from datetime import timedelta
from django.core.exceptions import ImproperlyConfigured


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG') == 'True'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',') + [
    '.ngrok-free.app',
    '.trycloudflare.com',
    '127.0.0.1',
    'localhost',
]

# --- CONFIGURACIÓN PARA REVERSE PROXY (NGROK, HEROKU, ETC.) ---
# Estas líneas le dicen a Django que confíe en las cabeceras del proxy
# para construir correctamente las URLs de retorno con https://
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

# Dominios de confianza para CSRF. Añade tu dominio de producción en .env:
# CSRF_TRUSTED_ORIGINS=https://app.halu.co,https://*.ngrok-free.app
_csrf_raw = os.environ.get('CSRF_TRUSTED_ORIGINS', 'https://*.ngrok-free.app,https://*.trycloudflare.com')
CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_raw.split(',') if o.strip()]

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
    'elearning.apps.ElearningConfig',
    'mensajeria.apps.MensajeriaConfig',
    'recursos_educativos.apps.RecursosEducativosConfig',
    'platform_control.apps.PlatformControlConfig',
    'facturacion_electronica.apps.FacturacionElectronicaConfig',
    'auditoria.apps.AuditoriaConfig',
    'autenticacion_2fa.apps.Autenticacion2faConfig',
    'simulacros.apps.SimulacrosConfig',
    'piar.apps.PiarConfig',


    # 2. APPS DE TERCEROS DESPUÉS (si tienes más, van aquí)
    'django_ratelimit',
    'corsheaders',  # Para permitir CORS desde la app móvil
    'import_export',
    'crispy_forms',
    'crispy_bootstrap5',
    'rest_framework.authtoken',
    'django.contrib.humanize',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    
            
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

# Configuración actual de allauth (evita warnings deprecados)
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*', 'password2*']

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
    'auditoria.middleware.AuditoriaMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'proyecto_colegio.middleware.InstitucionActivaMiddleware', # <-- AÑADE ESTA LÍNEA AQUÍ
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'autenticacion_2fa.middleware.Verificacion2FAMiddleware',

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


def _env_trim(key, default=""):
    """Lee variable de entorno y quita espacios y comillas simples/dobles típicas de .env."""
    val = os.getenv(key, default)
    if val is None:
        return ""
    val = str(val).strip()
    if len(val) >= 2 and val[0] in "'\"" and val[0] == val[-1]:
        val = val[1:-1].strip()
    return val


def _use_sqlite_toggle():
    """USE_SQLITE=1 (o true/yes/on) fuerza SQLite."""
    return _env_trim("USE_SQLITE").lower() in ("1", "true", "yes", "on")


def _postgresql_database_config_from_env():
    """
    Configuración PostgreSQL (motor predeterminado si DB_ENGINE no está en .env).

    Requiere DB_HOST, DB_NAME y DB_USER no vacíos. DB_PASSWORD puede ir vacío si el
    servidor lo permite (p. ej. trust en red local); debe existir la clave en .env
    si usas contraseña.
    """
    default_engine = "django.db.backends.postgresql"
    engine = _env_trim("DB_ENGINE") or default_engine
    postgres_engine_aliases = {
        "django.db.backends.postgresql",
        "django.db.backends.postgresql_psycopg2",
    }
    if engine not in postgres_engine_aliases:
        raise ImproperlyConfigured(
            f"DB_ENGINE={engine!r} no es un motor PostgreSQL soportado. "
            f"Usa {default_engine!r}, django.db.backends.postgresql_psycopg2, "
            "deja DB_ENGINE vacío para el predeterminado, o USE_SQLITE=1."
        )

    db_host = _env_trim("DB_HOST")
    db_name = _env_trim("DB_NAME")
    db_user = _env_trim("DB_USER")
    db_password = _env_trim("DB_PASSWORD")
    if not (db_host and db_name and db_user):
        raise ImproperlyConfigured(
            "PostgreSQL es el motor por defecto (USE_SQLITE distinto de 1). "
            "Define DB_HOST, DB_NAME y DB_USER en el entorno, o activa USE_SQLITE=1 "
            "(p. ej. si psycopg2 falla en Windows)."
        )

    pg_options = {}
    sslmode = _env_trim("DB_SSLMODE")
    if sslmode:
        pg_options["sslmode"] = sslmode
    # 60 s por defecto: Daphne reutiliza la conexión durante un minuto
    # en lugar de abrir/cerrar en cada request.
    conn_max_age_raw = _env_trim("DB_CONN_MAX_AGE", "60")
    try:
        conn_max_age = int(conn_max_age_raw)
    except ValueError:
        conn_max_age = 60

    cfg = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": db_name,
        "USER": db_user,
        "PASSWORD": db_password,
        "HOST": db_host,
        "PORT": _env_trim("DB_PORT", "5432") or "5432",
        "CONN_MAX_AGE": conn_max_age,
    }
    if pg_options:
        cfg["OPTIONS"] = pg_options
    return {"default": cfg}


if _use_sqlite_toggle():
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
            "OPTIONS": {"timeout": 20},
        },
    }
else:
    DATABASES = _postgresql_database_config_from_env()

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

# --- CONFIGURACIÓN DE ARCHIVOS MEDIA ---
# Si se configuran variables S3/R2, usa almacenamiento en la nube (necesario en
# Railway ya que hay dos contenedores separados: Daphne y Celery).
# Compatible con AWS S3 y Cloudflare R2 (endpoint personalizado).
_AWS_BUCKET = os.environ.get('AWS_STORAGE_BUCKET_NAME')

if _AWS_BUCKET:
    # Django 5.x: DEFAULT_FILE_STORAGE ya no existe; el storage se define en STORAGES.
    STORAGES = {
        "default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    AWS_STORAGE_BUCKET_NAME = _AWS_BUCKET
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'auto')
    AWS_S3_ENDPOINT_URL = os.environ.get('AWS_S3_ENDPOINT_URL')  # Para Cloudflare R2
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None
    MEDIA_URL = f'https://{_AWS_BUCKET}.s3.amazonaws.com/' if not AWS_S3_ENDPOINT_URL else f'{AWS_S3_ENDPOINT_URL}/{_AWS_BUCKET}/'
else:
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- CONFIGURACIÓN DE AUTENTICACIÓN ---
AUTH_USER_MODEL = 'gestion_academica.Usuario' # ¡CRUCIAL! Debe ser exacto
LOGIN_URL = 'login' # Nombre de la URL de login (generalmente de django.contrib.auth.urls)
LOGIN_REDIRECT_URL = 'gestion_academica:inicio_academico' # A dónde ir después de un login exitoso
LOGOUT_REDIRECT_URL = 'login' # A dónde ir después de un logout exitoso (puede ser otra página)

# --- CONFIGURACIÓN DE DJANGO CRISPY FORMS ---
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"


# --- CONFIGURACIÓN GLOBAL DEL SOFTWARE (Inamovible por interfaz) ---
SOFTWARE_NAME = "HALU - Sistema de Gestión Escolar"
SOFTWARE_LOGO_URL = "core/img/logo_mi_software.png" # Ruta relativa dentro de STATICFILES_DIRS
SOFTWARE_SLOGAN = "Conectando mentes, creando futuros."
SOFTWARE_CONTACT_EMAIL = "haluplataformaescolar@gmail.com"

# --- CONFIGURACIÓN DE ENVÍO DE CORREO ELECTRÓNICO (solo infraestructura Django) ---
# Los correos transaccionales por colegio usan SMTP definido en InstitucionEducativa
# (admisiones.utils.enviar_correo_dinamico, señales, etc.); no hay DEFAULT_FROM_EMAIL ni
# credenciales de tenant en este archivo.
#
# El backend global se usa para mensajes SIN contexto de institución: allauth,
# password reset, alertas internas, etc. Por defecto:
#   - DEBUG=True  -> console.EmailBackend (los correos se imprimen en consola).
#   - DEBUG=False -> smtp.EmailBackend (envía por SMTP global).
# Puedes forzar con la variable de entorno EMAIL_BACKEND.
_DEFAULT_EMAIL_BACKEND = (
    'django.core.mail.backends.console.EmailBackend' if DEBUG
    else 'django.core.mail.backends.smtp.EmailBackend'
)
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', _DEFAULT_EMAIL_BACKEND)

# Credenciales SMTP globales (solo se usan si EMAIL_BACKEND apunta al backend SMTP).
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587') or 587)
EMAIL_USE_TLS = (os.environ.get('EMAIL_USE_TLS', 'True').lower() in ('1', 'true', 'yes', 'on'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER or 'no-reply@halu.com')
EMAIL_TIMEOUT = 15  # segundos — evita que conexiones SMTP lentas bloqueen indefinidamente
# Brevo API (alternativa a SMTP en Railway donde los puertos SMTP están bloqueados).
# Cuando está presente, todos los correos transaccionales se envían vía HTTPS.
BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')
# Email verificado en Brevo como remitente (ej: haluplataformaescolar@gmail.com).
# Obligatorio cuando BREVO_API_KEY está activo; debe coincidir con un remitente
# verificado en la cuenta Brevo (NO usar el usuario SMTP de Brevo: xxxxxx@smtp-brevo.com).
BREVO_SENDER_EMAIL = os.environ.get('BREVO_SENDER_EMAIL', '')
BREVO_SENDER_NAME = os.environ.get('BREVO_SENDER_NAME', 'Halu Plataforma')

# Para correos a usuarios finales seguimos usando el SMTP por InstitucionEducativa
# (multi-tenant), vía admisiones.utils.enviar_correo_dinamico.

# --- (Opcional) CONFIGURACIÓN DE SIMPLE JWT ---
# Puedes añadir esto para configurar la duración de los tokens, etc.
# from datetime import timedelta
# 

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60), # Aumentado a 60 minutos
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
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

# ── A02 / A05: Clave de cifrado para campos sensibles en BD ──────────────────
FERNET_KEY = os.environ.get('FERNET_KEY', '')
if not DEBUG and not FERNET_KEY:
    import sys
    print("ERROR CRÍTICO: FERNET_KEY no está configurada en las variables de entorno.", file=sys.stderr)
    sys.exit(1)

# ── A05: Límites de tamaño para uploads y campos de formulario ───────────────
FILE_UPLOAD_MAX_MEMORY_SIZE = 15 * 1024 * 1024   # 15 MB (archivos en memoria)
DATA_UPLOAD_MAX_MEMORY_SIZE = 5  * 1024 * 1024   # 5 MB  (campos de formulario)
DATA_UPLOAD_MAX_NUMBER_FIELDS = 300               # máx 300 campos en un POST

# ── A05: Rate limiting ────────────────────────────────────────────────────────
RATELIMIT_USE_CACHE = 'default'
RATELIMIT_FAIL_OPEN = False  # Si el cache falla, bloquea (más seguro que dejar pasar)

# ── A05: Headers de seguridad — algunos aplican siempre, otros solo en producción
X_FRAME_OPTIONS             = 'DENY'       # Evita clickjacking en cualquier entorno
SECURE_CONTENT_TYPE_NOSNIFF = True         # Evita MIME-sniffing
SECURE_BROWSER_XSS_FILTER   = True

if not DEBUG:
    SECURE_SSL_REDIRECT            = True   # Redirige HTTP → HTTPS
    SESSION_COOKIE_SECURE          = True   # Cookie de sesión solo por HTTPS
    CSRF_COOKIE_SECURE             = True   # Cookie CSRF solo por HTTPS
    SESSION_COOKIE_HTTPONLY        = True   # JS no puede leer la cookie de sesión
    SECURE_HSTS_SECONDS            = 31536000  # 1 año de HSTS
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD            = True

# ── A09: Logs con ruta segura y rotación ─────────────────────────────────────
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(LOGS_DIR / "app.log"),
            "maxBytes": 10 * 1024 * 1024,  # 10 MB por archivo
            "backupCount": 5,               # Mantiene 5 archivos históricos
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
# Redis como backend de resultados: más rápido que la BD y no acumula rows en Django
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'America/Bogota'

# Concurrencia configurable. En SQLite conviene 1 (evita "database is locked");
# en PostgreSQL puedes subirlo (4-8 según CPU del host).
try:
    CELERY_WORKER_CONCURRENCY = int(os.environ.get('CELERY_WORKER_CONCURRENCY', '4'))
except ValueError:
    CELERY_WORKER_CONCURRENCY = 4

# Las tareas de admisiones/finanzas pueden ser largas: reportamos progreso a la BD
# en tiempo real y descartamos prefetch para que tareas pesadas no acaparen al worker.
CELERY_WORKER_PREFETCH_MULTIPLIER = int(
    os.environ.get('CELERY_WORKER_PREFETCH_MULTIPLIER', '1')
)

# Tareas programadas (Celery Beat)
from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    # Backup diario a las 2:00 AM hora Colombia
    'backup-diario': {
        'task': 'gestion_academica.tasks.ejecutar_backup_database',
        'schedule': crontab(hour=2, minute=0),
    },
}

# ── SENTRY — monitoreo de errores en producción ───────────────────────────────
SENTRY_DSN = os.environ.get('SENTRY_DSN', '')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration(), RedisIntegration()],
        traces_sample_rate=0.1,       # 10 % de requests trackeados (performance)
        send_default_pii=False,        # No enviar datos personales a Sentry
        environment='production' if not DEBUG else 'development',
        release=os.environ.get('GIT_COMMIT', 'unknown'),
    )
CELERY_TASK_ACKS_LATE = True

# --- CACHÉ ---
# Producción: Redis (db 2) — django_ratelimit exige un cache compartido.
# Desarrollo (sin REDIS_URL): memoria local.
_REDIS_URL = os.environ.get('REDIS_URL', '')
if _REDIS_URL:
    # REDIS_URL puede traer un número de db (ej. .../3 para channels);
    # el caché usa siempre la db 2.
    _base, _sep, _db = _REDIS_URL.rpartition('/')
    _cache_url = f"{_base}/2" if _db.isdigit() else f"{_REDIS_URL}/2"
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": _cache_url,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }

# --- SESIONES EN BASE DE DATOS (predeterminado Django, sin Redis) ---
# En producción cambiar a cache backend cuando Redis esté activo
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# --- CONFIGURACIÓN DE DJANGO CHANNELS ---
ASGI_APPLICATION = 'proyecto_colegio.asgi.application'

# db 0 → broker Celery | db 1 → results Celery | db 2 → caché+sesiones | db 3 → channel layer
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/3')],
            "capacity": 1500,       # mensajes en cola por grupo antes de descartar
            "expiry":   60,         # segundos que vive un mensaje no consumido
        },
    },
}
