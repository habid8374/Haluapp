# gestion_academica/context_processors.py
from gestion_academica.models import ConfiguracionInstitucion # Usar importación absoluta

def datos_institucion_context(request):
    """
    Añade la configuración de la institución al contexto de las plantillas.
    """
    config = None
    try:
        # Intentamos obtener la primera (y única) instancia de ConfiguracionInstitucion.
        # Es importante que solo exista una fila en esta tabla.
        config = ConfiguracionInstitucion.objects.first()
    except Exception as e:
        # Opcional: registrar el error si algo sale mal al acceder a la BD
        # print(f"Error al obtener ConfiguracionInstitucion: {e}")
        pass # Si hay un error o no existe, config será None, y la plantilla usará el default.
        
    return {'configuracion_institucion': config}
