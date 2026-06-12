"""
AuditoriaMiddleware — guarda el request actual en thread-local para que las
signals de auditoría puedan acceder al usuario y la IP sin necesidad de
recibir esos datos explícitamente.
"""
import threading

_thread_locals = threading.local()


def get_current_user():
    """Devuelve el usuario autenticado del request activo en este hilo, o None."""
    return getattr(_thread_locals, 'usuario', None)


def get_current_ip():
    """Devuelve la IP del request activo en este hilo, o None."""
    return getattr(_thread_locals, 'ip_address', None)


def _get_client_ip(request):
    """Extrae la IP real del cliente respetando cabeceras de proxy."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class AuditoriaMiddleware:
    """
    Almacena request.user y la IP del cliente en variables thread-local
    para que las signals de post_save/post_delete puedan consultarlas.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Guardar usuario e IP antes de procesar la vista
        _thread_locals.usuario = getattr(request, 'user', None)
        _thread_locals.ip_address = _get_client_ip(request)

        response = self.get_response(request)

        # Limpiar después de cada request para no filtrar datos entre hilos reutilizados
        _thread_locals.usuario = None
        _thread_locals.ip_address = None

        return response
