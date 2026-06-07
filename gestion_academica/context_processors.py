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

    return {
        'branding': software_branding,
        'institucion_actual': institucion_actual,
        'banners_activos': banners_activos,
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
