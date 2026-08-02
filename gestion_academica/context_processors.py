from django.conf import settings
from django.db.models import Q
from django.utils import timezone


def branding_processor(request):
    """
    Añade las variables de marca del software (HALU) y la información
    de la institución específica del usuario al contexto de todas las plantillas.
    """

    software_branding = {
        'NOMBRE': getattr(settings, 'SOFTWARE_NAME', "HALU"),
        'LEMA': getattr(settings, 'SOFTWARE_SLOGAN', "Conectando mentes, creando futuros"),
        'LOGO_URL': getattr(settings, 'SOFTWARE_LOGO_URL', "core/img/default_logo.png"),
    }

    institucion_actual = None
    banners_activos = []

    if request.user.is_authenticated:
        institucion_actual = getattr(request.user, 'institucion_asociada', None)

        if institucion_actual:
            banners_activos = _get_banners_activos(request.user, institucion_actual)

    # Regla GLOBAL para mostrar el menú/administración de staff en cualquier
    # plantilla base (académico, admisiones, finanzas…). Los roles con panel
    # propio y acotado (tesorería, secretaría) NO ven el menú de staff completo
    # ni «Admin Avanzado», aunque tengan is_staff. Centralizado aquí para no
    # repetir la condición en cada base y que no vuelva a "expandirse" el navbar.
    ve_menu_staff = False
    if request.user.is_authenticated:
        _rol = getattr(request.user, 'rol', '') or ''
        ve_menu_staff = bool(request.user.is_staff and _rol not in ('tesoreria', 'secretaria', 'psicologo'))

    # ¿La institución usa el módulo de finanzas? Si NO (colegio público o con
    # usa_modulo_financiero=False), en los portales de estudiante y familiar se
    # oculta TODO lo relacionado con pagos/cartera (botón de pagos, estado de
    # cuenta, mensaje de "estás al día"…), porque ese colegio maneja lo
    # económico por fuera de la plataforma. Coincide con lo que bloquea
    # ModuloFinancieroMiddleware. Sin institución (p. ej. superusuario) → True.
    institucion_usa_finanzas = True
    if institucion_actual is not None:
        institucion_usa_finanzas = bool(
            getattr(institucion_actual, 'tipo_institucion', '') != 'publico'
            and getattr(institucion_actual, 'usa_modulo_financiero', True)
        )

    return {
        'branding': software_branding,
        'institucion_actual': institucion_actual,
        'banners_activos': banners_activos,
        've_menu_staff': ve_menu_staff,
        'institucion_usa_finanzas': institucion_usa_finanzas,
    }


def turnstile_processor(request):
    """Expone la configuración pública de Cloudflare Turnstile a las plantillas."""
    return {
        'TURNSTILE_ENABLED': getattr(settings, 'TURNSTILE_ENABLED', False),
        'TURNSTILE_SITE_KEY': getattr(settings, 'TURNSTILE_SITE_KEY', ''),
    }


def _get_banners_activos(user, institucion):
    try:
        from gestion_academica.models import Noticia
        hoy = timezone.now().date()
        cargo = getattr(user, 'cargo', '') or ''

        cargo_a_audiencia = {
            'docente': ['TODOS', 'DOCENTES'],
            'estudiante': ['TODOS', 'ESTUDIANTES'],
            'acudiente': ['TODOS', 'FAMILIAS'],
            'familiar': ['TODOS', 'FAMILIAS'],
            'coordinador': ['TODOS', 'DOCENTES'],
            'admin_institucion': ['TODOS', 'DOCENTES'],
        }
        audiencias_validas = cargo_a_audiencia.get(cargo, ['TODOS'])

        qs = Noticia.objects.filter(
            institucion=institucion,
            mostrar_banner=True,
            tipo__in=[Noticia.TIPO_URGENTE, Noticia.TIPO_EVENTO],
            audiencia__in=audiencias_validas,
        ).filter(
            Q(fecha_expiracion_banner__isnull=True) |
            Q(fecha_expiracion_banner__gte=hoy)
        ).order_by('-fecha_publicacion')[:5]

        return list(qs)
    except Exception:
        return []
