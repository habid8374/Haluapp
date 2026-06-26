"""
AuditoriaMiddleware — guarda el request actual en thread-local para que las
signals de auditoría puedan acceder al usuario y la IP sin necesidad de
recibir esos datos explícitamente.

Además registra en la propia sesión la IP "en vivo" (la red desde la que el
usuario está navegando ahora mismo) y su última actividad, para que el panel
de Conexiones muestre la ubicación actual de cada sesión y pueda detectar una
sesión usada desde una IP distinta (señal típica de cookie robada).
"""
import threading
import time

_thread_locals = threading.local()

# Mínimo de segundos entre escrituras de "última actividad" para no guardar la
# sesión en cada request (la IP sí se actualiza siempre que cambie).
_INTERVALO_ACTIVIDAD = 120


def get_current_user():
    """Devuelve el usuario autenticado del request activo en este hilo, o None."""
    return getattr(_thread_locals, 'usuario', None)


def get_current_ip():
    """Devuelve la IP del request activo en este hilo, o None."""
    return getattr(_thread_locals, 'ip_address', None)


def _get_client_ip(request):
    """Extrae la IP del cliente de forma resistente a spoofing.

    X-Forwarded-For es controlable por el cliente, por lo que NO se confía en
    su primer valor. La entrada más cercana al servidor (la última de la lista)
    es la que añade el proxy de confianza; si no hay XFF, se usa REMOTE_ADDR.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[-1].strip()
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
        ip = _get_client_ip(request)
        _thread_locals.ip_address = ip

        response = self.get_response(request)

        # Actualizar la IP/actividad en vivo de la sesión. Se hace DESPUÉS de la
        # vista para que SessionMiddleware (que está antes en la lista, y por
        # tanto guarda al final) persista los cambios.
        self._actualizar_actividad_sesion(request, ip)

        # Limpiar después de cada request para no filtrar datos entre hilos reutilizados
        _thread_locals.usuario = None
        _thread_locals.ip_address = None

        return response

    @staticmethod
    def _actualizar_actividad_sesion(request, ip):
        """Guarda en la sesión la IP actual, el dispositivo y la última actividad.

        - La IP/dispositivo se reescriben solo cuando cambian (escrituras raras).
        - La marca de "última actividad" se actualiza como máximo cada
          _INTERVALO_ACTIVIDAD segundos para no guardar la sesión en cada request.
        """
        try:
            user = getattr(request, 'user', None)
            if user is None or not user.is_authenticated:
                return
            sesion = getattr(request, 'session', None)
            if sesion is None:
                return

            ua = (request.META.get('HTTP_USER_AGENT', '') or '')[:500]
            ahora = int(time.time())

            if sesion.get('_halu_ip') != ip:
                sesion['_halu_ip'] = ip
                sesion['_halu_ua'] = ua
            if ahora - int(sesion.get('_halu_seen', 0)) > _INTERVALO_ACTIVIDAD:
                sesion['_halu_seen'] = ahora
        except Exception:
            # Nunca interrumpir el request por el seguimiento de actividad.
            pass
