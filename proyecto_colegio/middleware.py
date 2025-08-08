# proyecto_colegio/middleware.py
from django.shortcuts import redirect
from django.contrib.auth import get_user_model
from django.urls import reverse # Necesario para resolver URLs por nombre
from django.conf import settings # Para acceder a STATIC_URL, MEDIA_URL
from django.contrib import messages
from django.contrib.auth import logout

class RedireccionRegistroInicialMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Rutas que DEBEN ser accesibles incluso si no hay usuarios registrados.
        EXCLUDED_PATHS = [
            reverse('gestion_academica:registro_inicial'), # La URL del formulario de registro inicial
            reverse('login'), # La URL de login estándar
            reverse('logout'), # La URL de logout estándar
            reverse('admin:index'), # El panel de administración
            
            # ¡CORRECCIÓN CLAVE AQUÍ! Usamos los nombres de URL directos (sin namespace)
            reverse('password_reset'),
            reverse('password_reset_done'),
            reverse('password_change'), 
            reverse('password_change_done'),
            # Las URLs de confirmación ('password_reset_confirm') y 'password_reset_complete'
            # tienen argumentos dinámicos (<uidb64>/<token>) que no se pueden usar con reverse() así.
            # Se excluyen por el prefijo '/accounts/' más abajo.
            # No las incluyas aquí directamente con reverse() sin argumentos.
        ]
        
        # Prefijos de URLs de autenticación o admin que también deberían ser excluidos
        # Esto capturará URLs como 'password_reset_confirm/<uidb64>/<token>/'
        AUTH_URL_PREFIXES = [
            '/accounts/', # Todas las URLs bajo /accounts/ (password_reset_confirm, etc.)
            '/admin/',    # Todas las URLs bajo /admin/
        ]
        
        current_path = request.path_info.split('?')[0] # Eliminar parámetros de query

        # Condición principal: Si no hay usuarios registrados
        if not get_user_model().objects.exists():
            # Y la ruta actual NO es una de las rutas excluidas explícitamente,
            # Y NO es una URL de archivos estáticos o de medios,
            # Y NO comienza con un prefijo de URL de autenticación o admin
            if current_path not in EXCLUDED_PATHS and \
               not current_path.startswith(settings.STATIC_URL) and \
               not current_path.startswith(settings.MEDIA_URL) and \
               not any(current_path.startswith(prefix) for prefix in AUTH_URL_PREFIXES):
                
                # Redirige al usuario al formulario de registro inicial
                return redirect('gestion_academica:registro_inicial') 
            
        response = self.get_response(request)
        return response
    

class InstitucionActivaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # El middleware no aplica para usuarios no autenticados o superusuarios
        if not request.user.is_authenticated or request.user.is_superuser:
            return self.get_response(request)

        # Excluimos la página de logout para evitar un bucle de redirección
        if request.path_info.startswith('/logout/'):
            return self.get_response(request)

        institucion = getattr(request.user, 'institucion_asociada', None)

        # Si el usuario tiene una institución y está marcada como NO activa
        if institucion and not institucion.activa:
            # Cerramos su sesión
            logout(request)
            # Le mostramos un mensaje claro
            messages.error(request, "El acceso para su institución ha sido suspendido. Por favor, contacte al administrador de la plataforma.")
            # Lo redirigimos a la página de login
            return redirect('login')

        # Si todo está en orden, la petición continúa normalmente
        return self.get_response(request)    