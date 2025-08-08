from django.conf import settings

def branding_processor(request):
    """
    Añade las variables de marca del software (HALU) y la información
    de la institución específica del usuario al contexto de todas las plantillas.
    """
    
    # 1. Carga la información de la marca "HALU" desde settings.py
    #    Esta información es la misma para todos.
    software_branding = {
        'NOMBRE': getattr(settings, 'SOFTWARE_NAME', "HALU"),
        'LEMA': getattr(settings, 'SOFTWARE_SLOGAN', "Conectando mentes, creando futuros"),
        'LOGO_URL': getattr(settings, 'SOFTWARE_LOGO_URL', "core/img/default_logo.png"),
    }
    
    # 2. Carga la información de la institución específica del usuario logueado
    #    Esto será None si el usuario no está logueado o no tiene institución.
    institucion_actual = None
    if request.user.is_authenticated:
        # Verifica si el usuario tiene una institución asociada
        institucion_actual = getattr(request.user, 'institucion_asociada', None)

    # 3. Retorna un diccionario con todas las variables para las plantillas
    return {
        'branding': software_branding,
        'institucion_actual': institucion_actual,
    }
