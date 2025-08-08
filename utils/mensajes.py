from functools import wraps
from django.contrib import messages


def mensaje_exito(texto="Operación realizada correctamente."):
    """Decorador para mostrar un mensaje de éxito luego de ejecutar una vista."""
    def decorador(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            response = view_func(request, *args, **kwargs)
            messages.success(request, texto)
            return response
        return _wrapped_view
    return decorador


def mensaje_error(texto="Ocurrió un error inesperado."):
    """Decorador para capturar errores y mostrar mensaje de error."""
    def decorador(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            try:
                return view_func(request, *args, **kwargs)
            except Exception as e:
                messages.error(request, f"{texto} - {str(e)}")
                raise  # re-levanta la excepción para que puedas verla en desarrollo
        return _wrapped_view
    return decorador


def mostrar_mensaje(request, texto, tipo="info"):
    """Función auxiliar para mostrar mensaje manual dentro de una vista."""
    tipos = {
        "success": messages.success,
        "error": messages.error,
        "warning": messages.warning,
        "info": messages.info,
    }
    tipos.get(tipo, messages.info)(request, texto)
